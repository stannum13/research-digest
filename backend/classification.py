from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from models import Paper, PaperClassification

CLASSIFICATION_SOURCE = "metadata-breakdown-heuristic-v1"
LABEL_TYPES = (
    "method_family",
    "evidence_type",
    "caveat_class",
    "task",
    "dataset_or_benchmark",
    "architecture_primitive",
    "probe_family",
)
LABEL_TYPE_INDEX = {label_type: index for index, label_type in enumerate(LABEL_TYPES)}


@dataclass(frozen=True)
class Rule:
    label_type: str
    label: str
    keywords: tuple[str, ...]
    confidence: float
    rationale: str


@dataclass(frozen=True)
class ClassificationCandidate:
    label_type: str
    label: str
    confidence: float
    rationale: str


RULES = (
    Rule(
        label_type="method_family",
        label="agent_systems",
        keywords=("long-horizon agent", "language agents", "tool use", "planning-and-audit", "state tracking"),
        confidence=0.86,
        rationale="The paper text describes an agent system or tool-use control loop.",
    ),
    Rule(
        label_type="method_family",
        label="mechanistic_interpretability",
        keywords=(
            "interpretability",
            "activation patching",
            "circuit motif",
            "sparse activation",
            "causal intervention",
        ),
        confidence=0.9,
        rationale="The paper text describes causal or circuit-level model interpretability.",
    ),
    Rule(
        label_type="method_family",
        label="benchmarking",
        keywords=("benchmark", "dataset", "scoring rubric", "evaluate frontier and open models"),
        confidence=0.88,
        rationale="The paper text frames the contribution as a benchmark, dataset, or evaluation rubric.",
    ),
    Rule(
        label_type="method_family",
        label="generative_augmentation",
        keywords=("diffusion prior", "feature-space augmentation", "generates local", "synthetic patches"),
        confidence=0.86,
        rationale="The paper text describes generative augmentation as the method family.",
    ),
    Rule(
        label_type="method_family",
        label="preference_optimization",
        keywords=("preference optimization", "pairwise comparisons", "reward modeling", "annotator noise"),
        confidence=0.86,
        rationale="The paper text centers on preference optimization or reward-modeling methods.",
    ),
    Rule(
        label_type="method_family",
        label="quantum_error_correction",
        keywords=("quantum error correction", "surface-code", "syndrome-aware decoder", "logical error"),
        confidence=0.88,
        rationale="The paper text describes quantum error-correction decoding.",
    ),
    Rule(
        label_type="method_family",
        label="quantum_algorithm",
        keywords=("hamiltonian simulation", "block-encoding", "query complexity", "oracle access"),
        confidence=0.88,
        rationale="The paper text describes a quantum algorithmic construction.",
    ),
    Rule(
        label_type="method_family",
        label="retrieval_augmented_training",
        keywords=("retrieval-calibrated", "hard negative retrieval", "cross-modal search", "retrieval signal"),
        confidence=0.86,
        rationale="The paper text describes retrieval pressure or retrieval-calibrated training.",
    ),
    Rule(
        label_type="evidence_type",
        label="benchmark_evaluation",
        keywords=("benchmark", "benchmarks", "evaluate frontier", "evaluations across", "scoring rubric"),
        confidence=0.84,
        rationale="The evidence is reported as benchmark or rubric-based evaluation.",
    ),
    Rule(
        label_type="evidence_type",
        label="empirical_evaluation",
        keywords=("experiments", "evaluated", "results suggest", "baseline comparisons", "comparisons"),
        confidence=0.76,
        rationale="The paper text reports experiments or empirical comparisons.",
    ),
    Rule(
        label_type="evidence_type",
        label="ablation_study",
        keywords=("ablation", "ablations", "ablates", "removes part"),
        confidence=0.82,
        rationale="The paper text reports ablations.",
    ),
    Rule(
        label_type="evidence_type",
        label="causal_intervention",
        keywords=("causal intervention", "causal interventions", "activation patching", "patch activations"),
        confidence=0.9,
        rationale="The evidence includes causal interventions or activation patching.",
    ),
    Rule(
        label_type="evidence_type",
        label="robustness_check",
        keywords=("robustness checks", "robustness check", "stress tests", "stress test"),
        confidence=0.78,
        rationale="The paper text reports robustness checks or stress tests.",
    ),
    Rule(
        label_type="evidence_type",
        label="theoretical_analysis",
        keywords=("finite-sample bounds", "theoretical", "theorem", "asymptotic", "analyzed asymptotically"),
        confidence=0.86,
        rationale="The evidence is primarily theoretical or asymptotic analysis.",
    ),
    Rule(
        label_type="evidence_type",
        label="simulation",
        keywords=("simulation", "simulations", "simulated", "toy lattice"),
        confidence=0.78,
        rationale="The paper text reports simulated evaluations.",
    ),
    Rule(
        label_type="caveat_class",
        label="simulation_realism",
        keywords=("simulated", "synthetic", "toy systems", "real workflows", "real research workflows"),
        confidence=0.76,
        rationale="Stored caveats or metadata question whether simulations or synthetic tasks transfer to reality.",
    ),
    Rule(
        label_type="caveat_class",
        label="evaluation_design_sensitivity",
        keywords=("evaluator", "rubric", "scenario design", "judgments may reward", "measured win rate"),
        confidence=0.82,
        rationale="Stored caveats point to evaluator, rubric, or scenario-design sensitivity.",
    ),
    Rule(
        label_type="caveat_class",
        label="prompt_sensitivity",
        keywords=("prompt formatting", "prompt families", "prompts", "prompt-family"),
        confidence=0.78,
        rationale="Stored caveats or metadata mention prompt sensitivity.",
    ),
    Rule(
        label_type="caveat_class",
        label="domain_shift",
        keywords=("distribution shift", "domain", "external validation", "clinical", "medical-imaging"),
        confidence=0.78,
        rationale="Stored caveats point to domain shift or external-validity risk.",
    ),
    Rule(
        label_type="caveat_class",
        label="hidden_assumption_cost",
        keywords=("oracle assumptions", "state preparation", "hidden costs", "pretraining data"),
        confidence=0.82,
        rationale="Stored caveats point to assumptions that may hide practical costs.",
    ),
    Rule(
        label_type="caveat_class",
        label="systems_overhead",
        keywords=("overhead", "latency", "real-time", "compute cost"),
        confidence=0.74,
        rationale="Stored caveats point to runtime, latency, or compute overhead.",
    ),
    Rule(
        label_type="caveat_class",
        label="data_leakage",
        keywords=("leak", "near-duplicate", "train/test overlap", "overlap"),
        confidence=0.78,
        rationale="Stored caveats point to data leakage or split contamination.",
    ),
    Rule(
        label_type="caveat_class",
        label="specialization_tradeoff",
        keywords=("generic visual tasks", "specialization", "capability is lost", "tradeoff"),
        confidence=0.74,
        rationale="Stored caveats point to a specialization tradeoff.",
    ),
    Rule(
        label_type="task",
        label="long_horizon_agent_workflows",
        keywords=("long-horizon", "research workflows", "tool failure", "multi-step model behavior"),
        confidence=0.86,
        rationale="The paper task is long-horizon agent workflow completion.",
    ),
    Rule(
        label_type="task",
        label="multi_step_reasoning",
        keywords=("multi-step reasoning", "reasoning prompts", "reasoning-style prompts"),
        confidence=0.82,
        rationale="The paper task involves multi-step reasoning behavior.",
    ),
    Rule(
        label_type="task",
        label="clarification_detection",
        keywords=("underspecified questions", "ask for clarification", "admit confusion", "clarification behavior"),
        confidence=0.9,
        rationale="The paper task is detecting underspecified requests and asking clarifying questions.",
    ),
    Rule(
        label_type="task",
        label="low_label_vision_adaptation",
        keywords=("low-label", "labels are scarce", "visual classifiers", "fine-grained recognition"),
        confidence=0.86,
        rationale="The paper task is vision adaptation with scarce labels.",
    ),
    Rule(
        label_type="task",
        label="preference_optimization_under_noise",
        keywords=("preference optimization", "noisy comparisons", "annotator noise", "pairwise comparisons"),
        confidence=0.88,
        rationale="The paper task is preference optimization under noisy comparisons.",
    ),
    Rule(
        label_type="task",
        label="quantum_error_correction_decoding",
        keywords=("quantum error correction", "syndrome", "surface-code", "decoder"),
        confidence=0.88,
        rationale="The paper task is quantum error-correction decoding.",
    ),
    Rule(
        label_type="task",
        label="sparse_hamiltonian_simulation",
        keywords=("sparse hamiltonian simulation", "hamiltonian simulation", "sparse matrix"),
        confidence=0.88,
        rationale="The paper task is sparse Hamiltonian simulation.",
    ),
    Rule(
        label_type="task",
        label="figure_question_answering",
        keywords=("figure question answering", "figure qa"),
        confidence=0.86,
        rationale="The paper evaluates figure question answering.",
    ),
    Rule(
        label_type="task",
        label="caption_grounding",
        keywords=("caption grounding", "captions"),
        confidence=0.82,
        rationale="The paper evaluates caption grounding.",
    ),
    Rule(
        label_type="task",
        label="cross_modal_search",
        keywords=("cross-modal search", "cross modal search"),
        confidence=0.84,
        rationale="The paper evaluates cross-modal search.",
    ),
    Rule(
        label_type="dataset_or_benchmark",
        label="simulated_research_workflows",
        keywords=("simulated research workflows", "research workflows"),
        confidence=0.82,
        rationale="The paper text names simulated research workflows as an evaluation setting.",
    ),
    Rule(
        label_type="dataset_or_benchmark",
        label="underspecified_questions_benchmark",
        keywords=("underspecified questions", "underspecified prompts", "admit confusion"),
        confidence=0.9,
        rationale="The paper text names an underspecified-question benchmark or dataset.",
    ),
    Rule(
        label_type="dataset_or_benchmark",
        label="prompt_family_robustness_checks",
        keywords=("prompt-family robustness", "prompt families", "robustness checks across prompt"),
        confidence=0.78,
        rationale="The paper text names prompt-family robustness checks.",
    ),
    Rule(
        label_type="dataset_or_benchmark",
        label="medical_imaging_like_benchmarks",
        keywords=("medical-imaging-like benchmarks", "medical imaging like benchmarks"),
        confidence=0.82,
        rationale="The paper text names medical-imaging-like benchmarks.",
    ),
    Rule(
        label_type="dataset_or_benchmark",
        label="fine_grained_recognition",
        keywords=("fine-grained recognition", "fine grained recognition"),
        confidence=0.78,
        rationale="The paper text names fine-grained recognition as an evaluation setting.",
    ),
    Rule(
        label_type="dataset_or_benchmark",
        label="synthetic_experiments",
        keywords=("synthetic experiments", "synthetic controls"),
        confidence=0.74,
        rationale="The paper text names synthetic experiments or controls.",
    ),
    Rule(
        label_type="dataset_or_benchmark",
        label="surface_code_simulations",
        keywords=("surface-code simulations", "surface code simulations", "code distances"),
        confidence=0.84,
        rationale="The paper text names surface-code simulations.",
    ),
    Rule(
        label_type="dataset_or_benchmark",
        label="toy_lattice_systems",
        keywords=("toy lattice systems", "toy lattice-system"),
        confidence=0.76,
        rationale="The paper text names toy lattice systems.",
    ),
    Rule(
        label_type="dataset_or_benchmark",
        label="scientific_figures_captions_text",
        keywords=("scientific figures", "captions", "scientific material"),
        confidence=0.8,
        rationale="The paper text names scientific figures, captions, and text as data.",
    ),
    Rule(
        label_type="architecture_primitive",
        label="language_model",
        keywords=("language model", "language models", "frontier and open models", "instruction-tuned"),
        confidence=0.8,
        rationale="The paper text references language models as the studied architecture family.",
    ),
    Rule(
        label_type="architecture_primitive",
        label="transformer",
        keywords=("transformer", "transformers", "instruction-tuned transformers"),
        confidence=0.86,
        rationale="The paper text references transformer architectures.",
    ),
    Rule(
        label_type="architecture_primitive",
        label="diffusion_model",
        keywords=("diffusion prior", "diffusion model"),
        confidence=0.86,
        rationale="The paper text references diffusion models or priors.",
    ),
    Rule(
        label_type="architecture_primitive",
        label="classifier",
        keywords=("classifier", "classifiers", "visual classifiers"),
        confidence=0.76,
        rationale="The paper text references classifier architectures.",
    ),
    Rule(
        label_type="architecture_primitive",
        label="retrieval_module",
        keywords=("retrieval", "retrieval-calibrated", "hard negative retrieval"),
        confidence=0.82,
        rationale="The paper text references retrieval as a model primitive.",
    ),
    Rule(
        label_type="architecture_primitive",
        label="multimodal_encoder",
        keywords=("multimodal", "figure/text pairs", "cross-modal"),
        confidence=0.82,
        rationale="The paper text references multimodal architecture primitives.",
    ),
    Rule(
        label_type="architecture_primitive",
        label="surface_code",
        keywords=("surface-code", "surface code"),
        confidence=0.84,
        rationale="The paper text references surface-code primitives.",
    ),
    Rule(
        label_type="architecture_primitive",
        label="block_encoding",
        keywords=("block-encoding", "block encoding"),
        confidence=0.88,
        rationale="The paper text references block encoding.",
    ),
    Rule(
        label_type="architecture_primitive",
        label="oracle_access",
        keywords=("oracle access", "oracles"),
        confidence=0.8,
        rationale="The paper text references oracle access.",
    ),
    Rule(
        label_type="architecture_primitive",
        label="tool_using_agent_loop",
        keywords=("tool selection", "state tracking", "structured notebook", "critic"),
        confidence=0.82,
        rationale="The paper text references a tool-using agent loop.",
    ),
    Rule(
        label_type="architecture_primitive",
        label="reward_model",
        keywords=("reward modeling", "reward-modeling", "direct preference objectives"),
        confidence=0.78,
        rationale="The paper text references reward-modeling primitives.",
    ),
    Rule(
        label_type="probe_family",
        label="activation_patching",
        keywords=("activation patching", "patch activations", "patching notebooks"),
        confidence=0.9,
        rationale="The paper text names activation patching as a probe.",
    ),
    Rule(
        label_type="probe_family",
        label="causal_intervention",
        keywords=("causal intervention", "causal interventions"),
        confidence=0.88,
        rationale="The paper text names causal interventions as probes.",
    ),
    Rule(
        label_type="probe_family",
        label="ablation",
        keywords=("ablation", "ablations"),
        confidence=0.82,
        rationale="The paper text names ablations as probes.",
    ),
    Rule(
        label_type="probe_family",
        label="stress_test",
        keywords=("stress test", "stress tests", "tool-failure stress"),
        confidence=0.78,
        rationale="The paper text names stress tests as probes.",
    ),
    Rule(
        label_type="probe_family",
        label="robustness_check",
        keywords=("robustness check", "robustness checks"),
        confidence=0.78,
        rationale="The paper text names robustness checks as probes.",
    ),
    Rule(
        label_type="probe_family",
        label="ambiguity_probe",
        keywords=("underspecified", "clarification", "ambiguous requests", "admit confusion"),
        confidence=0.88,
        rationale="The paper text probes ambiguity handling or clarification behavior.",
    ),
    Rule(
        label_type="probe_family",
        label="calibration_probe",
        keywords=("calibrated uncertainty", "uncertainty estimates", "confidence", "calibration"),
        confidence=0.76,
        rationale="The paper text probes calibration or uncertainty behavior.",
    ),
    Rule(
        label_type="probe_family",
        label="synthetic_control",
        keywords=("synthetic controls", "negative controls"),
        confidence=0.78,
        rationale="The paper text names synthetic or negative controls.",
    ),
)

