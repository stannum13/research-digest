from datetime import UTC, date, datetime, time, timedelta

from arxiv_client import ArxivPaper, date_window_utc, dedupe_by_base_id, normalize_arxiv_id


def test_normalize_arxiv_id_preserves_base_and_version() -> None:
    assert normalize_arxiv_id("https://arxiv.org/abs/2501.12345v2") == ("2501.12345", "v2")
    assert normalize_arxiv_id("cs/9901001v3") == ("cs/9901001", "v3")


def test_dedupe_by_base_id_keeps_latest_update() -> None:
    older = ArxivPaper(
        arxiv_id="2501.12345",
        arxiv_version="v1",
        title="Older",
        abstract="old",
        authors=[],
        primary_category="cs.LG",
        categories=["cs.LG"],
        published_at=datetime.now(UTC) - timedelta(days=2),
        updated_at=datetime.now(UTC) - timedelta(days=1),
        arxiv_url="https://arxiv.org/abs/2501.12345v1",
        pdf_url="https://arxiv.org/pdf/2501.12345v1",
        raw_metadata={},
    )
    newer = ArxivPaper(
        arxiv_id="2501.12345",
        arxiv_version="v2",
        title="Newer",
        abstract="new",
        authors=[],
        primary_category="cs.LG",
        categories=["cs.LG"],
        published_at=datetime.now(UTC) - timedelta(days=2),
        updated_at=datetime.now(UTC),
        arxiv_url="https://arxiv.org/abs/2501.12345v2",
        pdf_url="https://arxiv.org/pdf/2501.12345v2",
        raw_metadata={},
    )

    assert dedupe_by_base_id([older, newer]) == [newer]


def test_date_window_utc_covers_target_day() -> None:
    start, end = date_window_utc(date(2024, 1, 15))

    assert start == datetime.combine(date(2024, 1, 15), time.min, tzinfo=UTC)
    assert end == datetime.combine(date(2024, 1, 15), time.max, tzinfo=UTC)
