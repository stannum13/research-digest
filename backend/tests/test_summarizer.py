from datetime import UTC, datetime

from arxiv_client import ArxivPaper
from summarizer import estimate_cost_usd, prepare_summary_output


def test_estimate_cost_usd_uses_input_and_output_rates() -> None:
    assert (
        estimate_cost_usd(
            prompt_tokens=1_000_000,
            completion_tokens=500_000,
            input_price_per_m=1.40,
            output_price_per_m=4.40,
        )
        == 3.6
    )


def test_estimate_cost_usd_rounds_small_amounts() -> None:
    assert (
        estimate_cost_usd(
            prompt_tokens=1234,
            completion_tokens=567,
            input_price_per_m=1.40,
            output_price_per_m=4.40,
        )
        == 0.004222
    )


def test_failed_repair_falls_back_with_repair_metadata() -> None:
    paper = ArxivPaper(
        arxiv_id="2606.30001",
        arxiv_version="v1",
        title="Repair Test Paper",
        abstract="A paper about summary repair behavior.",
        authors=["Mira Chen"],
        primary_category="cs.LG",
        categories=["cs.LG"],
        published_at=datetime(2026, 6, 30, tzinfo=UTC),
        updated_at=datetime(2026, 6, 30, tzinfo=UTC),
        arxiv_url="https://arxiv.org/abs/2606.30001",
        pdf_url="https://arxiv.org/pdf/2606.30001",
        raw_metadata={},
    )
    raw = {
        "one_line_takeaway": 123,
        "_llm_usage": {
            "provider": "openai",
            "model_name": "summary-test",
            "prompt_tokens": 10,
            "completion_tokens": 3,
            "total_tokens": 13,
            "estimated_cost_usd": 0.001,
        },
    }

    def repairer(_paper: ArxivPaper, _raw: object, _error: str, _full_text: str) -> dict:
        return {
            "simple_summary": "",
            "_llm_usage": {
                "provider": "openai",
                "model_name": "summary-test",
                "prompt_tokens": 7,
                "completion_tokens": 2,
                "total_tokens": 9,
                "estimated_cost_usd": 0.0005,
            },
        }

    prepared = prepare_summary_output(raw, paper, repairer=repairer)

    assert prepared.validation_status == "fallback"
    assert prepared.repair_attempted is True
    assert prepared.repair_error
    assert prepared.cacheable is False
    assert prepared.data["model_provider"] == "mock"
    assert prepared.data["_summary_repair_attempted"] is True
    assert prepared.data["_summary_repair_prompt_version"] == "paper-summary-repair-v1"
    assert prepared.data["_llm_usage"] == {
        "provider": "openai",
        "model_name": "summary-test",
        "prompt_tokens": 17,
        "completion_tokens": 5,
        "total_tokens": 22,
        "estimated_cost_usd": 0.0015,
    }
