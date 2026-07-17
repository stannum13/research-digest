from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from hashlib import sha256
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from arxiv_client import ArxivPaper
from settings import Settings

PAPER_SUMMARY_TASK = "paper_summary"
SUMMARY_PROMPT_VERSION = "paper-summary-v1"
SUMMARY_REPAIR_PROMPT_VERSION = "paper-summary-repair-v1"
SUMMARY_PROMPT = """You are a careful research editor for a daily arXiv digest.

Explain the paper in plain language without flattening technical content.
Use only the provided title, abstract, metadata, and extracted text.
Return only JSON matching this schema:
{
  "one_line_takeaway": string,
  "simple_summary": string,
  "context": string,
  "what_is_new": string,
  "mechanism": string,
  "evidence": string,
  "methodology_caveats": string[],
  "meaningful_extensions": string[],
  "novelty_type": "method" | "benchmark" | "dataset" | "theory" | "systems" | "empirical" | "application" | "survey" | "other",
  "difficulty": "beginner" | "intermediate" | "expert",
  "confidence": "low" | "medium" | "high",
  "read_this_if": string,
  "tags": string[],
  "vibe": string,
  "glossary": [{"term": string, "definition": string}],
  "follow_up_questions": string[]
}

Rules:
- Do not invent results.
- Caveats must be specific, not generic disclaimers.
- Extensions must be concrete follow-up experiments, ablations, replications, or probes.
- If only the abstract is available, keep claims cautious and use lower confidence.
"""
SUMMARY_REPAIR_PROMPT = """You repair malformed paper-summary JSON for a daily arXiv digest.

Use only the provided paper metadata, extracted text, validation error, and malformed provider output.
Return only corrected JSON matching the original summary schema.

Rules:
- Do not invent results, baselines, scores, or claims that are not supported by the provided paper text.
- Preserve cautious wording when source evidence is abstract-only or partial.
- Fill missing fields with conservative, source-grounded language.
- Keep arrays as arrays and enum fields within the allowed schema values.
- Do not include explanations outside the JSON object.
"""


class Summarizer(Protocol):
    provider: str
    model_name: str

    def summarize(self, paper: ArxivPaper, full_text: str = "") -> dict: ...


SummaryText = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]
NoveltyType = Literal[
    "method", "benchmark", "dataset", "theory", "systems", "empirical", "application", "survey", "other"
]
Difficulty = Literal["beginner", "intermediate", "expert"]
Confidence = Literal["low", "medium", "high"]
SourceBasis = Literal["abstract_only", "partial_full_text", "full_text"]


class SummaryValidationError(ValueError):
    pass


class SummaryGlossaryTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: SummaryText
    definition: SummaryText


class PaperSummaryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    one_line_takeaway: SummaryText
    simple_summary: SummaryText
    context: SummaryText
    what_is_new: SummaryText
    mechanism: SummaryText
    evidence: SummaryText
    methodology_caveats: list[SummaryText] = Field(min_length=1)
    meaningful_extensions: list[SummaryText] = Field(min_length=1)
    novelty_type: NoveltyType
    difficulty: Difficulty
    confidence: Confidence
    read_this_if: SummaryText
    tags: list[SummaryText] = Field(min_length=1)
    vibe: SummaryText
    glossary: list[SummaryGlossaryTerm]
    follow_up_questions: list[SummaryText] = Field(min_length=1)
    model_provider: SummaryText
    model_name: SummaryText
    source_basis: SourceBasis


@dataclass(frozen=True)
class PreparedSummary:
    data: dict
    cacheable: bool
    validation_status: str
    validation_error: str | None = None
    repair_attempted: bool = False
    repair_error: str | None = None


SummaryRepairCallback = Callable[[ArxivPaper, object, str, str], object]


@dataclass(frozen=True)
class UsageEstimate:
    provider: str
    model_name: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def as_metadata(self) -> dict:
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
        }


