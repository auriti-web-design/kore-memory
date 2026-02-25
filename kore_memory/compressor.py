"""
Kore — Memory Compressor
Finds clusters of similar memories and merges them into a single richer record.

Strategy:
  1. Load all memories without a compressed_into reference
  2. For each pair, compute cosine similarity
  3. Cluster memories with similarity > threshold
  4. Merge each cluster into one record (union of content, max importance)
  5. Mark originals as compressed_into the new record
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import config
from .database import get_connection
from .embedder import cosine_similarity, deserialize
from .models import MemorySaveRequest
from .repository import _compress_lock, save_memory

SIMILARITY_THRESHOLD = config.SIMILARITY_THRESHOLD

# --- numpy availability (optional, installed with [semantic]) ---
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]
    _HAS_NUMPY = False


@dataclass
class CompressionResult:
    clusters_found: int
    memories_merged: int
    new_records_created: int


def run_compression(agent_id: str = "default") -> CompressionResult:
    """
    Compressione completa: trova memorie simili e le unisce.
    Thread-safe: un solo run alla volta.
    """
    if not _compress_lock.acquire(blocking=False):
        return CompressionResult(0, 0, 0)  # run già in corso

    try:
        return _run_compression_inner(agent_id)
    finally:
        _compress_lock.release()


def _run_compression_inner(agent_id: str = "default") -> CompressionResult:
    memories = _load_compressible_memories(agent_id)
    if len(memories) < 2:
        return CompressionResult(0, 0, 0)

    clusters = _find_clusters(memories)
    if not clusters:
        return CompressionResult(0, 0, 0)

    merged = 0
    created = 0
    for cluster in clusters:
        new_id = _merge_cluster(cluster, agent_id=agent_id)
        if new_id:
            merged += len(cluster)
            created += 1

    return CompressionResult(
        clusters_found=len(clusters),
        memories_merged=merged,
        new_records_created=created,
    )


def _load_compressible_memories(agent_id: str = "default") -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, content, category, importance, embedding
            FROM memories
            WHERE compressed_into IS NULL AND archived_at IS NULL AND embedding IS NOT NULL AND agent_id = ?
            """,
            (agent_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _find_clusters(memories: list[dict]) -> list[list[dict]]:
    """
    Clustering greedy: trova gruppi di memorie con similarità > threshold.

    Uses numpy matrix multiplication when available for O(n²) batch similarity
    computation (much faster than O(n²) pure Python pairwise comparisons).
    Falls back to pure Python if numpy is not installed.
    """
    # Pre-deserializza tutti i vettori una sola volta
    vectors: dict[int, list[float]] = {}
    for mem in memories:
        try:
            vectors[mem["id"]] = deserialize(mem["embedding"])
        except Exception:
            continue

    # Filter to only memories with valid vectors
    valid_memories = [m for m in memories if m["id"] in vectors]

    if len(valid_memories) < 2:
        return []

    if _HAS_NUMPY:
        return _find_clusters_numpy(valid_memories, vectors)
    else:
        return _find_clusters_python(valid_memories, vectors)


def _find_clusters_numpy(
    memories: list[dict],
    vectors: dict[int, list[float]],
) -> list[list[dict]]:
    """
    Numpy-accelerated clustering: build similarity matrix via matrix multiplication,
    then extract pairs above threshold from the upper triangle.
    """
    mem_ids = [m["id"] for m in memories]
    matrix = np.array([vectors[mid] for mid in mem_ids], dtype=np.float32)

    # Similarity matrix: since vectors are normalized, dot product = cosine similarity
    sim_matrix = matrix @ matrix.T  # shape: (n, n)

    # Build adjacency from upper triangle (i < j) where similarity >= threshold
    n = len(memories)
    used: set[int] = set()
    clusters: list[list[dict]] = []

    for i in range(n):
        if i in used:
            continue

        cluster_indices = [i]
        # Find all j > i similar to i (greedy: cluster around first unseen)
        for j in range(i + 1, n):
            if j in used:
                continue
            if sim_matrix[i, j] >= SIMILARITY_THRESHOLD:
                cluster_indices.append(j)

        if len(cluster_indices) > 1:
            for idx in cluster_indices:
                used.add(idx)
            clusters.append([memories[idx] for idx in cluster_indices])

    return clusters


def _find_clusters_python(
    memories: list[dict],
    vectors: dict[int, list[float]],
) -> list[list[dict]]:
    """
    Pure Python fallback: O(n²/2) pairwise cosine similarity comparisons.
    """
    used: set[int] = set()
    clusters: list[list[dict]] = []

    for i, mem_a in enumerate(memories):
        if mem_a["id"] in used:
            continue

        vec_a = vectors[mem_a["id"]]
        cluster = [mem_a]

        # Confronta solo con memorie successive (evita doppi confronti)
        for mem_b in memories[i + 1:]:
            if mem_b["id"] in used:
                continue
            if cosine_similarity(vec_a, vectors[mem_b["id"]]) >= SIMILARITY_THRESHOLD:
                cluster.append(mem_b)

        if len(cluster) > 1:
            for m in cluster:
                used.add(m["id"])
            clusters.append(cluster)

    return clusters


def _merge_cluster(cluster: list[dict], agent_id: str = "default") -> int | None:
    """
    Merge a cluster of memories into a single new record.
    Returns the id of the new merged record, or None on failure.
    """
    if not cluster:
        return None

    # Build merged content: combine unique sentences
    # Split on sentence boundaries (. ! ? followed by space/end) instead of pipe
    combined_parts = []
    seen = set()
    for mem in cluster:
        sentences = re.split(r'(?<=[.!?])\s+', mem["content"].strip())
        for s in sentences:
            s = s.strip()
            if s and s not in seen:
                seen.add(s)
                combined_parts.append(s)

    merged_content = " ".join(combined_parts)
    if len(merged_content) > 4000:
        merged_content = merged_content[:3997] + "..."

    # Use the most common category and highest importance
    categories = [m["category"] for m in cluster]
    merged_category = max(set(categories), key=categories.count)
    merged_importance = max(m["importance"] for m in cluster)

    # Save the new merged record
    req = MemorySaveRequest(
        content=merged_content,
        category=merged_category,
        importance=merged_importance,
    )
    new_id, _ = save_memory(req, agent_id=agent_id)

    # Migra tag e relazioni dagli originali al nuovo record, poi segna come compressi
    ids = [m["id"] for m in cluster]
    with get_connection() as conn:
        # Copia tag unici al nuovo record
        placeholders = ",".join("?" for _ in ids)
        conn.execute(
            f"""INSERT OR IGNORE INTO memory_tags (memory_id, tag)
                SELECT ?, tag FROM memory_tags WHERE memory_id IN ({placeholders})""",
            [new_id, *ids],
        )

        # Ricollega relazioni: source_id -> new_id
        conn.execute(
            f"""UPDATE memory_relations SET source_id = ?
                WHERE source_id IN ({placeholders})""",
            [new_id, *ids],
        )
        # Ricollega relazioni: target_id -> new_id
        conn.execute(
            f"""UPDATE memory_relations SET target_id = ?
                WHERE target_id IN ({placeholders})""",
            [new_id, *ids],
        )
        # Rimuovi eventuali self-relations create dal relink
        conn.execute(
            "DELETE FROM memory_relations WHERE source_id = target_id",
        )

        # Segna gli originali come compressi
        conn.executemany(
            "UPDATE memories SET compressed_into = ? WHERE id = ?",
            [(new_id, mid) for mid in ids],
        )

    return new_id
