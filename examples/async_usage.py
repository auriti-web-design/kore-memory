"""
Async usage of Kore Memory Python SDK.

Demonstrates how to:
- Use AsyncKoreClient for non-blocking operations
- Save and search memories asynchronously
- Run multiple operations concurrently with asyncio.gather
- Properly manage the async client lifecycle

Prerequisites:
    pip install kore-memory
    kore  # start the server on localhost:8765
"""

import asyncio

from kore_memory import AsyncKoreClient


async def main() -> None:
    # Create an async client. Use it as an async context manager
    # to ensure the underlying httpx.AsyncClient is properly closed.
    async with AsyncKoreClient(
        base_url="http://localhost:8765",
        agent_id="async-example-agent",
    ) as client:

        # -- Save multiple memories concurrently ------------------------------
        # asyncio.gather runs all coroutines concurrently, which is faster
        # than awaiting them sequentially.
        print("Saving memories concurrently...")
        results = await asyncio.gather(
            client.save(
                content="Python 3.12 introduces improved error messages.",
                category="general",
                importance=3,
            ),
            client.save(
                content="The async client uses httpx.AsyncClient under the hood.",
                category="decision",
                importance=2,
            ),
            client.save(
                content="Always close async clients to avoid resource leaks.",
                category="preference",
                importance=4,
            ),
        )
        print(f"Saved {len(results)} memories:")
        for r in results:
            print(f"  id={r.id}")

        # -- Search asynchronously --------------------------------------------
        print("\nSearching for 'async client'...")
        search_results = await client.search(q="async client", limit=5)
        print(f"Found {len(search_results.results)} result(s):")
        for mem in search_results.results:
            print(f"  [{mem.category}] {mem.content}")

        # -- Semantic search --------------------------------------------------
        print("\nSemantic search for 'how to avoid resource leaks'...")
        semantic_results = await client.search(
            q="how to avoid resource leaks",
            limit=3,
            semantic=True,
        )
        print(f"Found {len(semantic_results.results)} result(s):")
        for mem in semantic_results.results:
            print(f"  [{mem.category}] {mem.content}")

        # -- Timeline ---------------------------------------------------------
        print("\nFetching timeline...")
        timeline = await client.timeline(limit=10)
        print(f"Timeline has {len(timeline.memories)} memories:")
        for mem in timeline.memories:
            print(f"  [{mem.created_at}] {mem.content[:60]}")

        # -- Run multiple read operations concurrently ------------------------
        # This pattern is useful when you need data from multiple endpoints
        # at the same time.
        print("\nRunning concurrent search + timeline...")
        search_task, timeline_task = await asyncio.gather(
            client.search(q="Python", limit=3),
            client.timeline(limit=5),
        )
        print(f"Search found {len(search_task.results)} results")
        print(f"Timeline has {len(timeline_task.memories)} memories")

    # The async context manager ensures the client is closed here.
    print("\nDone! Client closed automatically.")


if __name__ == "__main__":
    asyncio.run(main())