CATEGORY_TASK_FALLBACKS = {
    "cs.ai": "artificial_intelligence_systems",
    "cs.cl": "language_model_evaluation",
    "cs.cv": "computer_vision",
    "cs.lg": "machine_learning",
    "quant-ph": "quantum_information",
    "stat.ml": "statistical_machine_learning",
}

NOVELTY_METHOD_FALLBACKS = {
    "method": "method_proposal",
    "benchmark": "benchmarking",
    "dataset": "dataset_contribution",
    "theory": "theoretical_method",
    "systems": "systems_method",
    "empirical": "empirical_study",
    "application": "application_study",
    "survey": "survey",
    "other": "other_method_family",
}

NOVELTY_EVIDENCE_FALLBACKS = {
    "benchmark": "benchmark_evaluation",
    "dataset": "dataset_release",
    "theory": "theoretical_analysis",
    "empirical": "empirical_evaluation",
    "survey": "literature_synthesis",
}


def extract_classifications(paper: Paper) -> list[ClassificationCandidate]:
    text = _combined_text(paper)
    normalized_text = _normalize_text(text)
    candidates: list[ClassificationCandidate] = []

    for rule in RULES:
        matches = _matched_keywords(normalized_text, rule.keywords)
        if not matches:
            continue
        candidates.append(
            ClassificationCandidate(
                label_type=rule.label_type,
                label=rule.label,
                confidence=rule.confidence,
                rationale=f"{rule.rationale} Matched: {', '.join(matches[:4])}.",
            )
        )

    candidates.extend(_fallback_candidates(paper, candidates))
    return _dedupe_candidates(candidates)


