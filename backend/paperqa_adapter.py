from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol


class PaperRecord(Protocol):
    arxiv_id: str
    arxiv_version: str | None
    title: str
    abstract: str
    authors_json: str
    primary_category: str
    categories_json: str
    published_at: datetime | date
    updated_at: datetime | date
    arxiv_url: str
    pdf_url: str


class BreakdownRecord(Protocol):
    one_line_takeaway: str
    context: str
    what_is_new: str
    mechanism: str
    evidence: str
    methodology_caveats_json: str
    meaningful_extensions_json: str
    confidence: str
    source_basis: str


@dataclass(frozen=True)
class PaperQADocumentSpec:
    """PaperQA2-ready document payload without importing PaperQA2 at module import time."""

    docname: str
    citation: str
    text: str
    metadata: dict[str, Any]


def paper_to_document_spec(
    paper: PaperRecord,
    breakdown: BreakdownRecord | None = None,
) -> PaperQADocumentSpec:
    """Convert a Marginalia paper row into a citation-preserving PaperQA2 document spec."""

    authors = _json_list(paper.authors_json)
    categories = _json_list(paper.categories_json)
    version = paper.arxiv_version or ""
    year = _year(paper.published_at)
    citation = _citation(paper.title, authors, year, paper.arxiv_id)

    text_parts = [
        f"Title: {paper.title}",
        f"arXiv ID: {paper.arxiv_id}{version}",
        f"Authors: {_authors_label(authors)}",
        f"Primary category: {paper.primary_category}",
        f"Categories: {', '.join(categories) if categories else paper.primary_category}",
        "",
        "Abstract:",
        paper.abstract.strip(),
    ]

    if breakdown:
        caveats = _json_list(breakdown.methodology_caveats_json)
        extensions = _json_list(breakdown.meaningful_extensions_json)
        text_parts.extend(
            [
                "",
                "Marginalia summary:",
                breakdown.one_line_takeaway.strip(),
                "",
                "Context:",
                breakdown.context.strip(),
                "",
                "What's new:",
                breakdown.what_is_new.strip(),
                "",
                "Mechanism:",
                breakdown.mechanism.strip(),
                "",
                "Evidence:",
                breakdown.evidence.strip(),
                "",
                "Caveats:",
                _bullets(caveats),
                "",
                "Possible extensions:",
                _bullets(extensions),
            ]
        )

    metadata: dict[str, Any] = {
        "source_kind": "marginalia_paper",
        "arxiv_id": paper.arxiv_id,
        "arxiv_version": version,
        "title": paper.title,
        "authors": authors,
        "primary_category": paper.primary_category,
        "categories": categories,
        "published_at": _iso(paper.published_at),
        "updated_at": _iso(paper.updated_at),
        "arxiv_url": paper.arxiv_url,
        "pdf_url": paper.pdf_url,
        "citation": citation,
    }

    if breakdown:
        metadata.update(
            {
                "source_basis": breakdown.source_basis,
                "confidence": breakdown.confidence,
                "has_marginalia_summary": True,
            }
        )
    else:
        metadata["has_marginalia_summary"] = False

    return PaperQADocumentSpec(
        docname=f"arxiv:{paper.arxiv_id}",
        citation=citation,
        text="\n".join(part for part in text_parts if part is not None).strip() + "\n",
        metadata=metadata,
    )


def paperqa2_importable() -> bool:
    try:
        __import__("paperqa")
    except ImportError:
        return False
    return True


def _json_list(raw: str) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _citation(title: str, authors: list[str], year: int | None, arxiv_id: str) -> str:
    author_label = _authors_label(authors)
    year_label = str(year) if year else "n.d."
    return f"{author_label} ({year_label}). {title}. arXiv:{arxiv_id}."


def _authors_label(authors: list[str]) -> str:
    if not authors:
        return "Unknown authors"
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} and {authors[1]}"
    return f"{authors[0]} et al."


def _year(value: datetime | date) -> int | None:
    return getattr(value, "year", None)


def _iso(value: datetime | date) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _bullets(items: list[str]) -> str:
    if not items:
        return "- None recorded."
    return "\n".join(f"- {item}" for item in items)
