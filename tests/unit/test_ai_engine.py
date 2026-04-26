"""Unit tests for AI retrieval and response parsing behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.helpers.runtime import import_fresh


@pytest.fixture
def engine():
    """Import the AI engine with all external providers stubbed."""
    return import_fresh("chatbot_app.ai.engine")


@pytest.mark.unit
def test_embedding_returns_correct_shape(engine):
    """Embedding model should produce a deterministic 2D vector matrix."""
    embeddings = engine.get_embedding_model().encode(["red apple", "blue car"])

    assert embeddings.shape == (2, 4)


@pytest.mark.unit
def test_retrieval_returns_relevant_chunks(engine):
    """KnowledgeBase search should rank semantically closer chunks first."""
    kb = engine.KnowledgeBase()
    kb.process_chunks(["Fresh red apple in stock", "Blue family car available"])

    results = kb.search("apple", top_k=1)

    assert results == ["Fresh red apple in stock"]


@pytest.mark.unit
def test_empty_query_handled_safely(engine):
    """Empty search queries should return a list and never raise exceptions."""
    kb = engine.KnowledgeBase()
    kb.process_chunks(["General knowledge chunk"])

    results = kb.search("", top_k=2)

    assert isinstance(results, list)


@pytest.mark.unit
def test_knowledge_base_loads_correctly(engine):
    """Processing chunks should populate the KB chunk list and vector index."""
    kb = engine.KnowledgeBase()
    kb.process_chunks(["Chunk one", "Chunk two"])

    assert kb.chunks == ["Chunk one", "Chunk two"]
    assert kb.index is not None


@pytest.mark.unit
def test_generate_response_mocks_external_api_calls(engine, monkeypatch):
    """LLM calls should be mocked and still return parsed structured output."""

    def fake_create(**_kwargs):
        content = '{"message": "Products are available.", "options": ["Buy now"], "links": [], "db_action": null}'
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    monkeypatch.setattr(engine.groq_client.chat.completions, "create", fake_create)

    result = engine.generate_response("What can I buy?", ["Fresh red apple in stock"])

    assert result["message"] == "Products are available."
    assert result["options"] == ["Buy now"]
