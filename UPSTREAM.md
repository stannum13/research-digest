# Upstream Substrate

Marginalia uses PaperQA2 as the intended substrate for scientific document ingestion, retrieval, citation handling, grounded answering, and evaluation.

| Component | Pin |
| --- | --- |
| Upstream repository | `https://github.com/Future-House/paper-qa` |
| Upstream commit inspected | `d7675d7b7eddeb3535e8c260399c5bbeeb818c50` |
| PyPI package | `paper-qa==2026.3.18` |
| Integration mode | Normal dependency plus local adapter; no vendored fork |

The current repository does not vendor PaperQA2. Product-specific arXiv ingestion, saved-paper state, feedback, synthesis records, and UI code remain in this repo. Algorithmic changes for E001 should either be expressed as PaperQA2 configuration or isolated in a focused upstream branch before claiming a PaperQA2 pipeline result.

Current local integration is `backend/paperqa_adapter.py`, which converts Marginalia paper rows into citation-preserving document specs. The E001 smoke command validates that adapter boundary; it does not run the canonical PaperQA2 answer-quality evaluation.
