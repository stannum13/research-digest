import json
from datetime import UTC, datetime
from types import SimpleNamespace

from paperqa_adapter import paper_to_document_spec


def test_paperqa_document_spec_preserves_citation_and_source_boundaries() -> None:
    paper = SimpleNamespace(
        arxiv_id="2607.12345",
        arxiv_version="v2",
        title="Budget-Aware Scientific Retrieval",
        abstract="We test retrieval policies with exact source citations.",
        authors_json=json.dumps(["Ada Lovelace", "Grace Hopper", "Katherine Johnson"]),
        primary_category="cs.IR",
        categories_json=json.dumps(["cs.IR", "cs.AI"]),
        published_at=datetime(2026, 7, 1, tzinfo=UTC),
        updated_at=datetime(2026, 7, 2, tzinfo=UTC),
        arxiv_url="https://arxiv.org/abs/2607.12345",
        pdf_url="https://arxiv.org/pdf/2607.12345",
    )
    breakdown = SimpleNamespace(
        one_line_takeaway="Adaptive stopping saves calls when evidence is redundant.",
        context="Scientific QA pipelines can over-retrieve evidence.",
        what_is_new="The paper links stopping decisions to citation coverage.",
        mechanism="A reranker tracks redundancy, coverage, and uncertainty.",
        evidence="Evidence comes from source-linked QA tasks.",
        methodology_caveats_json=json.dumps(["Full-text availability is uneven."]),
        meaningful_extensions_json=json.dumps(["Run by subdomain."]),
        confidence="medium",
        source_basis="abstract_plus_metadata",
    )

    spec = paper_to_document_spec(paper, breakdown)

    assert spec.docname == "arxiv:2607.12345"
    assert spec.citation == "Ada Lovelace et al. (2026). Budget-Aware Scientific Retrieval. arXiv:2607.12345."
    assert "Abstract:\nWe test retrieval policies with exact source citations." in spec.text
    assert "Marginalia summary:\nAdaptive stopping saves calls when evidence is redundant." in spec.text
    assert "Caveats:\n- Full-text availability is uneven." in spec.text
    assert spec.metadata["source_kind"] == "marginalia_paper"
    assert spec.metadata["arxiv_version"] == "v2"
    assert spec.metadata["has_marginalia_summary"] is True
    assert spec.metadata["categories"] == ["cs.IR", "cs.AI"]