def classify_paper(db: Session, paper: Paper) -> list[PaperClassification]:
    candidates = extract_classifications(paper)
    generated_keys = {(candidate.label_type, candidate.label) for candidate in candidates}
    existing = db.query(PaperClassification).filter(PaperClassification.paper_id == paper.id).all()
    existing_by_key = {(classification.label_type, classification.label): classification for classification in existing}

    for candidate in candidates:
        row = existing_by_key.get((candidate.label_type, candidate.label))
        if row is None:
            db.add(
                PaperClassification(
                    paper_id=paper.id,
                    label_type=candidate.label_type,
                    label=candidate.label,
                    confidence=candidate.confidence,
                    source=CLASSIFICATION_SOURCE,
                    rationale=candidate.rationale,
                )
            )
            continue
        if row.source == CLASSIFICATION_SOURCE:
            _update_classification_if_changed(row, candidate)

    for row in existing:
        if row.source == CLASSIFICATION_SOURCE and (row.label_type, row.label) not in generated_keys:
            db.delete(row)

    db.commit()
    return list_paper_classifications(db, paper)


def list_paper_classifications(db: Session, paper: Paper) -> list[PaperClassification]:
    rows = db.query(PaperClassification).filter(PaperClassification.paper_id == paper.id).all()
    return sorted(rows, key=_classification_sort_key)


