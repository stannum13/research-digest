# Limitations

## Evidence Status

- E001 has a reproducible adapter smoke artifact, not a PaperQA2 answer-quality result.
- `results/e001/summary.*` records smoke status only. It must not be read as citation-support, answer-quality, or cost-frontier evidence.
- The canonical PaperQA2 evaluation remains blocked until the task set, credentials, budget, and quality tolerances are selected before running.

## Data Limits

- Seed data is synthetic but realistic enough for UI and API smoke testing.
- Live arXiv records vary by date, category, and full-text availability.
- Abstract-only records are weaker evidence than full-text records and should be split in any canonical analysis.

## Model and Provider Limits

- Provider pricing and model availability can change independently of this repository.
- Cost accounting uses provider-reported tokens when available and configured price tables; it is an estimate, not a bill.
- No-provider mode is deterministic and useful for development, but it is not a substitute for live synthesis evaluation.

## Product Limits

- The local product supports briefings, saved papers, feedback, search, classification, cost accounting, and selected-paper synthesis.
- Non-canonical exploratory diagram, relation, and note workflows were removed from the public main path.
- Search currently uses stored metadata and deterministic labels; PaperQA2 is the intended full scientific retrieval substrate for E001.

## External Validity

- A positive E001 result would apply only to the selected scientific QA task set, model/provider configuration, document availability, and budget.
- Subdomain failures should be reported directly rather than averaged away.
- Any treatment that only changes configuration, without a distinguishable reranking or stopping policy, should not be promoted as a method result.
