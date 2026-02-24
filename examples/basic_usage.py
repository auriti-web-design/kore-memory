"""
Basic usage of Kore Memory Python SDK.

Demonstrates how to:
- Connect to a running Kore server
- Save memories with categories and importance
- Search memories (full-text and semantic)
- Retrieve a timeline of recent memories
- Work with tags and relations

Prerequisites:
    pip install kore-memory
    kore  # start the server on localhost:8765
"""

from kore_memory import KoreClient


def main() -> None:
    # Connect to the Kore server.
    # When running locally with KORE_LOCAL_ONLY=1, no API key is needed.
    # For authenticated servers, pass api_key="your-key".
    client = KoreClient(
        base_url="http://localhost:8765",
        agent_id="example-agent",
    )

    # -- Save memories --------------------------------------------------------
    # Save a simple memory. The server auto-scores importance if you pass 1.
    result = client.save(
        content="The project deadline is March 15th.",
        category="project",
        importance=1,  # auto-scored by the server
    )
    project_memory_id = result.id
    print(f"Saved project memory: id={project_memory_id}")

    # Save a memory with explicit importance (1=low, 5=critical)
    result = client.save(
        content="Always use UTC timestamps in the API.",
        category="decision",
        importance=4,
    )
    decision_memory_id = result.id
    print(f"Saved decision memory: id={decision_memory_id}")

    # Save a preference memory
    client.save(
        content="User prefers dark mode and compact layout.",
        category="preference",
        importance=3,
    )
    print("Saved preference memory.")

    # -- Search memories ------------------------------------------------------
    # Full-text search (uses SQLite FTS5 under the hood)
    search_results = client.search(q="deadline", limit=5)
    print(f"\nSearch for 'deadline': {len(search_results.results)} result(s)")
    for mem in search_results.results:
        print(f"  [{mem.category}] {mem.content} (score={mem.effective_score:.2f})")

    # Semantic search (requires sentence-transformers installed on the server)
    semantic_results = client.search(q="when is the project due?", limit=5, semantic=True)
    print(f"\nSemantic search for 'when is the project due?': {len(semantic_results.results)} result(s)")
    for mem in semantic_results.results:
        print(f"  [{mem.category}] {mem.content}")

    # -- Timeline -------------------------------------------------------------
    # Get recent memories ordered by creation time
    timeline = client.timeline(limit=10)
    print(f"\nTimeline ({len(timeline.memories)} memories):")
    for mem in timeline.memories:
        print(f"  [{mem.created_at}] {mem.content[:60]}...")

    # -- Tags -----------------------------------------------------------------
    # Add tags to a memory for easy filtering
    client.add_tags(memory_id=project_memory_id, tags=["deadline", "q1-2026"])
    print(f"\nAdded tags to memory {project_memory_id}")

    # Retrieve tags for a memory
    tags = client.get_tags(memory_id=project_memory_id)
    print(f"Tags: {tags.tags}")

    # -- Relations ------------------------------------------------------------
    # Create a relation between two memories
    client.add_relation(
        source_id=project_memory_id,
        target_id=decision_memory_id,
        relation_type="informs",
    )
    print(f"\nCreated relation: {project_memory_id} --informs--> {decision_memory_id}")

    # Retrieve relations for a memory
    relations = client.get_relations(memory_id=project_memory_id)
    print(f"Relations: {len(relations.relations)} relation(s)")

    # -- Cleanup --------------------------------------------------------------
    # Close the HTTP client when done
    client.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