def _fallback_candidates(
    paper: Paper, existing_candidates: list[ClassificationCandidate]
) -> list[ClassificationCandidate]:
    candidates: list[ClassificationCandidate] = []
    existing_types = {candidate.label_type for candidate in existing_candidates}
    breakdown = paper.breakdown

    if breakdown is not None and "method_family" not in existing_types:
        label = NOVELTY_METHOD_FALLBACKS.get(breakdown.novelty_type, "other_method_family")
        candidates.append(
            ClassificationCandidate(
                label_type="method_family",
                label=label,
                confidence=0.52,
                rationale=f"Fallback from stored PaperBreakdown novelty_type={breakdown.novelty_type}.",
            )
        )

    if breakdown is not None and "evidence_type" not in existing_types:
        label = NOVELTY_EVIDENCE_FALLBACKS.get(breakdown.novelty_type, "abstract_claim")
        candidates.append(
            ClassificationCandidate(
                label_type="evidence_type",
                label=label,
                confidence=0.48,
                rationale=f"Fallback from stored PaperBreakdown novelty_type={breakdown.novelty_type}.",
            )
        )

    if (
        breakdown is not None
        and "caveat_class" not in existing_types
        and _json_list(breakdown.methodology_caveats_json)
    ):
        candidates.append(
            ClassificationCandidate(
                label_type="caveat_class",
                label="reported_methodology_caveat",
                confidence=0.46,
                rationale="Fallback from the presence of stored methodology caveats.",
            )
        )

    if "task" not in existing_types:
        category_labels = _category_task_labels(paper)
        if category_labels:
            candidates.append(
                ClassificationCandidate(
                    label_type="task",
                    label=category_labels[0],
                    confidence=0.42,
                    rationale=f"Fallback from paper category {paper.primary_category}.",
                )
            )

    return candidates


