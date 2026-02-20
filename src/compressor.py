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

from dataclasses import dataclass

from .database import get_connection
from .embedder import cosine_similarity, deserialize, embed, serialize
from .models import MemorySaveRequest
from .repository import _compress_lock, save_memory

SIMILARITY_THRESHOLD = 0.88  # memorie sopra questa soglia sono considerate duplicati


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
            WHERE compressed_into IS NULL AND embedding IS NOT NULL AND agent_id = ?
            """,
            (agent_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _find_clusters(memories: list[dict]) -> list[list[dict]]:
    """
    Greedy clustering: group memories where any pair exceeds threshold.
    Each memory belongs to at most one cluster.
    """
    used = set()
    clusters = []

    for i, mem_a in enumerate(memories):
        if mem_a["id"] in used:
            continue

        vec_a = deserialize(mem_a["embedding"])
        cluster = [mem_a]

        for j, mem_b in enumerate(memories):
            if i == j or mem_b["id"] in used:
                continue
            vec_b = deserialize(mem_b["embedding"])
            if cosine_similarity(vec_a, vec_b) >= SIMILARITY_THRESHOLD:
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
    combined_parts = []
    seen = set()
    for mem in cluster:
        for sentence in mem["content"].split("|"):
            s = sentence.strip()
            if s and s not in seen:
                seen.add(s)
                combined_parts.append(s)

    merged_content = " | ".join(combined_parts)
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

    # Segna gli originali come compressi
    ids = [m["id"] for m in cluster]
    with get_connection() as conn:
        conn.executemany(
            "UPDATE memories SET compressed_into = ? WHERE id = ?",
            [(new_id, mid) for mid in ids],
        )

    return new_id
