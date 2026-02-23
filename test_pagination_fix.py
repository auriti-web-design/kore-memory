#!/usr/bin/env python3
"""Test rapido per verificare il fix pagination issue #2"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from src.database import init_db
from src.models import MemorySaveRequest
from src.repository import save_memory, search_memories

# Init DB
init_db()

# Pulisci test precedenti
from src.database import get_connection
with get_connection() as conn:
    conn.execute("DELETE FROM memories WHERE agent_id = 'test_pagination'")

print("🧪 Testing pagination fix...")

# Crea 20 memorie di test
print("\n1️⃣ Creando 20 memorie...")
for i in range(20):
    req = MemorySaveRequest(
        content=f"Test memory number {i+1:02d} for pagination testing",
        category="general",
        importance=3,
    )
    save_memory(req, agent_id="test_pagination")

print("✅ 20 memorie create")

# Test 1: Prima pagina (limit=5, no cursor)
print("\n2️⃣ Test prima pagina (limit=5, no cursor)...")
results1, cursor1 = search_memories("test memory", limit=5, semantic=False, agent_id="test_pagination")
print(f"   Risultati: {len(results1)}")
print(f"   Ha next cursor: {cursor1 is not None}")
print(f"   IDs: {[r.id for r in results1]}")
assert len(results1) == 5, f"Expected 5 results, got {len(results1)}"
assert cursor1 is not None, "Expected cursor for next page"

# Test 2: Seconda pagina (limit=5, with cursor)
print("\n3️⃣ Test seconda pagina (limit=5, with cursor)...")
results2, cursor2 = search_memories("test memory", limit=5, semantic=False, agent_id="test_pagination", cursor=cursor1)
print(f"   Risultati: {len(results2)}")
print(f"   Ha next cursor: {cursor2 is not None}")
print(f"   IDs: {[r.id for r in results2]}")
assert len(results2) == 5, f"Expected 5 results, got {len(results2)}"
assert cursor2 is not None, "Expected cursor for next page"

# Test 3: Verifica che non ci siano duplicati
print("\n4️⃣ Test no duplicati tra pagine...")
ids1 = {r.id for r in results1}
ids2 = {r.id for r in results2}
overlap = ids1 & ids2
assert len(overlap) == 0, f"Found duplicate IDs between pages: {overlap}"
print("   ✅ Nessun duplicato")

# Test 4: Pagina 3 e 4
print("\n5️⃣ Test pagine successive...")
results3, cursor3 = search_memories("test memory", limit=5, semantic=False, agent_id="test_pagination", cursor=cursor2)
results4, cursor4 = search_memories("test memory", limit=5, semantic=False, agent_id="test_pagination", cursor=cursor3)
print(f"   Pagina 3: {len(results3)} risultati, cursor={cursor3 is not None}")
print(f"   Pagina 4: {len(results4)} risultati, cursor={cursor4 is not None}")

# Test 5: Totale risultati
all_ids = {r.id for r in results1 + results2 + results3 + results4}
print(f"\n6️⃣ Totale IDs unici ottenuti: {len(all_ids)}")
assert len(all_ids) == 20, f"Expected 20 unique results, got {len(all_ids)}"

# Cleanup
with get_connection() as conn:
    conn.execute("DELETE FROM memories WHERE agent_id = 'test_pagination'")

print("\n✅ TUTTI I TEST PASSATI! Issue #2 è fixata! 🎉")
