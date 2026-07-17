import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from time import sleep

from settings import Settings

ARXIV_ID_RE = re.compile(r"(?P<base>(?:[a-z-]+/\d{7}|\d{4}\.\d{4,5}))(?P<version>v\d+)?")


@dataclass(frozen=True)
class ArxivPaper:
    arxiv_id: str
    arxiv_version: str | None
    title: str
    abstract: str
    authors: list[str]
    primary_category: str
    categories: list[str]
    published_at: datetime
    updated_at: datetime
    arxiv_url: str
    pdf_url: str
    raw_metadata: dict


def normalize_arxiv_id(raw_id: str) -> tuple[str, str | None]:
    match = ARXIV_ID_RE.search(raw_id)
    if not match:
        cleaned = raw_id.rstrip("/").split("/")[-1]
        return cleaned, None
    return match.group("base"), match.group("version")


def dedupe_by_base_id(papers: list[ArxivPaper]) -> list[ArxivPaper]:
    seen: dict[str, ArxivPaper] = {}
    for paper in papers:
        previous = seen.get(paper.arxiv_id)
        if previous is None or paper.updated_at > previous.updated_at:
            seen[paper.arxiv_id] = paper
    return list(seen.values())


class ArxivClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def fetch_recent(self, categories: Sequence[str] | None = None) -> list[ArxivPaper]:
        try:
            import arxiv
        except ImportError as exc:
            raise RuntimeError("The arxiv package is not installed.") from exc

        client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=2)
        earliest = datetime.now(UTC) - timedelta(hours=self.settings.lookback_hours)
        papers: list[ArxivPaper] = []

        for category in categories or self.settings.category_list:
            search = arxiv.Search(
                query=f"cat:{category}",
                max_results=self.settings.arxiv_max_results_per_category,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending,
            )
            for result in client.results(search):
                published = _ensure_utc(result.published)
                updated = _ensure_utc(result.updated)
                if published < earliest and updated < earliest:
                    continue
                base_id, version = normalize_arxiv_id(result.entry_id)
                categories = list(getattr(result, "categories", []) or [category])
                papers.append(
                    ArxivPaper(
                        arxiv_id=base_id,
                        arxiv_version=version,
                        title=" ".join(result.title.split()),
                        abstract=" ".join(result.summary.split()),
                        authors=[author.name for author in result.authors],
                        primary_category=getattr(result, "primary_category", category) or category,
                        categories=categories,
                        published_at=published,
                        updated_at=updated,
                        arxiv_url=result.entry_id,
                        pdf_url=result.pdf_url,
                        raw_metadata={
                            "entry_id": result.entry_id,
                            "doi": getattr(result, "doi", None),
                            "journal_ref": getattr(result, "journal_ref", None),
                        },
                    )
                )
            sleep(0.5)

        return dedupe_by_base_id(papers)

    def fetch_for_date(self, target_date: date, categories: Sequence[str] | None = None) -> list[ArxivPaper]:
        try:
            import arxiv
        except ImportError as exc:
            raise RuntimeError("The arxiv package is not installed.") from exc

        client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=2)
        start, end = date_window_utc(target_date)
        papers: list[ArxivPaper] = []

        for category in categories or self.settings.category_list:
            search = arxiv.Search(
                query=f"cat:{category} AND submittedDate:[{target_date:%Y%m%d}0000 TO {target_date:%Y%m%d}2359]",
                max_results=self.settings.arxiv_max_results_per_category,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending,
            )
            for result in client.results(search):
                published = _ensure_utc(result.published)
                if published < start or published > end:
                    continue
                updated = _ensure_utc(result.updated)
                base_id, version = normalize_arxiv_id(result.entry_id)
                result_categories = list(getattr(result, "categories", []) or [category])
                papers.append(
                    ArxivPaper(
                        arxiv_id=base_id,
                        arxiv_version=version,
                        title=" ".join(result.title.split()),
                        abstract=" ".join(result.summary.split()),
                        authors=[author.name for author in result.authors],
                        primary_category=getattr(result, "primary_category", category) or category,
                        categories=result_categories,
                        published_at=published,
                        updated_at=updated,
                        arxiv_url=result.entry_id,
                        pdf_url=result.pdf_url,
                        raw_metadata={
                            "entry_id": result.entry_id,
                            "doi": getattr(result, "doi", None),
                            "journal_ref": getattr(result, "journal_ref", None),
                            "target_date": target_date.isoformat(),
                        },
                    )
                )
            sleep(0.5)

        return dedupe_by_base_id(papers)


def date_window_utc(target_date: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(target_date, time.min, tzinfo=UTC),
        datetime.combine(target_date, time.max, tzinfo=UTC),
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
