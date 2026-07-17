from collections import Counter
from dataclasses import dataclass

POSITIVE_TERMS = {
    "agent": 2.4,
    "agents": 2.4,
    "language model": 2.2,
    "llm": 2.2,
    "reasoning": 2.0,
    "interpretability": 2.0,
    "mechanistic": 2.0,
    "post-training": 1.8,
    "retrieval": 1.6,
    "evaluation": 1.4,
    "robustness": 1.4,
    "scaling": 1.4,
    "multimodal": 1.4,
    "diffusion": 1.4,
    "optimization": 1.2,
    "quantum error correction": 2.5,
    "error correction": 2.0,
    "quantum algorithm": 2.2,
    "hamiltonian": 1.9,
    "tensor network": 1.8,
    "variational quantum": 1.7,
    "noise": 1.3,
    "decoherence": 1.3,
}

EVIDENCE_TERMS = {
    "ablation": 1.4,
    "baseline": 1.1,
    "proof": 1.2,
    "theorem": 1.1,
    "experiment": 1.1,
    "benchmark": 0.8,
    "simulation": 1.0,
    "dataset": 0.8,
    "open-source": 0.7,
    "code": 0.6,
}

NEGATIVE_TERMS = {
    "survey": 2.0,
    "position paper": 1.6,
    "preliminary": 1.0,
    "state-of-the-art": 0.7,
    "sota": 0.7,
    "novel framework": 0.6,
}

VAGUE_TERMS = {"comprehensive", "efficient", "robust", "powerful", "significant", "extensive", "promising"}

CATEGORY_BUCKETS = {
    "cs.LG": "ml",
    "stat.ML": "ml",
    "cs.AI": "ai",
    "cs.CL": "language",
    "cs.CV": "vision",
    "quant-ph": "quantum",
}


@dataclass(frozen=True)
class RankablePaper:
    arxiv_id: str
    title: str
    abstract: str
    primary_category: str
    categories: list[str]
    score: float | None = None


def _contains_count(text: str, weighted_terms: dict[str, float]) -> float:
    lower = text.lower()
    return sum(weight for term, weight in weighted_terms.items() if term in lower)


def score_paper(paper: RankablePaper) -> float:
    text = f"{paper.title}\n{paper.abstract}"
    lower = text.lower()
    score = 0.0
    score += _contains_count(lower, POSITIVE_TERMS)
    score += _contains_count(lower, EVIDENCE_TERMS)
    score -= _contains_count(lower, NEGATIVE_TERMS)

    if any(category in {"cs.LG", "cs.AI", "cs.CL", "cs.CV", "stat.ML", "quant-ph"} for category in paper.categories):
        score += 1.5
    if paper.primary_category == "quant-ph" and ("hardware" in lower or "noise" in lower or "fault-tolerant" in lower):
        score += 0.9
    if len(paper.abstract.split()) < 70:
        score -= 1.5
    if sum(1 for term in VAGUE_TERMS if term in lower) >= 4:
        score -= 1.2
    if "without" in lower and ("ablation" in lower or "baseline" in lower or "evaluation" in lower):
        score -= 0.6

    return round(max(score, 0.0), 3)


def rank_papers(papers: list[RankablePaper]) -> list[RankablePaper]:
    return sorted(
        (RankablePaper(**{**paper.__dict__, "score": score_paper(paper)}) for paper in papers),
        key=lambda paper: (paper.score or 0, paper.title),
        reverse=True,
    )


def select_diverse_top(papers: list[RankablePaper], top_n: int) -> list[RankablePaper]:
    ranked = rank_papers(papers)
    selected: list[RankablePaper] = []
    bucket_counts: Counter[str] = Counter()

    for paper in ranked:
        bucket = CATEGORY_BUCKETS.get(paper.primary_category, "other")
        if bucket_counts[bucket] >= 3 and len(selected) < max(5, top_n // 2):
            continue
        selected.append(paper)
        bucket_counts[bucket] += 1
        if len(selected) == top_n:
            return selected

    selected_ids = {paper.arxiv_id for paper in selected}
    for paper in ranked:
        if paper.arxiv_id not in selected_ids:
            selected.append(paper)
        if len(selected) == top_n:
            break
    return selected