def _dedupe_candidates(candidates: list[ClassificationCandidate]) -> list[ClassificationCandidate]:
    best_by_key: dict[tuple[str, str], ClassificationCandidate] = {}
    for candidate in candidates:
        if candidate.label_type not in LABEL_TYPE_INDEX:
            continue
        label = _to_label(candidate.label)
        key = (candidate.label_type, label)
        normalized = ClassificationCandidate(
            label_type=candidate.label_type,
            label=label,
            confidence=round(max(0.0, min(candidate.confidence, 1.0)), 3),
            rationale=candidate.rationale.strip(),
        )
        current = best_by_key.get(key)
        if current is None or normalized.confidence > current.confidence:
            best_by_key[key] = normalized
    return sorted(best_by_key.values(), key=lambda candidate: _candidate_sort_key(candidate))


def _update_classification_if_changed(row: PaperClassification, candidate: ClassificationCandidate) -> None:
    if (
        round(row.confidence or 0.0, 3) == candidate.confidence
        and row.rationale == candidate.rationale
        and row.source == CLASSIFICATION_SOURCE
    ):
        return
    row.confidence = candidate.confidence
    row.rationale = candidate.rationale
    row.source = CLASSIFICATION_SOURCE
    row.updated_at = datetime.now(UTC)


def _combined_text(paper: Paper) -> str:
    pieces = [
        paper.title,
        paper.abstract,
        paper.primary_category,
        " ".join(str(category) for category in _json_list(paper.categories_json)),
        paper.raw_metadata_json,
    ]
    breakdown = paper.breakdown
    if breakdown is not None:
        pieces.extend(
            [
                breakdown.one_line_takeaway,
                breakdown.simple_summary,
                breakdown.context,
                breakdown.what_is_new,
                breakdown.mechanism,
                breakdown.evidence,
                breakdown.novelty_type,
                breakdown.difficulty,
                breakdown.confidence,
                breakdown.read_this_if,
                breakdown.vibe,
                breakdown.source_basis,
            ]
        )
        for raw_json in [
            breakdown.methodology_caveats_json,
            breakdown.meaningful_extensions_json,
            breakdown.tags_json,
            breakdown.glossary_json,
            breakdown.follow_up_questions_json,
        ]:
            pieces.extend(_stringify_json_item(item) for item in _json_list(raw_json))
    return " ".join(piece for piece in pieces if piece)


