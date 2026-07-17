from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from evidence_audit import audit_synthesis_source_refs
from models import Paper
from settings import Settings
from summarizer import estimate_cost_usd

MAX_SYNTHESIS_PAPERS = 8
SYNTHESIS_PROMPT_VERSION = "synthesis-workbench-deterministic-v1"
SYNTHESIS_PROVIDER_PROMPT_VERSION = "synthesis-workbench-provider-v1"
SYNTHESIS_TASK = "synthesis"
SYNTHESIS_MODEL_PROVIDER = "none"
SYNTHESIS_MODEL_NAME = "metadata-breakdown-heuristic-v1"
SYNTHESIS_PROVIDER_PROMPT = """You are a careful research synthesis editor.

Create a structured synthesis over the selected papers only.
Return only JSON with these array fields:
argument_map, contradictions, evidence_matrix, open_questions, extension_ideas,
replication_or_ablation_plan, caveats.

Rules:
- Every non-speculative item must include source_paper_ids using only the selected paper ids.
- Speculative ideas must include speculative: true and cautious wording.
- Do not invent paper claims, metrics, datasets, or results.
- Use the user's instructions as emphasis, not permission to ignore source discipline.
- Keep each section independently renderable as a list of objects.
"""


class SynthesisValidationError(ValueError):
    pass


class ProviderSynthesisOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    argument_map: list[dict[str, object]] = Field(min_length=1)
    contradictions: list[dict[str, object]] = Field(min_length=1)
    evidence_matrix: list[dict[str, object]] = Field(min_length=1)
    open_questions: list[dict[str, object]] = Field(min_length=1)
    extension_ideas: list[dict[str, object]] = Field(min_length=1)
    replication_or_ablation_plan: list[dict[str, object]] = Field(min_length=1)
    caveats: list[dict[str, object]] = Field(min_length=1)


ProviderSynthesisGenerator = Callable[[list[Paper], str, str | None, Settings], dict[str, object]]


def build_synthesis(
    papers: list[Paper],
    mode: str,
    instructions: str | None,
    settings: Settings,
    provider_generate: ProviderSynthesisGenerator | None = None,
) -> dict[str, object]:
    deterministic = build_deterministic_synthesis(papers=papers, mode=mode)
    if not _synthesis_provider_configured(settings):
        return deterministic

    provider, model_name = _synthesis_provider_identity(settings)
    raw: object | None = None
    try:
        raw = (
            provider_generate(papers, mode, instructions, settings)
            if provider_generate is not None
            else _generate_provider_synthesis(papers, mode, instructions, settings)
        )
        return prepare_provider_synthesis_output(
            raw=raw,
            fallback=deterministic,
            provider=provider,
            model_name=model_name,
        )
    except Exception as exc:
        fallback = dict(deterministic)
        fallback["model_provider"] = SYNTHESIS_MODEL_PROVIDER
        fallback["model_name"] = SYNTHESIS_MODEL_NAME
        fallback["_synthesis_validation_status"] = "fallback"
        fallback["_synthesis_validation_error"] = _compact_error(exc)
        usage = _usage_metadata(raw)
        if usage:
            fallback["_llm_usage"] = usage
        return fallback


def prepare_provider_synthesis_output(
    raw: object,
    fallback: dict[str, object],
    provider: str,
    model_name: str,
) -> dict[str, object]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SynthesisValidationError(_compact_error(exc)) from exc
    if not isinstance(raw, dict):
        raise SynthesisValidationError(f"Expected synthesis JSON object, got {type(raw).__name__}")

    try:
        output = ProviderSynthesisOutput.model_validate(_without_private_keys(raw))
    except ValidationError as exc:
        raise SynthesisValidationError(_compact_error(exc)) from exc

    source_paper_ids = [int(item) for item in fallback["source_paper_ids"]]
    data = output.model_dump()
    issues = audit_synthesis_source_refs(data, source_paper_ids)
    if issues:
        raise SynthesisValidationError("; ".join(issues))
    data["source_paper_ids"] = source_paper_ids
    data["prompt_version"] = SYNTHESIS_PROVIDER_PROMPT_VERSION
    data["model_provider"] = provider
    data["model_name"] = model_name
    data["_synthesis_validation_status"] = "valid"
    usage = _usage_metadata(raw)
    if usage:
        data["_llm_usage"] = usage
    return data


