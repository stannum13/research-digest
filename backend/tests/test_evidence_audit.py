from evidence_audit import audit_synthesis_source_refs


def test_synthesis_audit_allows_explicit_speculation_without_source_refs() -> None:
    data = {
        "argument_map": [{"source_paper_ids": [1], "claim": "Sourced claim"}],
        "contradictions": [{"source_paper_ids": [1, 2], "status": "not_detected"}],
        "evidence_matrix": [{"source_paper_ids": [2], "evidence": "Evidence"}],
        "open_questions": [{"source_paper_ids": [1], "question": "Question?"}],
        "extension_ideas": [{"speculative": True, "idea": "Speculative extension"}],
        "replication_or_ablation_plan": [{"source_paper_ids": [1], "action": "Ablate"}],
        "caveats": [{"source_paper_ids": [2], "caveat": "Caveat"}],
    }

    assert audit_synthesis_source_refs(data, [1, 2]) == []
    assert data["extension_ideas"][0]["source_paper_ids"] == []
