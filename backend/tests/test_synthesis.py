import pytest

from synthesis import SynthesisValidationError, prepare_provider_synthesis_output


def test_provider_synthesis_validation_rejects_unsourced_claims() -> None:
    fallback = {"source_paper_ids": [1, 2]}
    raw = {
        "argument_map": [{"claim": "Unsupported cross-paper claim"}],
        "contradictions": [{"source_paper_ids": [1], "status": "not_detected"}],
        "evidence_matrix": [{"source_paper_ids": [1], "evidence": "Evidence"}],
        "open_questions": [{"source_paper_ids": [2], "question": "Question?"}],
        "extension_ideas": [{"source_paper_ids": [1, 2], "idea": "Idea"}],
        "replication_or_ablation_plan": [{"source_paper_ids": [1], "action": "Ablate"}],
        "caveats": [{"source_paper_ids": [2], "caveat": "Caveat"}],
    }

    with pytest.raises(SynthesisValidationError, match="missing source_paper_ids"):
        prepare_provider_synthesis_output(
            raw=raw,
            fallback=fallback,
            provider="zai",
            model_name="glm-test",
        )