def build_deterministic_synthesis(papers: list[Paper], mode: str) -> dict[str, object]:
    profiles = [_paper_profile(paper) for paper in papers]
    source_paper_ids = [int(profile["paper_id"]) for profile in profiles]
    return {
        "argument_map": _argument_map(profiles, mode),
        "contradictions": _contradictions(profiles),
        "evidence_matrix": _evidence_matrix(profiles),
        "open_questions": _open_questions(profiles),
        "extension_ideas": _extension_ideas(profiles),
        "replication_or_ablation_plan": _replication_or_ablation_plan(profiles),
        "caveats": _caveats(profiles),
        "source_paper_ids": source_paper_ids,
        "prompt_version": SYNTHESIS_PROMPT_VERSION,
        "model_provider": SYNTHESIS_MODEL_PROVIDER,
        "model_name": SYNTHESIS_MODEL_NAME,
    }


def _generate_provider_synthesis(
    papers: list[Paper],
    mode: str,
    instructions: str | None,
    settings: Settings,
) -> dict[str, object]:
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return _generate_openai_synthesis(papers, mode, instructions, settings)
    if settings.llm_provider == "zai" and settings.zai_api_key:
        return _generate_zai_synthesis(papers, mode, instructions, settings)
    raise RuntimeError(f"Provider-backed synthesis is not configured for {settings.llm_provider}.")


def _generate_openai_synthesis(
    papers: list[Paper],
    mode: str,
    instructions: str | None,
    settings: Settings,
) -> dict[str, object]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The openai package is not installed.") from exc

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.responses.create(
        model=settings.openai_model,
        input=f"{SYNTHESIS_PROVIDER_PROMPT}\n\nSynthesis input JSON:\n{json.dumps(_provider_payload(papers, mode, instructions), default=str)}",
    )
    data = json.loads(getattr(response, "output_text", ""))
    data["_llm_usage"] = _usage_from_responses_api(response, "openai", settings.openai_model)
    return data


