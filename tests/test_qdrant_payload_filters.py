"""
Qdrant payload filters — plan 0.15, the last open Phase-0 item.

Filters were string-concatenated into the query text and then embedded:

    enhanced_query = f"{query} category:{' OR '.join(categories)}"

which is a silent no-op. The words "category" and "rules" merely perturbed the
vector, so a rules lookup still searched all 11,017 chunks — including five
Stormlight novels — and `document_tag == "rules"` restricted nothing. The
retriever had accepted a `filters` argument all along; nothing ever passed one.

It was worse than a no-op in one respect: the agent only handled
`isinstance(filters, list)`, while the orchestrator sends
`{'value': '{"context_type": [...]}'}`, so `categories` was empty even on the
no-op path — visible in the live log as
`Applying contextual filters: {'value': '{"context_type": ["campaigns", ...'}`.

Verified against the live store (11,017 points): unfiltered retrieval returns
mixed `['lore', 'rules']`; filtering to `rules` returns only rules.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.unit]

from storage.simple_document_store import SimpleDocumentStore


class TestFilterNormalisation:
    """
    Callers send four different shapes. All must work — the bug was handling
    exactly one of them.
    """

    def test_a_plain_list(self):
        assert SimpleDocumentStore.build_payload_filter(["rules"]) == {
            "field": "meta.document_tag", "operator": "==", "value": "rules"}

    def test_several_categories_use_in(self):
        result = SimpleDocumentStore.build_payload_filter(["rules", "lore"])
        assert result["operator"] == "in"
        assert result["value"] == ["rules", "lore"]

    def test_a_context_type_dict(self):
        result = SimpleDocumentStore.build_payload_filter(
            {"context_type": ["rules", "lore"]})
        assert result["value"] == ["rules", "lore"]

    def test_the_shape_the_orchestrator_actually_sends(self):
        """
        The exact value from the live log — a dict whose "value" is a JSON
        STRING. The old code ignored it entirely.
        """
        result = SimpleDocumentStore.build_payload_filter(
            {"value": '{"context_type": ["campaigns", "items"]}'})
        assert result is not None, (
            "the orchestrator's own filter shape produced no filter")
        assert result["value"] == ["campaigns", "items"]

    def test_a_bare_string(self):
        assert SimpleDocumentStore.build_payload_filter("rules")["value"] == "rules"

    def test_no_filter_means_search_everything(self):
        """None is the correct default, not an empty match."""
        assert SimpleDocumentStore.build_payload_filter(None) is None
        assert SimpleDocumentStore.build_payload_filter([]) is None
        assert SimpleDocumentStore.build_payload_filter({}) is None
        assert SimpleDocumentStore.build_payload_filter("") is None

    def test_malformed_json_does_not_raise(self):
        """A broken filter must degrade to an unfiltered search, not a crash."""
        result = SimpleDocumentStore.build_payload_filter({"value": "{not json"})
        assert result is None or "value" in result

    def test_nested_lists_are_flattened(self):
        result = SimpleDocumentStore.build_payload_filter([["rules"], ["lore"]])
        assert result["value"] == ["rules", "lore"]

    def test_the_field_is_the_real_payload_path(self):
        """
        Chunks are written with `meta.document_tag` — verified by scrolling the
        live collection. A filter on the wrong path matches nothing, which looks
        exactly like a working filter on an empty result set.
        """
        result = SimpleDocumentStore.build_payload_filter(["rules"])
        assert result["field"] == "meta.document_tag"


class TestFiltersAreNotConcatenatedIntoTheQuery:
    """The regression itself: no filter may reach the embedder as text."""

    def test_the_store_no_longer_builds_an_enhanced_query(self):
        """
        Grep for the CONCATENATION, not the substring "category:" — that also
        appears in `debug_rag_print(category: str, ...)` and in the comment
        recording this bug.
        """
        source = (PROJECT_ROOT / "agents" / "rag_retriever_agent.py").read_text()
        offenders = [line.strip() for line in source.splitlines()
                     if "enhanced_query" in line and not line.strip().startswith("#")]
        assert not offenders, (
            "filters are still being concatenated into the query text, which is "
            f"a silent no-op: {offenders}")

    def test_the_store_passes_filters_to_the_retriever(self):
        import inspect

        source = inspect.getsource(SimpleDocumentStore.retrieve_documents)
        assert "filters" in source
        assert "build_payload_filter" in source

    def test_search_with_metadata_accepts_filters(self):
        import inspect

        parameters = inspect.signature(
            SimpleDocumentStore.search_with_metadata).parameters
        assert "filters" in parameters, (
            "the RAG agent's only search entry point cannot filter")

    def test_the_retriever_supports_filters_at_all(self):
        """If this ever stops being true, filtering is impossible — fail loudly."""
        import inspect

        from haystack_integrations.components.retrievers.qdrant import (
            QdrantEmbeddingRetriever)

        assert "filters" in inspect.signature(
            QdrantEmbeddingRetriever.run).parameters


@pytest.mark.integration
class TestFiltersRestrictTheLiveStore:
    """
    The end-to-end proof, against the real indexed corpus.

    Uses a random query vector deliberately: the correctness of FILTERING is
    independent of the embedding, and the embedder needs HuggingFace, which is
    not reachable from the test sandbox. What matters is which documents come
    back, not their ranking.
    """

    @pytest.fixture
    def retriever(self):
        storage = PROJECT_ROOT / "qdrant_storage"
        if not storage.exists():
            pytest.skip("no local qdrant_storage to filter against")

        import shutil
        import tempfile

        from haystack_integrations.components.retrievers.qdrant import (
            QdrantEmbeddingRetriever)
        from haystack_integrations.document_stores.qdrant import (
            QdrantDocumentStore)

        # Copy: a running game holds the single-writer lock on the real store.
        temp = Path(tempfile.mkdtemp()) / "qs"
        shutil.copytree(storage, temp)
        store = QdrantDocumentStore(path=str(temp), index="dnd_documents",
                                    embedding_dim=1024, recreate_index=False)
        yield QdrantEmbeddingRetriever(document_store=store, top_k=8)
        shutil.rmtree(temp, ignore_errors=True)

    @staticmethod
    def _vector():
        import random
        random.seed(1)
        return [random.random() for _ in range(1024)]

    def _tags(self, retriever, filters):
        documents = retriever.run(query_embedding=self._vector(),
                                  filters=filters)["documents"]
        return documents, sorted({(d.meta or {}).get("document_tag")
                                  for d in documents})

    def test_unfiltered_retrieval_mixes_categories(self, retriever):
        """The baseline — and the problem: a rules question hits novels."""
        documents, tags = self._tags(retriever, None)
        assert documents, "the store returned nothing at all"
        assert len(tags) > 1, (
            f"expected a mix of categories unfiltered, got {tags}")

    def test_filtering_to_rules_excludes_everything_else(self, retriever):
        documents, tags = self._tags(
            retriever, SimpleDocumentStore.build_payload_filter(["rules"]))
        assert documents, "the rules filter matched nothing — wrong payload path?"
        assert tags == ["rules"], f"rules filter also returned {tags}"

    def test_filtering_to_lore_excludes_rules(self, retriever):
        """Both directions: the filter must be selective, not just present."""
        documents, tags = self._tags(
            retriever, SimpleDocumentStore.build_payload_filter(["lore"]))
        assert documents
        assert tags == ["lore"], f"lore filter also returned {tags}"

    def test_two_categories_return_both(self, retriever):
        documents, tags = self._tags(
            retriever, SimpleDocumentStore.build_payload_filter(["rules", "lore"]))
        assert set(tags) <= {"rules", "lore"}
        assert documents

    def test_an_unknown_category_returns_nothing(self, retriever):
        """
        Proves the filter is really applied. If an impossible category still
        returned documents, the filter would be being ignored.
        """
        documents, _ = self._tags(
            retriever,
            SimpleDocumentStore.build_payload_filter(["no-such-category"]))
        assert documents == [], (
            f"{len(documents)} documents matched an impossible category — the "
            f"filter is not being applied")
