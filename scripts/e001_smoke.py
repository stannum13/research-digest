from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from paperqa_adapter import paper_to_document_spec, paperqa2_importable  # noqa: E402


def main() -> int:
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "experiments/e001/configs/smoke.json"
    if not config_path.is_absolute():
        config_path = REPO_ROOT / config_path
    config = json.loads(config_path.read_text())
    if config.get("mode") == "canonical" and not config.get("enabled", True):
        print(f"Canonical E001 is disabled: {config.get('blocked_reason', 'no reason recorded')}", file=sys.stderr)
        return 2

    result_dir = REPO_ROOT / "results/e001"
    result_dir.mkdir(parents=True, exist_ok=True)

    paper = SimpleNamespace(
        arxiv_id="2607.00001",
        arxiv_version="v1",
        title="Budget-Aware Scientific Retrieval Smoke Fixture",
        abstract="This fixture validates citation-preserving conversion before PaperQA2 evaluation runs.",
        authors_json=json.dumps(["Marginalia Fixture"]),
        primary_category="cs.IR",
        categories_json=json.dumps(["cs.IR"]),
        published_at=datetime(2026, 7, 17, tzinfo=UTC),
        updated_at=datetime(2026, 7, 17, tzinfo=UTC),
        arxiv_url="https://arxiv.org/abs/2607.00001",
        pdf_url="https://arxiv.org/pdf/2607.00001",
    )
    spec = paper_to_document_spec(paper)
    spec_payload = {
        "docname": spec.docname,
        "citation": spec.citation,
        "text_sha256": hashlib.sha256(spec.text.encode("utf-8")).hexdigest(),
        "metadata": spec.metadata,
    }

    summary = {
        "experiment_id": config["experiment_id"],
        "mode": config["mode"],
        "status": "adapter_smoke_passed",
        "canonical_quality_result": False,
        "paperqa2_importable": paperqa2_importable(),
        "records_checked": 1,
        "official_answer_quality": None,
        "official_citation_support": None,
        "estimated_cost_usd": 0.0,
        "notes": [
            "Smoke output validates Marginalia-to-PaperQA2 document shaping only.",
            "It is not a PaperQA2 answer-quality or citation-support result.",
        ],
    }

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "config_path": str(config_path.relative_to(REPO_ROOT)),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "upstream": config["upstream"],
        "artifacts": {
            "summary_json": "results/e001/summary.json",
            "summary_csv": "results/e001/summary.csv",
            "figure_svg": "results/e001/figure.svg",
        },
        "smoke_record": spec_payload,
    }

    (result_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (result_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    with (result_dir / "summary.csv").open("w", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "experiment_id",
                "mode",
                "status",
                "canonical_quality_result",
                "paperqa2_importable",
                "records_checked",
                "estimated_cost_usd",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow({field: summary[field] for field in writer.fieldnames})

    figure = """<svg xmlns="http://www.w3.org/2000/svg" width="760" height="220" viewBox="0 0 760 220" role="img" aria-labelledby="title desc">
  <title id="title">E001 smoke status</title>
  <desc id="desc">Adapter smoke passed; canonical PaperQA2 quality evaluation has not run.</desc>
  <rect width="760" height="220" fill="#fffaf3"/>
  <rect x="32" y="32" width="696" height="156" fill="#f0e7db" stroke="#c8b8a8"/>
  <text x="56" y="82" font-family="monospace" font-size="20" fill="#2f2a25">E001 smoke: adapter_smoke_passed</text>
  <text x="56" y="122" font-family="monospace" font-size="15" fill="#5f564e">Records checked: 1 Marginalia paper document</text>
  <text x="56" y="152" font-family="monospace" font-size="15" fill="#8a4f43">Canonical PaperQA2 quality result: not run</text>
</svg>
"""
    (result_dir / "figure.svg").write_text(figure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