def _generate_zai_synthesis(
    papers: list[Paper],
    mode: str,
    instructions: str | None,
    settings: Settings,
) -> dict[str, object]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The openai package is not installed.") from exc

    client = OpenAI(api_key=settings.zai_api_key, base_url=settings.zai_base_url.rstrip("/"))
    response = client.chat.completions.create(
        model=settings.zai_synthesis_model,
        messages=[
            {"role": "system", "content": SYNTHESIS_PROVIDER_PROMPT},
            {
                "role": "user",
                "content": f"Synthesis input JSON:\n{json.dumps(_provider_payload(papers, mode, instructions), default=str)}",
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    data = json.loads(response.choices[0].message.content or "{}")
    data["_llm_usage"] = _usage_from_chat_completion(
        response=response,
        provider="zai",
        model_name=settings.zai_synthesis_model,
        input_price_per_m=settings.zai_synthesis_input_price_per_m,
        output_price_per_m=settings.zai_synthesis_output_price_per_m,
    )
    return data


def _paper_profile(paper: Paper) -> dict[str, object]:
    breakdown = paper.breakdown
    categories = [str(category) for category in _json_list(paper.categories_json)] or [paper.primary_category]
    if breakdown is None:
        return {
            "paper_id": paper.id,
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "categories": categories,
            "primary_category": paper.primary_category,
            "claim": _clip(paper.abstract),
            "mechanism": "No stored paper breakdown is available; this is based on metadata and abstract text.",
            "evidence": "No stored evidence summary is available; inspect the paper before relying on this claim.",
            "methodology_caveats": ["No stored methodology caveats are available for this paper."],
            "meaningful_extensions": [
                "Create a paper breakdown, then run a closer synthesis pass against the extracted caveats."
            ],
            "novelty_type": "other",
            "confidence": "low",
            "tags": categories,
            "follow_up_questions": ["What evidence in the full paper most changes the abstract-level claim?"],
            "source_basis": "metadata_only",
        }

    methodology_caveats = [str(item) for item in _json_list(breakdown.methodology_caveats_json)]
    meaningful_extensions = [str(item) for item in _json_list(breakdown.meaningful_extensions_json)]
    tags = [str(item) for item in _json_list(breakdown.tags_json)]
    follow_up_questions = [str(item) for item in _json_list(breakdown.follow_up_questions_json)]
    return {
        "paper_id": paper.id,
        "arxiv_id": paper.arxiv_id,
        "title": paper.title,
        "categories": categories,
        "primary_category": paper.primary_category,
        "claim": breakdown.one_line_takeaway,
        "mechanism": breakdown.mechanism,
        "evidence": breakdown.evidence,
        "methodology_caveats": methodology_caveats,
        "meaningful_extensions": meaningful_extensions,
        "novelty_type": breakdown.novelty_type,
        "confidence": breakdown.confidence,
        "tags": tags,
        "follow_up_questions": follow_up_questions,
        "source_basis": breakdown.source_basis,
    }


def _provider_payload(papers: list[Paper], mode: str, instructions: str | None) -> dict[str, object]:
    return {
        "mode": mode,
        "instructions": instructions,
        "selected_papers": [_paper_profile(paper) for paper in papers],
    }


def _argument_map(profiles: list[dict[str, object]], mode: str) -> list[dict[str, object]]:
    source_paper_ids = [int(profile["paper_id"]) for profile in profiles]
    entries = [
        {
            "role": "paper_claim",
            "paper_id": profile["paper_id"],
            "arxiv_id": profile["arxiv_id"],
            "title": profile["title"],
            "source_paper_ids": [profile["paper_id"]],
            "claim": profile["claim"],
            "mechanism": profile["mechanism"],
            "evidence": profile["evidence"],
            "primary_caveat": _first(profile["methodology_caveats"]),
        }
        for profile in profiles
    ]
    entries.append(
        {
            "role": "cross_paper_synthesis",
            "source_paper_ids": source_paper_ids,
            "claim": _cross_paper_claim(profiles, mode),
            "shared_categories": _shared_categories(profiles),
            "shared_tags": _shared_tags(profiles),
            "basis": "Deterministic synthesis over stored paper metadata and paper_breakdowns.",
        }
    )
    return entries


def _contradictions(profiles: list[dict[str, object]]) -> list[dict[str, object]]:
    source_paper_ids = [int(profile["paper_id"]) for profile in profiles]
    novelty_types = sorted({str(profile["novelty_type"]) for profile in profiles})
    confidence_levels = sorted({str(profile["confidence"]) for profile in profiles})
    checks = [
        f"Check whether {profile['arxiv_id']} caveats weaken claims reused from adjacent selected papers."
        for profile in profiles
    ]
    return [
        {
            "status": "not_detected",
            "source_paper_ids": source_paper_ids,
            "note": (
                "No explicit contradiction is asserted by the stored summaries. Treat this as a triage note, "
                "not as proof that the papers are mutually consistent."
            ),
            "novelty_types": novelty_types,
            "confidence_levels": confidence_levels,
            "checks": checks,
        }
    ]


def _evidence_matrix(profiles: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "paper_id": profile["paper_id"],
            "arxiv_id": profile["arxiv_id"],
            "title": profile["title"],
            "source_paper_ids": [profile["paper_id"]],
            "evidence": profile["evidence"],
            "methodology_caveats": profile["methodology_caveats"],
            "meaningful_extensions": profile["meaningful_extensions"],
            "source_basis": profile["source_basis"],
            "confidence": profile["confidence"],
        }
        for profile in profiles
    ]


def _open_questions(profiles: list[dict[str, object]]) -> list[dict[str, object]]:
    questions: list[dict[str, object]] = []
    for profile in profiles:
        follow_ups = list(profile["follow_up_questions"])
        for question in follow_ups[:2]:
            questions.append(
                {
                    "source_paper_ids": [profile["paper_id"]],
                    "arxiv_id": profile["arxiv_id"],
                    "question": question,
                }
            )
    questions.append(
        {
            "source_paper_ids": [int(profile["paper_id"]) for profile in profiles],
            "arxiv_id": None,
            "question": "Which caveat, if resolved, would most improve confidence across the selected papers?",
        }
    )
    return questions


def _extension_ideas(profiles: list[dict[str, object]]) -> list[dict[str, object]]:
    ideas: list[dict[str, object]] = []
    for profile in profiles:
        for idea in list(profile["meaningful_extensions"])[:2]:
            ideas.append(
                {
                    "source_paper_ids": [profile["paper_id"]],
                    "arxiv_id": profile["arxiv_id"],
                    "idea": idea,
                }
            )
    return ideas


def _replication_or_ablation_plan(profiles: list[dict[str, object]]) -> list[dict[str, object]]:
    plan: list[dict[str, object]] = []
    for index, profile in enumerate(profiles, start=1):
        extension = _first(profile["meaningful_extensions"])
        caveat = _first(profile["methodology_caveats"])
        plan.append(
            {
                "step": index,
                "source_paper_ids": [profile["paper_id"]],
                "arxiv_id": profile["arxiv_id"],
                "action": f"Replicate or ablate the core claim in {profile['title']}: {extension}",
                "watch_for": caveat,
            }
        )
    return plan


def _caveats(profiles: list[dict[str, object]]) -> list[dict[str, object]]:
    caveats: list[dict[str, object]] = []
    for profile in profiles:
        for caveat in list(profile["methodology_caveats"])[:2]:
            caveats.append(
                {
                    "source_paper_ids": [profile["paper_id"]],
                    "arxiv_id": profile["arxiv_id"],
                    "caveat": caveat,
                }
            )
    caveats.append(
        {
            "source_paper_ids": [int(profile["paper_id"]) for profile in profiles],
            "arxiv_id": None,
            "caveat": (
                "This deterministic pass only uses stored metadata and paper_breakdowns; it does not read full papers "
                "or call an LLM provider."
            ),
        }
    )
    return caveats


def _cross_paper_claim(profiles: list[dict[str, object]], mode: str) -> str:
    titles = "; ".join(str(profile["title"]) for profile in profiles)
    shared_categories = _shared_categories(profiles)
    shared_tags = _shared_tags(profiles)
    if mode == "compare":
        return f"Compare the selected papers by evidence strength, caveats, and extension paths: {titles}."
    if mode == "argument_map":
        return f"Use each paper as a sourced claim node, then test cross-paper support and caveats: {titles}."
    if mode == "research_plan":
        return f"Build a follow-up plan around replications and ablations grounded in these papers: {titles}."
    if shared_categories:
        return f"The selected papers share categories {', '.join(shared_categories)} and can be read as one cluster."
    if shared_tags:
        return f"The selected papers share tags {', '.join(shared_tags)} and can seed a combined research note."
    return f"The selected papers can be synthesized as a cross-paper research note: {titles}."


def _shared_categories(profiles: list[dict[str, object]]) -> list[str]:
    category_sets = [set(str(category) for category in profile["categories"]) for profile in profiles]
    if not category_sets:
        return []
    return sorted(set.intersection(*category_sets))


def _shared_tags(profiles: list[dict[str, object]]) -> list[str]:
    tag_counts = Counter(tag for profile in profiles for tag in profile["tags"])
    return sorted(str(tag) for tag, count in tag_counts.items() if count > 1)


def _first(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "No stored item is available."
    return str(items[0])


def _clip(value: str, limit: int = 280) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3].rstrip()}..."


def _json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _synthesis_provider_configured(settings: Settings) -> bool:
    if settings.llm_provider == "openai":
        return bool(settings.openai_api_key)
    if settings.llm_provider == "zai":
        return bool(settings.zai_api_key)
    return False


def _synthesis_provider_identity(settings: Settings) -> tuple[str, str]:
    if settings.llm_provider == "zai":
        return "zai", settings.zai_synthesis_model
    if settings.llm_provider == "openai":
        return "openai", settings.openai_model
    return settings.llm_provider, "unknown"


def _without_private_keys(data: dict) -> dict:
    return {key: value for key, value in data.items() if not str(key).startswith("_")}


def _usage_metadata(raw: object) -> dict:
    if not isinstance(raw, dict):
        return {}
    usage = raw.get("_llm_usage")
    return usage if isinstance(usage, dict) else {}


def _usage_from_responses_api(response: object, provider: str, model_name: str) -> dict:
    usage = getattr(response, "usage", None)
    prompt_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
    completion_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
    total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0) if usage else 0
    return {
        "provider": provider,
        "model_name": model_name,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": 0.0,
    }


def _usage_from_chat_completion(
    response: object,
    provider: str,
    model_name: str,
    input_price_per_m: float,
    output_price_per_m: float,
) -> dict:
    usage = getattr(response, "usage", None)
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
    total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0) if usage else 0
    return {
        "provider": provider,
        "model_name": model_name,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimate_cost_usd(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            input_price_per_m=input_price_per_m,
            output_price_per_m=output_price_per_m,
        ),
    }


def _compact_error(error: Exception) -> str:
    return str(error).replace("\n", " ")[:1000]
