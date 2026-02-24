"""
Kore — MCP server tests
Tests MCP tool functions directly (no MCP protocol needed).
Each tool is a plain Python function that calls repository layer.

Setup: temp DB + local-only mode, same pattern as test_api.py.
Must set env vars BEFORE importing mcp_server (it calls init_db at import time).
"""

import os
import tempfile

import pytest

# DB temporaneo + local-only mode — DEVE essere impostato prima dell'import
os.environ["KORE_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["KORE_LOCAL_ONLY"] = "1"

from kore_memory.mcp_server import (  # noqa: E402
    memory_add_relation,
    memory_add_tags,
    memory_cleanup,
    memory_delete,
    memory_export,
    memory_import,
    memory_save,
    memory_save_batch,
    memory_search,
    memory_search_by_tag,
    memory_timeline,
    memory_update,
)

AGENT = "mcp-test-agent"


class TestMemorySave:
    def test_save_returns_id_and_importance(self):
        result = memory_save(
            content="MCP test: remember this important fact",
            category="general",
            agent_id=AGENT,
        )
        assert "id" in result
        assert result["id"] > 0
        assert "importance" in result
        assert result["importance"] >= 1
        assert result["message"] == "Memory saved"

    def test_save_with_explicit_importance(self):
        result = memory_save(
            content="Critical security credential for production",
            category="project",
            importance=5,
            agent_id=AGENT,
        )
        assert result["importance"] == 5

    def test_save_with_category(self):
        result = memory_save(
            content="Juan prefers dark mode in all editors",
            category="preference",
            agent_id=AGENT,
        )
        assert result["id"] > 0


class TestMemorySearch:
    def test_search_finds_saved_memory(self):
        memory_save(
            content="Semantic search test: unique kangaroo phrase",
            category="general",
            agent_id=AGENT,
        )
        result = memory_search(
            query="kangaroo",
            limit=5,
            semantic=False,
            agent_id=AGENT,
        )
        assert "results" in result
        assert "total" in result
        assert "has_more" in result
        assert any("kangaroo" in r["content"] for r in result["results"])

    def test_search_returns_empty_for_no_match(self):
        result = memory_search(
            query="zzzyyyxxx_nonexistent_term",
            limit=5,
            semantic=False,
            agent_id=AGENT,
        )
        assert result["results"] == []

    def test_search_with_category_filter(self):
        memory_save(
            content="Finance test: quarterly earnings report analysis",
            category="finance",
            agent_id=AGENT,
        )
        result = memory_search(
            query="earnings",
            limit=5,
            category="finance",
            semantic=False,
            agent_id=AGENT,
        )
        found = result["results"]
        assert all(r["category"] == "finance" for r in found)


class TestMemoryDelete:
    def test_delete_existing_memory(self):
        saved = memory_save(
            content="This memory will be deleted soon",
            category="general",
            agent_id=AGENT,
        )
        mem_id = saved["id"]
        result = memory_delete(memory_id=mem_id, agent_id=AGENT)
        assert result["success"] is True
        assert result["message"] == "Memory deleted"

    def test_delete_nonexistent_memory(self):
        result = memory_delete(memory_id=999999, agent_id=AGENT)
        assert result["success"] is False
        assert result["message"] == "Memory not found"

    def test_delete_wrong_agent(self):
        saved = memory_save(
            content="Memory owned by mcp-test-agent only",
            category="general",
            agent_id=AGENT,
        )
        result = memory_delete(memory_id=saved["id"], agent_id="wrong-agent")
        assert result["success"] is False


class TestMemoryUpdate:
    def test_update_content(self):
        saved = memory_save(
            content="Original content before update",
            category="general",
            agent_id=AGENT,
        )
        result = memory_update(
            memory_id=saved["id"],
            content="Updated content after modification",
            agent_id=AGENT,
        )
        assert result["success"] is True
        assert result["message"] == "Memory updated"

    def test_update_category(self):
        saved = memory_save(
            content="Will change category from general to project",
            category="general",
            agent_id=AGENT,
        )
        result = memory_update(
            memory_id=saved["id"],
            category="project",
            agent_id=AGENT,
        )
        assert result["success"] is True

    def test_update_importance(self):
        saved = memory_save(
            content="Will increase importance to maximum",
            category="general",
            importance=1,
            agent_id=AGENT,
        )
        result = memory_update(
            memory_id=saved["id"],
            importance=5,
            agent_id=AGENT,
        )
        assert result["success"] is True

    def test_update_nonexistent(self):
        result = memory_update(
            memory_id=999999,
            content="This should fail",
            agent_id=AGENT,
        )
        assert result["success"] is False
        assert result["message"] == "Memory not found"


class TestMemoryAddTags:
    def test_add_tags_to_memory(self):
        saved = memory_save(
            content="Memory that needs tags for organization",
            category="general",
            agent_id=AGENT,
        )
        result = memory_add_tags(
            memory_id=saved["id"],
            tags=["python", "testing", "mcp"],
            agent_id=AGENT,
        )
        assert result["count"] == 3
        assert "3 tags added" in result["message"]

    def test_add_tags_to_nonexistent_memory(self):
        result = memory_add_tags(
            memory_id=999999,
            tags=["orphan"],
            agent_id=AGENT,
        )
        assert result["count"] == 0


class TestMemorySearchByTag:
    def test_search_by_tag_finds_tagged_memory(self):
        saved = memory_save(
            content="Tagged memory for search by tag test",
            category="project",
            agent_id=AGENT,
        )
        memory_add_tags(
            memory_id=saved["id"],
            tags=["unique-tag-xyz"],
            agent_id=AGENT,
        )
        result = memory_search_by_tag(
            tag="unique-tag-xyz",
            agent_id=AGENT,
        )
        assert result["total"] >= 1
        assert any(r["id"] == saved["id"] for r in result["results"])

    def test_search_by_tag_no_results(self):
        result = memory_search_by_tag(
            tag="nonexistent-tag-abc",
            agent_id=AGENT,
        )
        assert result["total"] == 0
        assert result["results"] == []


class TestMemoryCleanup:
    def test_cleanup_returns_count(self):
        result = memory_cleanup(agent_id=AGENT)
        assert "removed" in result
        assert isinstance(result["removed"], int)
        assert "message" in result


class TestMemoryExport:
    def test_export_returns_memories(self):
        # Save a memory first to ensure there's something to export
        memory_save(
            content="Memory for export test verification",
            category="general",
            agent_id=AGENT,
        )
        result = memory_export(agent_id=AGENT)
        assert "memories" in result
        assert "total" in result
        assert result["total"] >= 1
        assert isinstance(result["memories"], list)

    def test_export_empty_agent(self):
        result = memory_export(agent_id="empty-agent-no-memories")
        assert result["total"] == 0
        assert result["memories"] == []


class TestMemoryImport:
    def test_import_memories(self):
        records = [
            {"content": "Imported memory one for testing", "category": "general", "importance": 2},
            {"content": "Imported memory two for testing", "category": "project", "importance": 3},
        ]
        result = memory_import(memories=records, agent_id=AGENT)
        assert result["imported"] == 2
        assert "2 memories imported" in result["message"]

    def test_import_skips_invalid(self):
        records = [
            {"content": "Valid imported memory content"},
            {"content": "ab"},           # too short (< 3 chars)
            {"content": "  "},           # blank
            {"content": ""},             # empty
        ]
        result = memory_import(memories=records, agent_id=AGENT)
        assert result["imported"] == 1


class TestMemorySaveBatch:
    def test_save_batch(self):
        memories = [
            {"content": "Batch memory alpha for testing", "category": "general"},
            {"content": "Batch memory beta for testing", "category": "project", "importance": 3},
        ]
        result = memory_save_batch(memories=memories, agent_id=AGENT)
        assert result["total"] == 2
        assert len(result["saved"]) == 2
        assert all("id" in s for s in result["saved"])

    def test_save_batch_skips_invalid(self):
        memories = [
            {"content": "Valid batch content here"},
            {"content": "ab"},   # too short
        ]
        result = memory_save_batch(memories=memories, agent_id=AGENT)
        assert result["total"] == 1


class TestMemoryAddRelation:
    def test_add_relation_between_memories(self):
        m1 = memory_save(content="Source memory for relation test", category="general", agent_id=AGENT)
        m2 = memory_save(content="Target memory for relation test", category="general", agent_id=AGENT)
        result = memory_add_relation(
            source_id=m1["id"],
            target_id=m2["id"],
            relation="related",
            agent_id=AGENT,
        )
        assert result["success"] is True
        assert result["message"] == "Relation created"

    def test_add_relation_nonexistent_memory(self):
        m1 = memory_save(content="Existing memory for failed relation", category="general", agent_id=AGENT)
        result = memory_add_relation(
            source_id=m1["id"],
            target_id=999999,
            relation="related",
            agent_id=AGENT,
        )
        assert result["success"] is False


class TestMemoryTimeline:
    def test_timeline_returns_results(self):
        memory_save(
            content="Timeline event: project Kore started development",
            category="project",
            agent_id=AGENT,
        )
        result = memory_timeline(
            subject="Kore",
            limit=10,
            agent_id=AGENT,
        )
        assert "results" in result
        assert "total" in result
        assert "has_more" in result
        assert isinstance(result["results"], list)
