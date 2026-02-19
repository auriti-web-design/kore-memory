"""
Kore — import_memory.py
Popola il DB Kore leggendo MEMORY.md e suddividendo per sezioni.
Esegui una volta sola dopo l'installazione.
"""

import re
import sys
import json
from pathlib import Path

import httpx

MEMORY_PATH = Path(__file__).parent.parent.parent / "MEMORY.md"
KORE_URL = "http://localhost:8765"

SECTION_CATEGORY_MAP = {
    "finanz": "finance",
    "kore": "project",
    "progetti": "project",
    "clawdwork": "task",
    "freelance": "person",
    "crypto": "trading",
    "regole": "preference",
    "ottimizzaz": "preference",
    "calcfast": "project",
    "amazon": "project",
    "agencypilot": "project",
    "priorità": "task",
}

IMPORTANCE_MAP = {
    "finance": 4,
    "trading": 4,
    "project": 3,
    "task": 3,
    "preference": 5,
    "person": 2,
    "decision": 4,
    "general": 2,
}


def detect_category(section_title: str) -> str:
    title_lower = section_title.lower()
    for keyword, category in SECTION_CATEGORY_MAP.items():
        if keyword in title_lower:
            return category
    return "general"


def parse_memory_md(path: Path) -> list[dict]:
    """Split MEMORY.md into chunks by H2 section, return list of records."""
    text = path.read_text(encoding="utf-8")
    sections = re.split(r"\n(?=## )", text)

    records = []
    for section in sections:
        lines = section.strip().splitlines()
        if not lines:
            continue

        title_line = lines[0].lstrip("#").strip()
        body_lines = [l for l in lines[1:] if l.strip() and not l.startswith("---")]

        if not body_lines:
            continue

        category = detect_category(title_line)
        importance = IMPORTANCE_MAP.get(category, 2)

        # Split long sections into sub-chunks by bullet points
        chunks = chunk_section(title_line, body_lines)
        for chunk in chunks:
            records.append({
                "content": chunk,
                "category": category,
                "importance": importance,
            })

    return records


def chunk_section(title: str, lines: list[str]) -> list[str]:
    """
    Group bullet lines into chunks of max 3 items, prefixed with section title.
    Avoids saving single massive blobs.
    """
    bullets = [l.strip().lstrip("-").lstrip("*").strip() for l in lines if l.strip()]
    bullets = [b for b in bullets if len(b) > 10]

    if not bullets:
        return []

    chunks = []
    for i in range(0, len(bullets), 3):
        group = bullets[i:i+3]
        chunk = f"[{title}] " + " | ".join(group)
        if len(chunk) > 4000:
            chunk = chunk[:3997] + "..."
        chunks.append(chunk)

    return chunks


def save_record(record: dict) -> int | None:
    try:
        resp = httpx.post(f"{KORE_URL}/save", json=record, timeout=5)
        if resp.status_code == 201:
            return resp.json()["id"]
        else:
            print(f"  ⚠️  {resp.status_code}: {resp.text[:80]}")
            return None
    except Exception as e:
        print(f"  ❌ Errore: {e}")
        return None


def main():
    print(f"📂 Lettura {MEMORY_PATH}...")
    records = parse_memory_md(MEMORY_PATH)
    print(f"📝 Trovati {len(records)} chunk da importare\n")

    saved = 0
    for rec in records:
        record_id = save_record(rec)
        if record_id:
            print(f"  ✅ #{record_id} [{rec['category']}] ★{rec['importance']} — {rec['content'][:60]}...")
            saved += 1

    print(f"\n🎉 Importati {saved}/{len(records)} record in Kore")


if __name__ == "__main__":
    main()
