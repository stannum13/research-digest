import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_digest.db"
os.environ["ENABLE_SCHEDULER"] = "false"

TEST_DB = Path("test_digest.db")
if TEST_DB.exists():
    TEST_DB.unlink()

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402

import agent  # noqa: E402
import main  # noqa: E402
from arxiv_client import ArxivPaper  # noqa: E402
from database import Base, SessionLocal, engine, init_db  # noqa: E402
from fulltext import ExtractedText  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    BackfillJob,
    DigestRun,
    LLMCall,
    Paper,
    PaperBreakdown,
    PaperClassification,
    PaperSummaryCache,
    RetrievalSearchCache,
)
from seed import seed_if_empty  # noqa: E402
from settings import Settings  # noqa: E402


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()


def reset_empty_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def reset_old_schema_db_missing_recent_objects() -> None:
    Base.metadata.drop_all(bind=engine)
    timestamp = "2024-01-15 12:30:00.000000"
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE papers (
                    id INTEGER NOT NULL PRIMARY KEY,
                    arxiv_id VARCHAR NOT NULL,
                    arxiv_version VARCHAR,
                    title VARCHAR NOT NULL,
                    abstract TEXT NOT NULL,
                    authors_json TEXT NOT NULL DEFAULT '[]',
                    primary_category VARCHAR NOT NULL,
                    categories_json TEXT NOT NULL DEFAULT '[]',
                    published_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    arxiv_url VARCHAR NOT NULL,
                    pdf_url VARCHAR NOT NULL,
                    raw_metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at DATETIME NOT NULL,
                    updated_local_at DATETIME NOT NULL,
                    last_seen_at DATETIME NOT NULL,
                    is_summarized BOOLEAN NOT NULL DEFAULT 1,
                    is_saved BOOLEAN NOT NULL DEFAULT 0
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO papers (
                    id,
                    arxiv_id,
                    arxiv_version,
                    title,
                    abstract,
                    authors_json,
                    primary_category,
                    categories_json,
                    published_at,
                    updated_at,
                    arxiv_url,
                    pdf_url,
                    raw_metadata_json,
                    created_at,
                    updated_local_at,
                    last_seen_at,
                    is_summarized,
                    is_saved
                )
                VALUES (
                    :id,
                    :arxiv_id,
                    :arxiv_version,
                    :title,
                    :abstract,
                    :authors_json,
                    :primary_category,
                    :categories_json,
                    :published_at,
                    :updated_at,
                    :arxiv_url,
                    :pdf_url,
                    :raw_metadata_json,
                    :created_at,
                    :updated_local_at,
                    :last_seen_at,
                    :is_summarized,
                    :is_saved
                )
                """
            ),
            {
                "id": 1,
                "arxiv_id": "2607.00001",
                "arxiv_version": "v1",
                "title": "Benchmarking attention probes for transformer behavior",
                "abstract": (
                    "A benchmark and scoring rubric evaluate transformer attention probes, activation patching, "
                    "and robustness checks."
                ),
                "authors_json": json.dumps(["Ada Tester"]),
                "primary_category": "cs.CL",
                "categories_json": json.dumps(["cs.CL", "cs.AI"]),
                "published_at": timestamp,
                "updated_at": timestamp,
                "arxiv_url": "https://arxiv.org/abs/2607.00001",
                "pdf_url": "https://arxiv.org/pdf/2607.00001",
                "raw_metadata_json": "{}",
                "created_at": timestamp,
                "updated_local_at": timestamp,
                "last_seen_at": timestamp,
                "is_summarized": True,
                "is_saved": False,
            },
        )


def test_init_db_upgrades_old_sqlite_schema_for_recent_columns_tables_and_indexes() -> None:
    reset_old_schema_db_missing_recent_objects()
    try:
        init_db()

        inspector = inspect(engine)
        assert "paper_classifications" in inspector.get_table_names()
        assert "score" in {column["name"] for column in inspector.get_columns("papers")}
        assert "ix_papers_category_score" in {index["name"] for index in inspector.get_indexes("papers")}
        assert "ix_paper_classifications_paper_type" in {
            index["name"] for index in inspector.get_indexes("paper_classifications")
        }

        with TestClient(app) as client:
            papers = client.get("/papers")
            created = client.post("/papers/2607.00001/classify")
            listed = client.get("/papers/2607.00001/classifications")

        assert papers.status_code == 200
        assert papers.json()["total"] == 1
        assert papers.json()["items"][0]["score"] is None
        assert created.status_code == 200
        assert listed.status_code == 200
        assert created.json()["items"]
        assert listed.json()["items"] == created.json()["items"]
    finally:
        reset_empty_db()


def test_health_and_seeded_papers() -> None:
    reset_db()
    with TestClient(app) as client:
        health = client.get("/health")
        papers = client.get("/papers")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert papers.status_code == 200
    data = papers.json()
    assert data["total"] == 8
    assert data["items"][0]["breakdown"]["one_line_takeaway"]
    assert data["digest_status"]["status"] == "success"


def test_cors_allows_vite_fallback_dev_ports() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/papers",
            headers={
                "Origin": "http://localhost:5176",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5176"


def test_unhandled_exception_returns_request_id_without_raw_detail() -> None:
    if not any(getattr(route, "path", "") == "/__test__/boom" for route in app.routes):

        @app.get("/__test__/boom")
        def _test_boom() -> None:
            raise RuntimeError("secret provider traceback detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__test__/boom", headers={"x-request-id": "req-test-123"})

    assert response.status_code == 500
    payload = response.json()
    assert payload == {
        "error": "Internal server error",
        "detail": "Request ID: req-test-123",
    }
    assert "secret provider" not in json.dumps(payload)


def test_filters_search_and_saved_route() -> None:
    reset_db()
    with TestClient(app) as client:
        quantum = client.get("/papers", params={"category": "quant-ph"})
        saved = client.get("/papers/saved")
        search = client.get("/papers", params={"q": "confusion"})

    assert quantum.status_code == 200
    assert quantum.json()["total"] == 2
    assert saved.status_code == 200
    assert saved.json()["total"] == 2
    assert search.status_code == 200
    assert search.json()["total"] == 1


def test_papers_date_filter_uses_published_day() -> None:
    reset_db()
    target_published_at = datetime(2024, 1, 15, 12, 30, tzinfo=UTC)
    db = SessionLocal()
    try:
        paper = db.query(Paper).filter(Paper.arxiv_id == "2606.30003").one()
        paper.published_at = target_published_at
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        matching_day = client.get("/papers", params={"date": "2024-01-15"})
        other_day = client.get("/papers", params={"date": "2024-01-16"})
        invalid = client.get("/papers", params={"date": "not-a-date"})

    assert matching_day.status_code == 200
    assert matching_day.json()["total"] == 1
    assert matching_day.json()["items"][0]["arxiv_id"] == "2606.30003"
    assert other_day.status_code == 200
    assert other_day.json()["total"] == 0
    assert invalid.status_code == 400


def test_save_toggle_and_feedback() -> None:
    reset_db()
    with TestClient(app) as client:
        before = client.get("/papers/2606.30003").json()
        toggled = client.post("/papers/2606.30003/save").json()
        feedback = client.post(
            "/papers/2606.30003/feedback",
            json={"signal": "important", "note": "Useful calibration benchmark."},
        )

    assert toggled["is_saved"] is (not before["is_saved"])
    assert feedback.status_code == 200
    assert feedback.json()["signal"] == "important"


def test_paper_classification_create_list_idempotent_and_label_shape() -> None:
    reset_db()
    expected_label_types = {
        "method_family",
        "evidence_type",
        "caveat_class",
        "task",
        "dataset_or_benchmark",
        "architecture_primitive",
        "probe_family",
    }

    with TestClient(app) as client:
        before = client.get("/papers/2606.30003/classifications")
        created = client.post("/papers/2606.30003/classify")
        repeated = client.post("/papers/2606.30003/classify")
        listed = client.get("/papers/2606.30003/classifications")

    assert before.status_code == 200
    assert before.json()["items"] == []
    assert created.status_code == 200
    assert repeated.status_code == 200
    assert listed.status_code == 200

    payload = created.json()
    classifications = payload["items"]
    repeated_classifications = repeated.json()["items"]
    listed_classifications = listed.json()["items"]
    triples = {(item["label_type"], item["label"]) for item in classifications}

    assert payload["arxiv_id"] == "2606.30003"
    assert {item["label_type"] for item in classifications} >= expected_label_types
    assert triples == {(item["label_type"], item["label"]) for item in repeated_classifications}
    assert triples == {(item["label_type"], item["label"]) for item in listed_classifications}
    assert ("method_family", "benchmarking") in triples
    assert ("evidence_type", "benchmark_evaluation") in triples
    assert ("caveat_class", "evaluation_design_sensitivity") in triples
    assert ("task", "clarification_detection") in triples
    assert ("dataset_or_benchmark", "underspecified_questions_benchmark") in triples
    assert ("architecture_primitive", "language_model") in triples
    assert ("probe_family", "ambiguity_probe") in triples

    for item in classifications:
        assert item["label_type"] in expected_label_types
        assert item["label"] == item["label"].lower()
        assert " " not in item["label"]
        assert 0 <= item["confidence"] <= 1
        assert item["source"] == "metadata-breakdown-heuristic-v1"
        assert item["rationale"]
        assert item["created_at"]
        assert item["updated_at"]

    db = SessionLocal()
    try:
        assert db.query(PaperClassification).filter(PaperClassification.paper_id == payload["paper_id"]).count() == len(
            classifications
        )
    finally:
        db.close()


def test_paper_classification_unknown_paper() -> None:
    reset_db()
    with TestClient(app) as client:
        classify_response = client.post("/papers/9999.99999/classify")
        list_response = client.get("/papers/9999.99999/classifications")

    assert classify_response.status_code == 404
    assert classify_response.json()["error"] == "Paper not found"
    assert list_response.status_code == 404
    assert list_response.json()["error"] == "Paper not found"


def test_paper_classification_does_not_call_llm(monkeypatch) -> None:
    reset_db()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("classification endpoint must not call digest or summary providers")

    monkeypatch.setattr(main, "run_digest", fail_if_called)
    monkeypatch.setattr(agent, "get_summarizer", fail_if_called)

    db = SessionLocal()
    try:
        llm_calls_before = db.query(LLMCall).count()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.post("/papers/2606.30003/classify")

    assert response.status_code == 200
    db = SessionLocal()
    try:
        assert db.query(LLMCall).count() == llm_calls_before
    finally:
        db.close()


def test_bulk_classification_run_respects_limit_summarized_only_and_idempotent() -> None:
    reset_db()
    db = SessionLocal()
    try:
        paper = db.query(Paper).filter(Paper.arxiv_id == "2606.30001").one()
        paper.is_summarized = False
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.post("/classifications/run", params={"limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["only_missing"] is True
    assert payload["limit"] == 2
    assert payload["papers_processed"] == 2
    assert payload["arxiv_ids"] == ["2606.30002", "2606.30003"]
    assert payload["status"]["summarized_paper_count"] == 7
    assert payload["status"]["classified_paper_count"] == 2
    assert payload["status"]["coverage_percentage"] == 28.57

    db = SessionLocal()
    try:
        first_paper = db.query(Paper).filter(Paper.arxiv_id == "2606.30001").one()
        label_count_after_first_run = db.query(PaperClassification).count()
        assert len(first_paper.classifications) == 0
    finally:
        db.close()

    with TestClient(app) as client:
        repeated = client.post("/classifications/run", params={"limit": 2, "only_missing": False})

    assert repeated.status_code == 200
    repeated_payload = repeated.json()
    assert repeated_payload["arxiv_ids"] == payload["arxiv_ids"]
    assert repeated_payload["status"]["total_labels"] == payload["status"]["total_labels"]

    db = SessionLocal()
    try:
        assert db.query(PaperClassification).count() == label_count_after_first_run
    finally:
        db.close()


def test_bulk_classification_only_missing_skips_already_classified_papers() -> None:
    reset_db()
    with TestClient(app) as client:
        preclassified = client.post("/papers/2606.30001/classify")
        response = client.post("/classifications/run", params={"limit": 2, "only_missing": True})

    assert preclassified.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["papers_processed"] == 2
    assert payload["arxiv_ids"] == ["2606.30002", "2606.30003"]
    assert payload["status"]["summarized_paper_count"] == 8
    assert payload["status"]["classified_paper_count"] == 3
    assert payload["status"]["coverage_percentage"] == 37.5


def test_classification_status_counts_and_coverage() -> None:
    reset_db()
    expected_label_types = {
        "method_family",
        "evidence_type",
        "caveat_class",
        "task",
        "dataset_or_benchmark",
        "architecture_primitive",
        "probe_family",
    }

    with TestClient(app) as client:
        before = client.get("/classifications/status")
        run = client.post("/classifications/run")
        after = client.get("/classifications/status")

    assert before.status_code == 200
    before_payload = before.json()
    assert before_payload["summarized_paper_count"] == 8
    assert before_payload["classified_paper_count"] == 0
    assert before_payload["coverage_percentage"] == 0.0
    assert before_payload["total_labels"] == 0
    assert set(before_payload["label_type_counts"]) == expected_label_types
    assert all(count == 0 for count in before_payload["label_type_counts"].values())

    assert run.status_code == 200
    run_payload = run.json()
    assert run_payload["papers_processed"] == 8

    assert after.status_code == 200
    after_payload = after.json()
    assert after_payload == run_payload["status"]
    assert after_payload["summarized_paper_count"] == 8
    assert after_payload["classified_paper_count"] == 8
    assert after_payload["coverage_percentage"] == 100.0
    assert after_payload["total_labels"] == sum(after_payload["label_type_counts"].values())
    assert after_payload["total_labels"] > 8
    assert set(after_payload["label_type_counts"]) == expected_label_types
    assert after_payload["label_type_counts"]["method_family"] >= 8


def test_bulk_classification_does_not_call_llm(monkeypatch) -> None:
    reset_db()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("bulk classification endpoint must not call digest or summary providers")

    monkeypatch.setattr(main, "run_digest", fail_if_called)
    monkeypatch.setattr(agent, "get_summarizer", fail_if_called)

    db = SessionLocal()
    try:
        llm_calls_before = db.query(LLMCall).count()
    finally:
        db.close()

    with TestClient(app) as client:
        status_response = client.get("/classifications/status")
        response = client.post("/classifications/run", params={"limit": 3})
        repeated = client.post("/classifications/run", params={"limit": 3, "only_missing": False})

    assert status_response.status_code == 200
    assert response.status_code == 200
    assert repeated.status_code == 200
    db = SessionLocal()
    try:
        assert db.query(LLMCall).count() == llm_calls_before
    finally:
        db.close()


def test_search_matches_paper_text_and_returns_reason() -> None:
    reset_db()

    with TestClient(app) as client:
        response = client.get("/search", params={"q": "confusion"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "confusion"
    assert payload["total"] == 1
    result = payload["items"][0]
    assert result["paper"]["arxiv_id"] == "2606.30003"
    assert result["score"] > 0
    assert result["matched_fields"]
    assert "Matched paper fields" in result["reason"]


def test_search_matches_classification_label_filters() -> None:
    reset_db()

    with TestClient(app) as client:
        classified = client.post("/papers/2606.30003/classify")
        response = client.get(
            "/search",
            params={
                "label_type": "probe_family",
                "label": "ambiguity_probe",
            },
        )

    assert classified.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    result = payload["items"][0]
    assert result["paper"]["arxiv_id"] == "2606.30003"
    assert "probe_family: ambiguity_probe" in result["matched_labels"]
    assert "Matched ontology labels" in result["reason"]


def test_search_cache_miss_then_hit_status_accounting() -> None:
    reset_db()

    with TestClient(app) as client:
        before = client.get("/search/cache/status")
        first = client.get("/search", params={"q": "confusion"})
        after_miss = client.get("/search/cache/status")
        second = client.get("/search", params={"q": "confusion"})
        after_hit = client.get("/search/cache/status")

    assert before.status_code == 200
    assert before.json()["total_entries"] == 0
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()

    miss_payload = after_miss.json()
    assert miss_payload["total_entries"] == 1
    assert miss_payload["total_hits"] == 0
    assert miss_payload["entries"][0]["normalized_q"] == "confusion"
    assert miss_payload["entries"][0]["result_count"] == 1
    assert miss_payload["entries"][0]["hit_count"] == 0

    hit_payload = after_hit.json()
    assert hit_payload["total_entries"] == 1
    assert hit_payload["total_hits"] == 1
    assert hit_payload["entries"][0]["hit_count"] == 1
    assert hit_payload["entries"][0]["last_hit_at"]

    db = SessionLocal()
    try:
        assert db.query(RetrievalSearchCache).count() == 1
    finally:
        db.close()


def test_search_cache_delete_requires_admin_key(monkeypatch) -> None:
    reset_db()

    monkeypatch.setattr(main.settings, "admin_api_key", "")
    with TestClient(app) as client:
        disabled_bulk = client.delete("/search/cache")
        disabled_targeted = client.delete("/search/cache/1")

    assert disabled_bulk.status_code == 404
    assert disabled_bulk.json()["error"] == "Administrative endpoint disabled"
    assert disabled_targeted.status_code == 404
    assert disabled_targeted.json()["error"] == "Administrative endpoint disabled"

    monkeypatch.setattr(main.settings, "admin_api_key", "test-admin")
    with TestClient(app) as client:
        missing_header = client.delete("/search/cache")
        wrong_header = client.delete("/search/cache", headers={"x-admin-key": "wrong"})

    assert missing_header.status_code == 403
    assert missing_header.json()["error"] == "Invalid administrative key"
    assert wrong_header.status_code == 403
    assert wrong_header.json()["error"] == "Invalid administrative key"


def test_search_cache_clear_deletes_current_version_entries_only(monkeypatch) -> None:
    reset_db()
    monkeypatch.setattr(main.settings, "admin_api_key", "test-admin")

    with TestClient(app) as client:
        first = client.get("/search", params={"q": "confusion"})

    assert first.status_code == 200

    db = SessionLocal()
    try:
        stale = RetrievalSearchCache(
            normalized_q="stale query",
            normalized_label_type="",
            normalized_label="",
            limit=25,
            cache_version="retrieval-search-stale",
            response_json='{"items":[],"total":0,"query":"stale query"}',
            result_count=0,
        )
        db.add(stale)
        db.flush()
        stale_id = stale.id
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        before = client.get("/search/cache/status")
        cleared = client.delete("/search/cache", headers={"x-admin-key": "test-admin"})
        after = client.get("/search/cache/status")

    assert before.status_code == 200
    before_payload = before.json()
    assert before_payload["cache_version"] == main.RETRIEVAL_SEARCH_CACHE_VERSION
    assert before_payload["total_entries"] == 1
    assert before_payload["entries"][0]["id"]

    assert cleared.status_code == 200
    assert cleared.json() == {
        "cache_version": main.RETRIEVAL_SEARCH_CACHE_VERSION,
        "deleted_count": 1,
    }

    assert after.status_code == 200
    after_payload = after.json()
    assert after_payload["cache_version"] == main.RETRIEVAL_SEARCH_CACHE_VERSION
    assert after_payload["total_entries"] == 0
    assert after_payload["total_hits"] == 0
    assert after_payload["entries"] == []

    db = SessionLocal()
    try:
        remaining = db.get(RetrievalSearchCache, stale_id)
        assert remaining is not None
        assert remaining.cache_version == "retrieval-search-stale"
        assert db.query(RetrievalSearchCache).count() == 1
    finally:
        db.close()


def test_search_cache_targeted_delete_by_status_id(monkeypatch) -> None:
    reset_db()
    monkeypatch.setattr(main.settings, "admin_api_key", "test-admin")

    with TestClient(app) as client:
        first = client.get("/search", params={"q": "confusion"})
        second = client.get("/search", params={"q": "transformer"})
        status = client.get("/search/cache/status")

        entries_by_query = {entry["normalized_q"]: entry for entry in status.json()["entries"]}
        deleted = client.delete(
            f"/search/cache/{entries_by_query['confusion']['id']}",
            headers={"x-admin-key": "test-admin"},
        )
        missing = client.delete(
            f"/search/cache/{entries_by_query['confusion']['id']}",
            headers={"x-admin-key": "test-admin"},
        )
        after = client.get("/search/cache/status")

    assert first.status_code == 200
    assert second.status_code == 200
    assert status.status_code == 200
    assert status.json()["total_entries"] == 2
    assert set(entries_by_query) == {"confusion", "transformer"}

    assert deleted.status_code == 200
    assert deleted.json() == {
        "cache_version": main.RETRIEVAL_SEARCH_CACHE_VERSION,
        "deleted_count": 1,
    }
    assert missing.status_code == 404
    assert missing.json()["error"] == "Search cache entry not found"

    after_payload = after.json()
    assert after_payload["total_entries"] == 1
    assert after_payload["entries"][0]["normalized_q"] == "transformer"


def test_search_cache_uses_normalized_key_equivalence() -> None:
    reset_db()

    with TestClient(app) as client:
        classified = client.post("/papers/2606.30003/classify")
        first = client.get(
            "/search",
            params={
                "q": "  AMBIGUITY  ",
                "label_type": "probe-family",
                "label": "ambiguity-probe",
                "limit": 5,
            },
        )
        second = client.get(
            "/search",
            params={
                "q": "ambiguity",
                "label_type": "probe_family",
                "label": "ambiguity_probe",
                "limit": 5,
            },
        )
        status = client.get("/search/cache/status")

    assert classified.status_code == 200
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["query"] == "ambiguity"

    status_payload = status.json()
    assert status_payload["total_entries"] == 1
    assert status_payload["total_hits"] == 1
    entry = status_payload["entries"][0]
    assert entry["normalized_q"] == "ambiguity"
    assert entry["normalized_label_type"] == "probe family"
    assert entry["normalized_label"] == "ambiguity probe"
    assert entry["limit"] == 5


def test_search_empty_query_returns_no_results() -> None:
    reset_db()

    with TestClient(app) as client:
        response = client.get("/search")
        repeated = client.get("/search")
        status = client.get("/search/cache/status")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "query": ""}
    assert repeated.status_code == 200
    assert repeated.json() == response.json()
    assert status.json()["total_entries"] == 1
    assert status.json()["total_hits"] == 1
    assert status.json()["entries"][0]["result_count"] == 0


def test_search_cache_does_not_call_llm(monkeypatch) -> None:
    reset_db()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("search cache endpoint must not call digest or summary providers")

    monkeypatch.setattr(main, "run_digest", fail_if_called)
    monkeypatch.setattr(agent, "get_summarizer", fail_if_called)

    db = SessionLocal()
    try:
        llm_calls_before = db.query(LLMCall).count()
    finally:
        db.close()

    with TestClient(app) as client:
        first = client.get("/search", params={"q": "confusion"})
        second = client.get("/search", params={"q": "confusion"})
        status = client.get("/search/cache/status")

    assert first.status_code == 200
    assert second.status_code == 200
    assert status.status_code == 200
    assert status.json()["total_hits"] == 1

    db = SessionLocal()
    try:
        assert db.query(LLMCall).count() == llm_calls_before
    finally:
        db.close()


def test_synthesis_run_create_list_get_and_deterministic_sources() -> None:
    reset_db()
    selected_arxiv_ids = ["2606.30001", "2606.30002", "2606.30003"]
    request_body = {
        "arxiv_ids": selected_arxiv_ids,
        "mode": "compare",
        "instructions": " Focus on evidence quality. ",
    }

    with TestClient(app) as client:
        created = client.post("/synthesis/runs", json=request_body)
        repeated = client.post("/synthesis/runs", json=request_body)
        listed = client.get("/synthesis/runs")
        detail = client.get(f"/synthesis/runs/{created.json()['id']}")

    assert created.status_code == 201
    payload = created.json()
    repeated_payload = repeated.json()
    selected_ids = [paper["id"] for paper in payload["selected_papers"]]

    assert payload["mode"] == "compare"
    assert payload["instructions"] == "Focus on evidence quality."
    assert payload["model_provider"] == "none"
    assert payload["model_name"] == "metadata-breakdown-heuristic-v1"
    assert payload["prompt_version"] == "synthesis-workbench-deterministic-v1"
    assert payload["source_paper_ids"] == selected_ids
    assert [paper["arxiv_id"] for paper in payload["selected_papers"]] == selected_arxiv_ids
    assert payload["argument_map"] == repeated_payload["argument_map"]
    assert payload["contradictions"] == repeated_payload["contradictions"]
    assert payload["evidence_matrix"] == repeated_payload["evidence_matrix"]
    assert payload["open_questions"] == repeated_payload["open_questions"]
    assert payload["extension_ideas"] == repeated_payload["extension_ideas"]
    assert payload["replication_or_ablation_plan"] == repeated_payload["replication_or_ablation_plan"]
    assert payload["caveats"] == repeated_payload["caveats"]

    selected_id_set = set(selected_ids)
    for field in [
        "argument_map",
        "contradictions",
        "evidence_matrix",
        "open_questions",
        "extension_ideas",
        "replication_or_ablation_plan",
        "caveats",
    ]:
        for entry in payload[field]:
            assert set(entry["source_paper_ids"]).issubset(selected_id_set)

    evidence_by_arxiv_id = {row["arxiv_id"]: row for row in payload["evidence_matrix"]}
    assert evidence_by_arxiv_id["2606.30001"]["source_paper_ids"] == [selected_ids[0]]
    assert evidence_by_arxiv_id["2606.30001"]["evidence"]

    assert listed.status_code == 200
    listed_payload = listed.json()
    assert listed_payload["total"] == 2
    assert listed_payload["items"][0]["id"] == repeated_payload["id"]
    assert listed_payload["items"][1]["id"] == payload["id"]

    assert detail.status_code == 200
    assert detail.json() == payload

    db = SessionLocal()
    try:
        assert db.query(LLMCall).count() == 0
    finally:
        db.close()


def test_synthesis_run_provider_output_logs_usage(monkeypatch) -> None:
    reset_db()
    selected_arxiv_ids = ["2606.30001", "2606.30002"]

    def fake_build_synthesis(papers: list[Paper], mode: str, instructions: str | None, settings: Settings) -> dict:
        source_ids = [paper.id for paper in papers]
        section = [
            {"source_paper_ids": source_ids, "claim": f"{mode} provider synthesis", "instructions": instructions}
        ]
        return {
            "argument_map": section,
            "contradictions": [{"source_paper_ids": source_ids, "status": "not_detected"}],
            "evidence_matrix": [{"source_paper_ids": [source_ids[0]], "evidence": "Provider evidence"}],
            "open_questions": [{"source_paper_ids": source_ids, "question": "Which claim survives ablation?"}],
            "extension_ideas": [{"source_paper_ids": source_ids, "idea": "Try a provider-guided extension"}],
            "replication_or_ablation_plan": [{"source_paper_ids": source_ids, "step": 1, "action": "Ablate"}],
            "caveats": [{"source_paper_ids": source_ids, "caveat": "Provider caveat"}],
            "source_paper_ids": source_ids,
            "prompt_version": "synthesis-workbench-provider-v1",
            "model_provider": "zai",
            "model_name": "glm-test",
            "_synthesis_validation_status": "valid",
            "_llm_usage": {
                "provider": "zai",
                "model_name": "glm-test",
                "prompt_tokens": 40,
                "completion_tokens": 20,
                "total_tokens": 60,
                "estimated_cost_usd": 0.003,
            },
        }

    monkeypatch.setattr(main, "build_synthesis", fake_build_synthesis)

    with TestClient(app) as client:
        created = client.post(
            "/synthesis/runs",
            json={
                "arxiv_ids": selected_arxiv_ids,
                "mode": "argument_map",
                "instructions": "Preserve source links.",
            },
        )

    assert created.status_code == 201
    payload = created.json()
    assert payload["model_provider"] == "zai"
    assert payload["model_name"] == "glm-test"
    assert payload["prompt_version"] == "synthesis-workbench-provider-v1"
    assert payload["argument_map"][0]["source_paper_ids"] == payload["source_paper_ids"]

    db = SessionLocal()
    try:
        llm_call = db.query(LLMCall).one()
        metadata = json.loads(llm_call.metadata_json)
        assert llm_call.digest_run_id is None
        assert llm_call.paper_id is None
        assert llm_call.task == "synthesis"
        assert llm_call.provider == "zai"
        assert llm_call.model_name == "glm-test"
        assert llm_call.prompt_tokens == 40
        assert llm_call.completion_tokens == 20
        assert llm_call.total_tokens == 60
        assert llm_call.estimated_cost_usd == 0.003
        assert metadata["mode"] == "argument_map"
        assert metadata["prompt_version"] == "synthesis-workbench-provider-v1"
        assert metadata["synthesis_validation_status"] == "valid"
        assert metadata["source_paper_ids"] == payload["source_paper_ids"]
    finally:
        db.close()


def test_synthesis_run_validation() -> None:
    reset_db()
    db = SessionLocal()
    try:
        first_id = db.query(Paper).filter(Paper.arxiv_id == "2606.30001").one().id
        second_id = db.query(Paper).filter(Paper.arxiv_id == "2606.30002").one().id
    finally:
        db.close()

    with TestClient(app) as client:
        one_paper = client.post("/synthesis/runs", json={"paper_ids": [first_id], "mode": "overview"})
        duplicate_paper = client.post("/synthesis/runs", json={"paper_ids": [first_id, first_id]})
        missing_paper = client.post("/synthesis/runs", json={"paper_ids": [first_id, 999999]})
        too_many = client.post("/synthesis/runs", json={"paper_ids": list(range(1, 10))})
        both_identifier_styles = client.post(
            "/synthesis/runs",
            json={"paper_ids": [first_id, second_id], "arxiv_ids": ["2606.30001", "2606.30002"]},
        )
        missing_run = client.get("/synthesis/runs/999999")

    assert one_paper.status_code == 400
    assert duplicate_paper.status_code == 400
    assert missing_paper.status_code == 400
    assert too_many.status_code == 422
    assert both_identifier_styles.status_code == 422
    assert missing_run.status_code == 404


def test_digest_run_without_llm_is_clear_and_logged() -> None:
    reset_db()
    with TestClient(app) as client:
        created = client.post("/digest/run")
        queued_status = client.get("/digest/status")
        run = client.post(f"/digest/runs/{created.json()['id']}/run")
        status = client.get("/digest/status")
        latest = client.get("/digest/latest")

    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["status"] == "pending"
    assert "Digest job created" in created_payload["message"]
    assert queued_status.json()["status"] == "pending"

    assert run.status_code == 200
    payload = run.json()
    assert payload["status"] == "failed"
    assert "LLM not configured" in payload["error_message"]
    assert payload["message"] == "Digest job failed."
    assert status.json()["status"] == "failed"
    assert len(latest.json()["papers"]) == 8


def test_digest_run_accepts_target_date_and_exposes_detail() -> None:
    reset_db()
    with TestClient(app) as client:
        run = client.post(
            "/digest/run",
            json={"target_date": "2024-01-15", "category_scope": ["cs.LG", "cs.AI"]},
        )
        detail = client.get(f"/digest/runs/{run.json()['id']}")
        worker = client.post(f"/digest/runs/{run.json()['id']}/run")
        alias_run = client.post("/digest/run", json={"target_date": "2024-01-16", "categories": ["cs.CL"]})

    assert run.status_code == 200
    payload = run.json()
    assert payload["status"] == "pending"
    assert payload["target_date"] == "2024-01-15"
    assert payload["category_scope"] == ["cs.LG", "cs.AI"]
    assert "Digest job created" in payload["message"]
    assert worker.status_code == 200
    assert worker.json()["status"] == "failed"
    assert "LLM not configured" in worker.json()["error_message"]
    assert alias_run.status_code == 200
    assert alias_run.json()["status"] == "pending"
    assert alias_run.json()["category_scope"] == ["cs.CL"]

    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["target_date"] == "2024-01-15"
    assert detail_payload["category_scope"] == ["cs.LG", "cs.AI"]
    assert detail_payload["config"]["target_date"] == "2024-01-15"
    assert detail_payload["config"]["categories"] == ["cs.LG", "cs.AI"]
    assert detail_payload["llm_calls"] == []
    assert detail_payload["llm_tokens_total"] == 0
    assert detail_payload["estimated_llm_cost_usd"] == 0


def test_digest_run_worker_is_idempotent_for_terminal_runs() -> None:
    reset_db()
    db = SessionLocal()
    try:
        run = DigestRun(
            status="success",
            papers_fetched=1,
            papers_new=1,
            papers_summarized=1,
            category_scope_json=json.dumps(["cs.LG"]),
            config_json=json.dumps({"categories": ["cs.LG"]}),
            completed_at=datetime.now(UTC),
        )
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    with TestClient(app) as client:
        first = client.post(f"/digest/runs/{run_id}/run")
        second = client.post(f"/digest/runs/{run_id}/run")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "success"
    assert first.json()["message"] == "Digest job already reached a terminal state."
    assert second.json()["papers_summarized"] == 1


def test_digest_run_detail_includes_llm_accounting() -> None:
    reset_db()
    db = SessionLocal()
    try:
        paper = db.query(Paper).filter(Paper.arxiv_id == "2606.30002").one()
        run = DigestRun(
            target_date=date(2024, 1, 15),
            category_scope_json=json.dumps(["cs.LG"]),
            status="success",
            papers_fetched=1,
            papers_new=0,
            papers_summarized=1,
            config_json=json.dumps({"categories": ["cs.LG"], "target_date": "2024-01-15"}),
        )
        db.add(run)
        db.flush()
        db.add(
            LLMCall(
                digest_run_id=run.id,
                paper_id=paper.id,
                task="paper_summary",
                provider="zai",
                model_name="glm-test",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                estimated_cost_usd=0.012345,
                metadata_json=json.dumps({"source_basis": "abstract_only"}),
            )
        )
        db.commit()
        run_id = run.id
    finally:
        db.close()

    with TestClient(app) as client:
        detail = client.get(f"/digest/runs/{run_id}")

    assert detail.status_code == 200
    payload = detail.json()
    assert payload["status"] == "success"
    assert payload["target_date"] == "2024-01-15"
    assert payload["llm_tokens_total"] == 150
    assert payload["estimated_llm_cost_usd"] == 0.012345
    assert payload["llm_calls"][0]["arxiv_id"] == "2606.30002"
    assert payload["llm_calls"][0]["metadata"] == {"source_basis": "abstract_only"}


def test_digest_budget_exhaustion_is_not_reported_as_success(monkeypatch) -> None:
    reset_empty_db()
    fetched = {
        "first": _digest_test_paper(
            arxiv_id="2606.99991",
            title="Budget Paper One",
            abstract="First paper should be summarized before the budget stop.",
        ),
        "second": _digest_test_paper(
            arxiv_id="2606.99992",
            title="Budget Paper Two",
            abstract="Second paper should remain unsummarized after the budget stop.",
        ),
    }
    summarizer = CountingSummaryProvider()
    _patch_digest_dependencies(monkeypatch, fetched, summarizer)
    settings = _digest_test_settings()
    settings.top_n = 2
    settings.llm_run_budget_usd = 0.001

    db = SessionLocal()
    try:
        run = agent.run_digest(db, settings)
        assert run.status == "budget_exhausted"
        assert run.papers_summarized == 1
        assert "LLM run budget reached" in (run.error_message or "")
        assert summarizer.calls == 1
        assert db.query(Paper).filter(Paper.is_summarized.is_(False)).count() == 1
        run_id = run.id
    finally:
        db.close()

    with TestClient(app) as client:
        latest = client.get("/digest/latest")
        status = client.get("/digest/status")

    assert latest.status_code == 200
    assert latest.json()["run"]["id"] == run_id
    assert latest.json()["run"]["status"] == "budget_exhausted"
    assert status.status_code == 200
    assert status.json()["status"] == "budget_exhausted"


def test_digest_summary_cache_hit_skips_llm_and_changed_content_miss_logs_call(monkeypatch) -> None:
    reset_empty_db()
    fetched = {"paper": _digest_test_paper(abstract="First abstract")}
    summarizer = CountingSummaryProvider()
    _patch_digest_dependencies(monkeypatch, fetched, summarizer)
    settings = _digest_test_settings()

    db = SessionLocal()
    try:
        first_run = agent.run_digest(db, settings)
        assert first_run.status == "success"
        assert first_run.papers_summarized == 1
        assert summarizer.calls == 1
        assert db.query(LLMCall).count() == 1
        assert db.query(PaperSummaryCache).count() == 1

        paper = db.query(Paper).filter(Paper.arxiv_id == fetched["paper"].arxiv_id).one()
        db.delete(paper.breakdown)
        paper.is_summarized = False
        db.commit()

        second_run = agent.run_digest(db, settings)
        assert second_run.status == "success"
        assert second_run.papers_summarized == 1
        assert summarizer.calls == 1
        assert db.query(LLMCall).count() == 1
        assert db.query(PaperSummaryCache).count() == 1

        paper = db.query(Paper).filter(Paper.arxiv_id == fetched["paper"].arxiv_id).one()
        assert paper.breakdown.one_line_takeaway == "Provider takeaway 1"
        db.delete(paper.breakdown)
        paper.is_summarized = False
        fetched["paper"] = _digest_test_paper(abstract="Changed abstract")
        db.commit()

        third_run = agent.run_digest(db, settings)
        assert third_run.status == "success"
        assert third_run.papers_summarized == 1
        assert summarizer.calls == 2
        assert db.query(LLMCall).count() == 2
        assert db.query(PaperSummaryCache).count() == 2
    finally:
        db.close()


def test_invalid_provider_summary_falls_back_without_broken_breakdown(monkeypatch) -> None:
    reset_empty_db()
    fetched = {"paper": _digest_test_paper()}
    summarizer = InvalidSummaryProvider()
    _patch_digest_dependencies(monkeypatch, fetched, summarizer)

    db = SessionLocal()
    try:
        run = agent.run_digest(db, _digest_test_settings())

        assert run.status == "success"
        assert run.papers_summarized == 1
        assert summarizer.calls == 1
        assert db.query(PaperSummaryCache).count() == 0

        breakdown = db.query(PaperBreakdown).one()
        assert breakdown.model_provider == "mock"
        assert breakdown.model_name == "deterministic-fallback"
        assert breakdown.difficulty == "intermediate"
        assert breakdown.confidence == "low"
        assert json.loads(breakdown.methodology_caveats_json)
        assert json.loads(breakdown.tags_json) == ["cs.LG", "fallback-summary"]

        llm_call = db.query(LLMCall).one()
        metadata = json.loads(llm_call.metadata_json)
        assert llm_call.provider == "openai"
        assert llm_call.model_name == "summary-test"
        assert metadata["summary_validation_status"] == "fallback"
        assert "one_line_takeaway" in metadata["summary_validation_error"]
    finally:
        db.close()


def test_invalid_provider_summary_can_be_repaired_and_cached(monkeypatch) -> None:
    reset_empty_db()
    fetched = {"paper": _digest_test_paper()}
    summarizer = RepairingSummaryProvider()
    _patch_digest_dependencies(monkeypatch, fetched, summarizer)

    db = SessionLocal()
    try:
        run = agent.run_digest(db, _digest_test_settings())

        assert run.status == "success"
        assert run.papers_summarized == 1
        assert summarizer.calls == 1
        assert summarizer.repairs == 1
        assert db.query(PaperSummaryCache).count() == 1

        breakdown = db.query(PaperBreakdown).one()
        assert breakdown.model_provider == "openai"
        assert breakdown.model_name == "summary-test"
        assert breakdown.one_line_takeaway == "Repaired provider takeaway"
        assert breakdown.confidence == "medium"

        llm_call = db.query(LLMCall).one()
        metadata = json.loads(llm_call.metadata_json)
        assert llm_call.provider == "openai"
        assert llm_call.model_name == "summary-test"
        assert llm_call.prompt_tokens == 32
        assert llm_call.completion_tokens == 14
        assert llm_call.total_tokens == 46
        assert llm_call.estimated_cost_usd == 0.005
        assert metadata["summary_validation_status"] == "repaired"
        assert metadata["summary_repair_attempted"] is True
        assert metadata["summary_repair_prompt_version"] == "paper-summary-repair-v1"
        assert "one_line_takeaway" in metadata["summary_validation_error"]
    finally:
        db.close()


def test_backfill_job_create_list_get_tracks_budget_and_range_without_running_digest() -> None:
    reset_db()
    db = SessionLocal()
    try:
        digest_runs_before = db.query(DigestRun).count()
    finally:
        db.close()

    with TestClient(app) as client:
        created = client.post(
            "/backfill/jobs",
            json={
                "start_date": "2024-01-15",
                "end_date": "2024-01-17",
                "categories": ["cs.LG", " cs.AI "],
                "budget_usd": 1.25,
            },
        )

    assert created.status_code == 201
    payload = created.json()
    assert payload["status"] == "pending"
    assert payload["start_date"] == "2024-01-15"
    assert payload["end_date"] == "2024-01-17"
    assert payload["category_scope"] == ["cs.LG", "cs.AI"]
    assert payload["budget_usd"] == 1.25
    assert payload["estimated_cost_usd"] == 0
    assert payload["budget_remaining_usd"] == 1.25
    assert payload["total_days"] == 3
    assert payload["completed_days"] == 0
    assert payload["failed_days"] == 0
    assert payload["papers_fetched"] == 0
    assert payload["papers_new"] == 0
    assert payload["papers_summarized"] == 0
    assert payload["error_message"] is None
    assert "not started automatically" in payload["message"]

    db = SessionLocal()
    try:
        assert db.query(DigestRun).count() == digest_runs_before
    finally:
        db.close()

    with TestClient(app) as client:
        listed = client.get("/backfill/jobs", params={"status": "pending"})
        detail = client.get(f"/backfill/jobs/{payload['id']}")

    assert listed.status_code == 200
    listed_payload = listed.json()
    assert listed_payload["total"] == 1
    assert listed_payload["items"][0]["id"] == payload["id"]
    assert listed_payload["items"][0]["message"] is None

    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["id"] == payload["id"]
    assert detail_payload["total_days"] == 3


def test_backfill_job_validation() -> None:
    reset_db()
    with TestClient(app) as client:
        reversed_range = client.post(
            "/backfill/jobs",
            json={"start_date": "2024-01-17", "end_date": "2024-01-15", "budget_usd": 1.0},
        )
        empty_categories = client.post(
            "/backfill/jobs",
            json={"start_date": "2024-01-15", "end_date": "2024-01-15", "category_scope": ["   "]},
        )
        invalid_status = client.get("/backfill/jobs", params={"status": "bogus"})
        missing = client.get("/backfill/jobs/999999")

    assert reversed_range.status_code == 422
    assert empty_categories.status_code == 400
    assert invalid_status.status_code == 422
    assert missing.status_code == 404


def test_backfill_job_run_drains_successfully(monkeypatch) -> None:
    reset_empty_db()
    calls = _patch_backfill_run_digest(
        monkeypatch,
        {
            "2024-01-15": {"papers_fetched": 2, "papers_new": 1, "papers_summarized": 1, "estimated_cost_usd": 0.01},
            "2024-01-16": {"papers_fetched": 3, "papers_new": 2, "papers_summarized": 2, "estimated_cost_usd": 0.02},
            "2024-01-17": {"papers_fetched": 1, "papers_new": 1, "papers_summarized": 1, "estimated_cost_usd": 0.03},
        },
    )

    with TestClient(app) as client:
        created = client.post(
            "/backfill/jobs",
            json={
                "start_date": "2024-01-15",
                "end_date": "2024-01-17",
                "category_scope": ["cs.LG"],
                "budget_usd": 1.0,
            },
        )
        first_step = client.post(f"/backfill/jobs/{created.json()['id']}/run")
        second_step = client.post(f"/backfill/jobs/{created.json()['id']}/run")
        drained = client.post(f"/backfill/jobs/{created.json()['id']}/run")

    assert first_step.status_code == 200
    assert first_step.json()["status"] == "running"
    assert first_step.json()["completed_days"] == 1
    assert first_step.json()["message"] == "Backfill job advanced one day."
    assert second_step.status_code == 200
    assert second_step.json()["status"] == "running"
    assert second_step.json()["completed_days"] == 2

    assert drained.status_code == 200
    payload = drained.json()
    assert payload["status"] == "success"
    assert payload["completed_days"] == 3
    assert payload["failed_days"] == 0
    assert payload["papers_fetched"] == 6
    assert payload["papers_new"] == 4
    assert payload["papers_summarized"] == 4
    assert payload["estimated_cost_usd"] == 0.06
    assert payload["budget_remaining_usd"] == 0.94
    assert payload["error_message"] is None
    assert payload["started_at"] is not None
    assert payload["completed_at"] is not None
    assert payload["message"] == "Backfill job completed."

    assert [call["target_date"].isoformat() for call in calls] == ["2024-01-15", "2024-01-16", "2024-01-17"]
    assert [call["category_scope"] for call in calls] == [["cs.LG"], ["cs.LG"], ["cs.LG"]]
    assert {call["backfill_job_id"] for call in calls} == {payload["id"]}

    db = SessionLocal()
    try:
        runs = db.query(DigestRun).filter(DigestRun.backfill_job_id == payload["id"]).all()
        assert len(runs) == 3
        assert {run.target_date.isoformat() for run in runs if run.target_date} == {
            "2024-01-15",
            "2024-01-16",
            "2024-01-17",
        }
    finally:
        db.close()


def test_backfill_job_run_records_failure_without_erasing_success(monkeypatch) -> None:
    reset_empty_db()
    calls = _patch_backfill_run_digest(
        monkeypatch,
        {
            "2024-01-15": {"papers_fetched": 2, "papers_new": 1, "papers_summarized": 1, "estimated_cost_usd": 0.01},
            "2024-01-16": {
                "status": "failed",
                "papers_fetched": 4,
                "papers_new": 2,
                "papers_summarized": 0,
                "error_message": "provider timeout",
            },
        },
    )

    with TestClient(app) as client:
        created = client.post(
            "/backfill/jobs",
            json={
                "start_date": "2024-01-15",
                "end_date": "2024-01-17",
                "category_scope": ["cs.LG"],
                "budget_usd": 1.0,
            },
        )
        first_step = client.post(f"/backfill/jobs/{created.json()['id']}/run")
        drained = client.post(f"/backfill/jobs/{created.json()['id']}/run")

    assert first_step.status_code == 200
    assert first_step.json()["status"] == "running"
    assert first_step.json()["completed_days"] == 1

    assert drained.status_code == 200
    payload = drained.json()
    assert payload["status"] == "failed"
    assert payload["completed_days"] == 1
    assert payload["failed_days"] == 1
    assert payload["papers_fetched"] == 6
    assert payload["papers_new"] == 3
    assert payload["papers_summarized"] == 1
    assert payload["estimated_cost_usd"] == 0.01
    assert "Digest failed for 2024-01-16: provider timeout" == payload["error_message"]
    assert [call["target_date"].isoformat() for call in calls] == ["2024-01-15", "2024-01-16"]

    db = SessionLocal()
    try:
        runs = db.query(DigestRun).filter(DigestRun.backfill_job_id == payload["id"]).all()
        assert len(runs) == 2
        statuses_by_date = {run.target_date.isoformat(): run.status for run in runs if run.target_date}
        assert statuses_by_date == {"2024-01-15": "success", "2024-01-16": "failed"}
    finally:
        db.close()

    retry_calls = _patch_backfill_run_digest(
        monkeypatch,
        {
            "2024-01-16": {"papers_fetched": 1, "papers_new": 1, "papers_summarized": 1, "estimated_cost_usd": 0.01},
            "2024-01-17": {"papers_fetched": 1, "papers_new": 1, "papers_summarized": 1, "estimated_cost_usd": 0.01},
        },
    )

    with TestClient(app) as client:
        retry_first = client.post(f"/backfill/jobs/{payload['id']}/run")
        retried = client.post(f"/backfill/jobs/{payload['id']}/run")

    assert retry_first.status_code == 200
    assert retry_first.json()["status"] == "running"
    assert retry_first.json()["completed_days"] == 2
    assert retried.status_code == 200
    retry_payload = retried.json()
    assert retry_payload["status"] == "success"
    assert retry_payload["completed_days"] == 3
    assert retry_payload["failed_days"] == 0
    assert [call["target_date"].isoformat() for call in retry_calls] == ["2024-01-16", "2024-01-17"]


def test_backfill_job_run_stops_before_next_date_when_budget_exhausted(monkeypatch) -> None:
    reset_empty_db()
    calls = _patch_backfill_run_digest(
        monkeypatch,
        {
            "2024-01-15": {"estimated_cost_usd": 0.6},
            "2024-01-16": {"estimated_cost_usd": 0.6},
            "2024-01-17": {"estimated_cost_usd": 0.6},
        },
    )

    with TestClient(app) as client:
        created = client.post(
            "/backfill/jobs",
            json={
                "start_date": "2024-01-15",
                "end_date": "2024-01-17",
                "category_scope": ["cs.LG"],
                "budget_usd": 1.0,
            },
        )
        first_step = client.post(f"/backfill/jobs/{created.json()['id']}/run")
        drained = client.post(f"/backfill/jobs/{created.json()['id']}/run")

    assert first_step.status_code == 200
    assert first_step.json()["status"] == "running"
    assert first_step.json()["completed_days"] == 1

    assert drained.status_code == 200
    payload = drained.json()
    assert payload["status"] == "budget_exhausted"
    assert payload["completed_days"] == 2
    assert payload["failed_days"] == 0
    assert payload["estimated_cost_usd"] == 1.2
    assert payload["budget_remaining_usd"] == 0
    assert payload["error_message"] == "Backfill budget exhausted before processing 2024-01-17."
    assert [call["target_date"].isoformat() for call in calls] == ["2024-01-15", "2024-01-16"]


def test_backfill_job_run_records_digest_budget_exhaustion(monkeypatch) -> None:
    reset_empty_db()
    calls = _patch_backfill_run_digest(
        monkeypatch,
        {
            "2024-01-15": {
                "status": "budget_exhausted",
                "papers_fetched": 2,
                "papers_new": 2,
                "papers_summarized": 1,
                "estimated_cost_usd": 0.25,
                "error_message": "LLM run budget reached before all shortlisted papers were summarized ($0.25).",
            },
        },
    )

    with TestClient(app) as client:
        created = client.post(
            "/backfill/jobs",
            json={
                "start_date": "2024-01-15",
                "end_date": "2024-01-16",
                "category_scope": ["cs.LG"],
                "budget_usd": 1.0,
            },
        )
        drained = client.post(f"/backfill/jobs/{created.json()['id']}/run")

    assert drained.status_code == 200
    payload = drained.json()
    assert payload["status"] == "budget_exhausted"
    assert payload["completed_days"] == 0
    assert payload["failed_days"] == 0
    assert payload["papers_fetched"] == 2
    assert payload["papers_new"] == 2
    assert payload["papers_summarized"] == 1
    assert payload["estimated_cost_usd"] == 0.25
    assert payload["error_message"].startswith("Digest budget exhausted for 2024-01-15:")
    assert "LLM run budget reached" in payload["error_message"]
    assert [call["target_date"].isoformat() for call in calls] == ["2024-01-15"]


def test_backfill_job_run_rejects_invalid_states(monkeypatch) -> None:
    reset_empty_db()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("run_digest should not be called for invalid backfill job states")

    monkeypatch.setattr(main, "run_digest", fail_if_called)

    db = SessionLocal()
    try:
        job_ids = {}
        for status_name in ["success", "canceled"]:
            job = BackfillJob(
                start_date=date(2024, 1, 15),
                end_date=date(2024, 1, 15),
                category_scope_json=json.dumps(["cs.LG"]),
                status=status_name,
                budget_usd=1.0,
                total_days=1,
            )
            db.add(job)
            db.flush()
            job_ids[status_name] = job.id
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        success = client.post(f"/backfill/jobs/{job_ids['success']}/run")
        canceled = client.post(f"/backfill/jobs/{job_ids['canceled']}/run")
        missing = client.post("/backfill/jobs/999999/run")

    assert success.status_code == 400
    assert success.json()["error"] == "Backfill job cannot run from success state"
    assert canceled.status_code == 400
    assert canceled.json()["error"] == "Backfill job cannot run from canceled state"
    assert missing.status_code == 404


def test_stats() -> None:
    reset_db()
    with TestClient(app) as client:
        response = client.get("/stats")

    assert response.status_code == 200
    stats = response.json()
    assert stats["papers_total"] == 8
    assert stats["categories"]["quant-ph"] == 2
    assert stats["llm_calls_total"] == 0
    assert stats["llm_tokens_total"] == 0
    assert stats["estimated_llm_cost_usd"] == 0


class FakeArxivClient:
    def __init__(self, _settings: Settings, fetched: dict[str, ArxivPaper]) -> None:
        self.fetched = fetched

    def fetch_recent(self, categories: list[str] | None = None) -> list[ArxivPaper]:
        return list(self.fetched.values())

    def fetch_for_date(self, target_date: date, categories: list[str] | None = None) -> list[ArxivPaper]:
        return list(self.fetched.values())


class CountingSummaryProvider:
    provider = "openai"
    model_name = "summary-test"

    def __init__(self) -> None:
        self.calls = 0

    def summarize(self, paper: ArxivPaper, full_text: str = "") -> dict:
        self.calls += 1
        return {
            "one_line_takeaway": f"Provider takeaway {self.calls}",
            "simple_summary": f"Provider summary for {paper.abstract}",
            "context": "Provider context",
            "what_is_new": "Provider novelty",
            "mechanism": "Provider mechanism",
            "evidence": "Provider evidence",
            "methodology_caveats": ["Provider caveat"],
            "meaningful_extensions": ["Provider extension"],
            "novelty_type": "method",
            "difficulty": "intermediate",
            "confidence": "medium",
            "read_this_if": "You want a tested summary.",
            "tags": ["cs.LG", "provider"],
            "vibe": "Provider vibe",
            "glossary": [{"term": "provider", "definition": "A test summary provider."}],
            "follow_up_questions": ["Does the cache work?"],
            "model_provider": self.provider,
            "model_name": self.model_name,
            "source_basis": "partial_full_text" if full_text else "abstract_only",
            "_llm_usage": {
                "provider": self.provider,
                "model_name": self.model_name,
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "estimated_cost_usd": 0.001,
            },
        }


class InvalidSummaryProvider:
    provider = "openai"
    model_name = "summary-test"

    def __init__(self) -> None:
        self.calls = 0

    def summarize(self, paper: ArxivPaper, full_text: str = "") -> dict:
        self.calls += 1
        return {
            "one_line_takeaway": 123,
            "simple_summary": "",
            "methodology_caveats": "not-a-list",
            "_llm_usage": {
                "prompt_tokens": 12,
                "completion_tokens": 4,
                "total_tokens": 16,
                "estimated_cost_usd": 0.002,
            },
        }


class RepairingSummaryProvider(InvalidSummaryProvider):
    def __init__(self) -> None:
        super().__init__()
        self.repairs = 0

    def repair_summary(
        self,
        paper: ArxivPaper,
        raw: object,
        validation_error: str,
        full_text: str = "",
    ) -> dict:
        self.repairs += 1
        assert validation_error
        assert isinstance(raw, dict)
        return {
            "one_line_takeaway": "Repaired provider takeaway",
            "simple_summary": f"Repaired provider summary for {paper.abstract}",
            "context": "Repaired provider context",
            "what_is_new": "Repaired provider novelty",
            "mechanism": "Repaired provider mechanism",
            "evidence": "Repaired provider evidence",
            "methodology_caveats": ["Repaired provider caveat"],
            "meaningful_extensions": ["Repaired provider extension"],
            "novelty_type": "method",
            "difficulty": "intermediate",
            "confidence": "medium",
            "read_this_if": "You want a repaired provider summary.",
            "tags": ["cs.LG", "provider", "repaired"],
            "vibe": "Repaired provider vibe",
            "glossary": [{"term": "repair", "definition": "A bounded validation retry."}],
            "follow_up_questions": ["Did repair preserve the source basis?"],
            "model_provider": self.provider,
            "model_name": self.model_name,
            "source_basis": "partial_full_text" if full_text else "abstract_only",
            "_llm_usage": {
                "provider": self.provider,
                "model_name": self.model_name,
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30,
                "estimated_cost_usd": 0.003,
            },
        }


def _patch_digest_dependencies(monkeypatch, fetched: dict[str, ArxivPaper], summarizer: object) -> None:
    monkeypatch.setattr(agent, "ArxivClient", lambda settings: FakeArxivClient(settings, fetched))
    monkeypatch.setattr(
        agent,
        "extract_full_text",
        lambda _pdf_url: ExtractedText(text="Extracted body", source_basis="partial_full_text"),
    )
    monkeypatch.setattr(agent, "get_summarizer", lambda _settings: summarizer)


def _patch_backfill_run_digest(monkeypatch, outcomes: dict[str, dict]) -> list[dict]:
    calls = []
    outcomes_by_date = {date.fromisoformat(target_date): outcome for target_date, outcome in outcomes.items()}

    def fake_run_digest(
        db,
        _settings,
        target_date=None,
        category_scope=None,
        backfill_job_id=None,
    ):
        if target_date is None:
            raise AssertionError("backfill run_digest calls must include target_date")
        outcome = outcomes_by_date[target_date]
        categories = list(category_scope or [])
        calls.append(
            {
                "target_date": target_date,
                "category_scope": categories,
                "backfill_job_id": backfill_job_id,
            }
        )
        run = DigestRun(
            backfill_job_id=backfill_job_id,
            target_date=target_date,
            category_scope_json=json.dumps(categories),
            status=outcome.get("status", "success"),
            papers_fetched=outcome.get("papers_fetched", 1),
            papers_new=outcome.get("papers_new", 1),
            papers_summarized=outcome.get("papers_summarized", 1),
            error_message=outcome.get("error_message"),
            completed_at=datetime.now(UTC),
            config_json=json.dumps(
                {
                    "categories": categories,
                    "target_date": target_date.isoformat(),
                    "backfill_job_id": backfill_job_id,
                }
            ),
        )
        db.add(run)
        db.flush()
        estimated_cost_usd = outcome.get("estimated_cost_usd", 0.0)
        if estimated_cost_usd:
            db.add(
                LLMCall(
                    digest_run_id=run.id,
                    task="paper_summary",
                    provider="mock",
                    model_name="mock-summary",
                    prompt_tokens=10,
                    completion_tokens=5,
                    total_tokens=15,
                    estimated_cost_usd=estimated_cost_usd,
                    metadata_json="{}",
                )
            )
        db.commit()
        db.refresh(run)
        return run

    monkeypatch.setattr(main, "run_digest", fake_run_digest)
    return calls


def _digest_test_settings() -> Settings:
    return Settings(
        llm_provider="openai",
        openai_api_key="test-key",
        openai_model="summary-test",
        arxiv_categories="cs.LG",
        top_n=1,
        llm_run_budget_usd=1.0,
        seed_on_empty=False,
        enable_scheduler=False,
    )


def _digest_test_paper(
    arxiv_id: str = "2606.99999",
    title: str = "Cacheable Summary Paper",
    abstract: str = "A cacheable summary paper.",
) -> ArxivPaper:
    published_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    return ArxivPaper(
        arxiv_id=arxiv_id,
        arxiv_version="v1",
        title=title,
        abstract=abstract,
        authors=["Ada Tester"],
        primary_category="cs.LG",
        categories=["cs.LG"],
        published_at=published_at,
        updated_at=published_at,
        arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        raw_metadata={"test": True},
    )
