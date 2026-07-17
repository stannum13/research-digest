from ranking import RankablePaper, rank_papers, score_paper, select_diverse_top


def test_score_paper_is_deterministic() -> None:
    paper = RankablePaper(
        arxiv_id="2606.1",
        title="Mechanistic Interpretability for Language Model Reasoning",
        abstract=(
            "We present activation patching experiments, ablation studies, and baselines for a transformer reasoning circuit."
        ),
        primary_category="cs.LG",
        categories=["cs.LG"],
    )

    assert score_paper(paper) == score_paper(paper)
    assert score_paper(paper) > 5


def test_rank_penalizes_vague_survey() -> None:
    strong = RankablePaper(
        arxiv_id="2606.2",
        title="Quantum Error Correction Under Biased Noise",
        abstract="We report surface-code simulations, noise analysis, baselines, and ablations for quantum error correction.",
        primary_category="quant-ph",
        categories=["quant-ph"],
    )
    weak = RankablePaper(
        arxiv_id="2606.3",
        title="A Comprehensive Survey of Powerful AI",
        abstract="A comprehensive efficient robust powerful significant extensive promising survey.",
        primary_category="cs.AI",
        categories=["cs.AI"],
    )

    ranked = rank_papers([weak, strong])

    assert ranked[0].arxiv_id == strong.arxiv_id


def test_select_diverse_top_limits_early_bucket_repetition() -> None:
    papers = [
        RankablePaper(
            arxiv_id=f"2606.ml{i}",
            title=f"Language Model Agent Evaluation {i}",
            abstract="agent reasoning evaluation ablation baseline language model " * 8,
            primary_category="cs.LG",
            categories=["cs.LG"],
        )
        for i in range(6)
    ] + [
        RankablePaper(
            arxiv_id="2606.quantum",
            title="Quantum Error Correction with Noise",
            abstract="quantum error correction surface-code noise simulation baseline " * 8,
            primary_category="quant-ph",
            categories=["quant-ph"],
        )
    ]

    selected = select_diverse_top(papers, top_n=5)

    assert any(paper.primary_category == "quant-ph" for paper in selected)
    assert len(selected) == 5
