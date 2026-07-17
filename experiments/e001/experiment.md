# E001: Budget-Aware Scientific Retrieval

## Status

Preregistered with adapter smoke coverage. The canonical PaperQA2 evaluation has not run yet, so this repository does not claim an answer-quality or citation-support improvement.

## Question

Can a small reranker plus adaptive evidence stopping reduce retrieval and synthesis cost while preserving PaperQA2 answer quality and citation support?

## Hypothesis

The treatment should materially reduce retrieval calls, token use, latency, and estimated cost while staying within a predeclared tolerance on PaperQA2 citation support and answer quality.

## Upstream Baseline

- Default PaperQA2 retrieval and answer pipeline pinned in `UPSTREAM.md`.
- Fixed top-k retrieval at several budgets.
- Large-model reranking without adaptive stopping.

## Treatment

- A pinned small reranker.
- A stopping rule based on evidence coverage, redundancy, and uncertainty.
- A fixed maximum budget per question.

## Controls

- Reranker only, without adaptive stopping.
- Adaptive stopping with the default reranker.
- Randomly truncated evidence.
- Abstract-only versus full-text subsets.

## Metrics

- Official PaperQA2 answer-quality and citation-support metrics.
- Retrieval calls, tokens, latency, and estimated cost.
- Evidence redundancy and source diversity.
- Failure rate split by abstract-only and full-text availability.

## Fixed Variables

- Upstream PaperQA2 version and commit.
- Evaluation task set.
- Model/provider configuration.
- Question order and random seed.
- Maximum retrieval and answer budget.

## Promotion Rule

Promote the treatment only if it reduces cost materially while answer quality and citation support remain inside the tolerance declared in the canonical config. If performance fails on a scientific subdomain, publish that boundary instead of hiding it.

## Artifact Chain

```text
config -> raw question records -> deterministic summary -> table/figure -> README statement
```

The current smoke command produces adapter-boundary artifacts only:

```bash
scripts/reproduce_e001.sh experiments/e001/configs/smoke.json
```

The canonical config is checked in but marked not runnable until the official PaperQA2 evaluation task, model credentials, and budget are selected.