def _category_task_labels(paper: Paper) -> list[str]:
    categories = [paper.primary_category, *[str(category) for category in _json_list(paper.categories_json)]]
    labels: list[str] = []
    for category in categories:
        label = CATEGORY_TASK_FALLBACKS.get(category.lower())
        if label and label not in labels:
            labels.append(label)
    return labels


def _matched_keywords(normalized_text: str, keywords: tuple[str, ...]) -> list[str]:
    matches: list[str] = []
    for keyword in keywords:
        normalized_keyword = _normalize_text(keyword)
        if normalized_keyword and normalized_keyword in normalized_text:
            matches.append(keyword)
    return matches


def _normalize_text(value: str) -> str:
    lowered = value.lower()
    cleaned = re.sub(r"[^a-z0-9.]+", " ", lowered)
    return " ".join(cleaned.split())


def _to_label(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return cleaned or "unknown"


def _json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _stringify_json_item(item: object) -> str:
    if isinstance(item, dict):
        return " ".join(str(value) for value in item.values())
    return str(item)


def _candidate_sort_key(candidate: ClassificationCandidate) -> tuple[int, str]:
    return (LABEL_TYPE_INDEX.get(candidate.label_type, len(LABEL_TYPES)), candidate.label)


def _classification_sort_key(classification: PaperClassification) -> tuple[int, str]:
    return (LABEL_TYPE_INDEX.get(classification.label_type, len(LABEL_TYPES)), classification.label)