class MockSummarizer:
    provider = "mock"
    model_name = "deterministic-fallback"

    def summarize(self, paper: ArxivPaper, full_text: str = "") -> dict:
        topic = paper.primary_category
        source_basis = "partial_full_text" if full_text else "abstract_only"
        return {
            "one_line_takeaway": f"The authors claim a focused contribution in {topic}, but the evidence needs close reading.",
            "simple_summary": (
                "This generated fallback summary is intentionally cautious because no configured LLM produced "
                "a full editorial read. It preserves the title and abstract context without inventing results."
            ),
            "context": "The paper sits inside the current arXiv stream for AI, machine learning, or quantum research.",
            "what_is_new": "The apparent novelty is inferred from the abstract language and should be verified in the paper.",
            "mechanism": "The mechanism is not expanded beyond the abstract in fallback mode.",
            "evidence": "Evidence was not independently extracted; inspect the paper for experiments, proofs, or simulations.",
            "methodology_caveats": [
                "Fallback mode cannot verify whether baselines, ablations, or assumptions are strong.",
                "Claims are based on metadata and abstract text only.",
            ],
            "meaningful_extensions": [
                "Run a close reading focused on evaluation design and failure cases.",
                "Compare the claimed contribution against recent related work in the same category.",
            ],
            "novelty_type": "other",
            "difficulty": "intermediate",
            "confidence": "low",
            "read_this_if": "You want a candidate paper to inspect manually from the latest arXiv feed.",
            "tags": [paper.primary_category, "fallback-summary"],
            "vibe": "A penciled placeholder awaiting a proper editorial pass",
            "glossary": [
                {"term": "fallback summary", "definition": "A deterministic summary generated without an LLM read."}
            ],
            "follow_up_questions": [
                "What exact evidence supports the central claim?",
                "Which assumptions would break the method?",
            ],
            "model_provider": "mock",
            "model_name": "deterministic-fallback",
            "source_basis": source_basis,
            "_llm_usage": UsageEstimate(provider="mock", model_name="deterministic-fallback").as_metadata(),
        }


class OpenAISummarizer:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self.provider = "openai"
        self.model_name = model

    def summarize(self, paper: ArxivPaper, full_text: str = "") -> dict:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("The openai package is not installed.") from exc

        client = OpenAI(api_key=self.api_key)
        payload = {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "authors": paper.authors,
            "categories": paper.categories,
            "abstract": paper.abstract,
            "extracted_text": full_text,
        }
        response = client.responses.create(
            model=self.model,
            input=f"{SUMMARY_PROMPT}\n\nPaper JSON:\n{json.dumps(payload)}",
        )
        text = getattr(response, "output_text", "")
        data = json.loads(text)
        data["model_provider"] = "openai"
        data["model_name"] = self.model
        data.setdefault("source_basis", "partial_full_text" if full_text else "abstract_only")
        data["_llm_usage"] = _usage_from_responses_api(response, "openai", self.model).as_metadata()
        return data

    def repair_summary(
        self,
        paper: ArxivPaper,
        raw: object,
        validation_error: str,
        full_text: str = "",
    ) -> dict:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("The openai package is not installed.") from exc

        client = OpenAI(api_key=self.api_key)
        payload = _summary_repair_payload(
            paper=paper,
            full_text=full_text,
            raw=raw,
            validation_error=validation_error,
        )
        response = client.responses.create(
            model=self.model,
            input=f"{SUMMARY_REPAIR_PROMPT}\n\nRepair input JSON:\n{json.dumps(payload, default=str)}",
        )
        text = getattr(response, "output_text", "")
        data = json.loads(text)
        data["model_provider"] = "openai"
        data["model_name"] = self.model
        data.setdefault("source_basis", "partial_full_text" if full_text else "abstract_only")
        data["_llm_usage"] = _usage_from_responses_api(response, "openai", self.model).as_metadata()
        return data


class ZaiSummarizer:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        input_price_per_m: float,
        output_price_per_m: float,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider = "zai"
        self.model_name = model
        self.input_price_per_m = input_price_per_m
        self.output_price_per_m = output_price_per_m

    def summarize(self, paper: ArxivPaper, full_text: str = "") -> dict:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("The openai package is not installed.") from exc

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        payload = {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "authors": paper.authors,
            "categories": paper.categories,
            "primary_category": paper.primary_category,
            "abstract": paper.abstract,
            "extracted_text": full_text,
        }
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": f"Paper JSON:\n{json.dumps(payload)}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        data["model_provider"] = "zai"
        data["model_name"] = self.model
        data.setdefault("source_basis", "partial_full_text" if full_text else "abstract_only")
        data["_llm_usage"] = _usage_from_chat_completion(
            response=response,
            provider="zai",
            model_name=self.model,
            input_price_per_m=self.input_price_per_m,
            output_price_per_m=self.output_price_per_m,
        ).as_metadata()
        return data

    def repair_summary(
        self,
        paper: ArxivPaper,
        raw: object,
        validation_error: str,
        full_text: str = "",
    ) -> dict:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("The openai package is not installed.") from exc

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        payload = _summary_repair_payload(
            paper=paper,
            full_text=full_text,
            raw=raw,
            validation_error=validation_error,
        )
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SUMMARY_REPAIR_PROMPT},
                {"role": "user", "content": f"Repair input JSON:\n{json.dumps(payload, default=str)}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        data["model_provider"] = "zai"
        data["model_name"] = self.model
        data.setdefault("source_basis", "partial_full_text" if full_text else "abstract_only")
        data["_llm_usage"] = _usage_from_chat_completion(
            response=response,
            provider="zai",
            model_name=self.model,
            input_price_per_m=self.input_price_per_m,
            output_price_per_m=self.output_price_per_m,
        ).as_metadata()
        return data


def estimate_cost_usd(
    prompt_tokens: int,
    completion_tokens: int,
    input_price_per_m: float,
    output_price_per_m: float,
) -> float:
    return round(
        (prompt_tokens / 1_000_000 * input_price_per_m) + (completion_tokens / 1_000_000 * output_price_per_m), 6
    )


def paper_summary_content_hash(paper: ArxivPaper, full_text: str = "") -> str:
    payload = {
        "arxiv_id": paper.arxiv_id,
        "arxiv_version": paper.arxiv_version or "",
        "title": paper.title,
        "abstract": paper.abstract,
        "authors": paper.authors,
        "primary_category": paper.primary_category,
        "categories": paper.categories,
        "updated_at": paper.updated_at.isoformat(),
        "full_text": full_text,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def prepare_summary_output(
    raw: object,
    paper: ArxivPaper,
    full_text: str = "",
    repairer: SummaryRepairCallback | None = None,
) -> PreparedSummary:
    try:
        data = validate_summary_output(raw)
    except SummaryValidationError as exc:
        validation_error = _compact_validation_error(exc)
        repair_attempted = False
        repair_error = None
        repair_usage: dict = {}

        if repairer is not None:
            repair_attempted = True
            try:
                repaired_raw = repairer(paper, raw, validation_error, full_text)
                repair_usage = _usage_metadata(repaired_raw)
                data = validate_summary_output(repaired_raw)
            except Exception as repair_exc:
                repair_error = _compact_validation_error(repair_exc)
            else:
                usage = _combined_usage_metadata(_usage_metadata(raw), repair_usage)
                if usage:
                    data["_llm_usage"] = usage
                data["_summary_validation_status"] = "repaired"
                data["_summary_validation_error"] = validation_error
                data["_summary_repair_attempted"] = True
                data["_summary_repair_prompt_version"] = SUMMARY_REPAIR_PROMPT_VERSION
                return PreparedSummary(
                    data=data,
                    cacheable=True,
                    validation_status="repaired",
                    validation_error=validation_error,
                    repair_attempted=True,
                )

        fallback = MockSummarizer().summarize(paper, full_text)
        fallback.pop("_llm_usage", None)
        usage = _combined_usage_metadata(_usage_metadata(raw), repair_usage)
        if usage:
            fallback["_llm_usage"] = usage
        fallback["_summary_validation_status"] = "fallback"
        fallback["_summary_validation_error"] = validation_error
        fallback["_summary_repair_attempted"] = repair_attempted
        if repair_attempted:
            fallback["_summary_repair_prompt_version"] = SUMMARY_REPAIR_PROMPT_VERSION
        if repair_error:
            fallback["_summary_repair_error"] = repair_error
        return PreparedSummary(
            data=fallback,
            cacheable=False,
            validation_status="fallback",
            validation_error=fallback["_summary_validation_error"],
            repair_attempted=repair_attempted,
            repair_error=repair_error,
        )

    data["_summary_validation_status"] = "valid"
    return PreparedSummary(data=data, cacheable=True, validation_status="valid")


def validate_summary_output(raw: object) -> dict:
    usage = _usage_metadata(raw)
    errors: list[str] = []

    for candidate in _summary_candidates(raw):
        try:
            output = PaperSummaryOutput.model_validate(candidate)
        except ValidationError as exc:
            errors.append(str(exc))
            continue

        data = output.model_dump()
        if usage:
            data["_llm_usage"] = usage
        return data

    message = "; ".join(errors) if errors else f"Expected summary JSON object, got {type(raw).__name__}"
    raise SummaryValidationError(message)


def cacheable_summary_payload(data: dict) -> dict:
    return PaperSummaryOutput.model_validate(_without_private_keys(data)).model_dump()


def get_summarizer(settings: Settings) -> Summarizer:
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return OpenAISummarizer(settings.openai_api_key, settings.openai_model)
    if settings.llm_provider == "zai" and settings.zai_api_key:
        return ZaiSummarizer(
            api_key=settings.zai_api_key,
            base_url=settings.zai_base_url,
            model=settings.zai_synthesis_model,
            input_price_per_m=settings.zai_synthesis_input_price_per_m,
            output_price_per_m=settings.zai_synthesis_output_price_per_m,
        )
    return MockSummarizer()


def _summary_candidates(raw: object) -> Iterable[dict]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return

    if not isinstance(raw, dict):
        return

    cleaned = _without_private_keys(raw)
    yield cleaned

    for key in ("summary", "breakdown", "paper_summary"):
        wrapped = raw.get(key)
        if isinstance(wrapped, dict):
            yield _without_private_keys(wrapped)


def _without_private_keys(data: dict) -> dict:
    return {key: value for key, value in data.items() if not str(key).startswith("_")}


def _usage_metadata(raw: object) -> dict:
    if not isinstance(raw, dict):
        return {}
    usage = raw.get("_llm_usage")
    return usage if isinstance(usage, dict) else {}


def _combined_usage_metadata(*items: dict) -> dict:
    usages = [item for item in items if item]
    if not usages:
        return {}

    provider = next((str(item["provider"]) for item in reversed(usages) if item.get("provider")), "unknown")
    model_name = next((str(item["model_name"]) for item in reversed(usages) if item.get("model_name")), "unknown")
    prompt_tokens = sum(int(item.get("prompt_tokens", 0) or 0) for item in usages)
    completion_tokens = sum(int(item.get("completion_tokens", 0) or 0) for item in usages)
    total_tokens = sum(int(item.get("total_tokens", 0) or 0) for item in usages)
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens

    return {
        "provider": provider,
        "model_name": model_name,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(sum(float(item.get("estimated_cost_usd", 0.0) or 0.0) for item in usages), 6),
    }


def _compact_validation_error(error: Exception) -> str:
    return str(error).replace("\n", " ")[:1000]


def _summary_repair_payload(
    paper: ArxivPaper,
    full_text: str,
    raw: object,
    validation_error: str,
) -> dict:
    return {
        "validation_error": validation_error,
        "malformed_output": raw,
        "paper": {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "authors": paper.authors,
            "categories": paper.categories,
            "primary_category": paper.primary_category,
            "abstract": paper.abstract,
            "extracted_text": full_text,
        },
    }


def _usage_from_responses_api(response: object, provider: str, model_name: str) -> UsageEstimate:
    usage = getattr(response, "usage", None)
    prompt_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
    completion_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
    total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0) if usage else 0
    return UsageEstimate(
        provider=provider,
        model_name=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _usage_from_chat_completion(
    response: object,
    provider: str,
    model_name: str,
    input_price_per_m: float,
    output_price_per_m: float,
) -> UsageEstimate:
    usage = getattr(response, "usage", None)
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
    total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0) if usage else 0
    return UsageEstimate(
        provider=provider,
        model_name=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimate_cost_usd(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            input_price_per_m=input_price_per_m,
            output_price_per_m=output_price_per_m,
        ),
    )
