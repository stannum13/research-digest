# Provider Setup and Cost Controls

Marginalia is useful without paid provider keys. Seed data and deterministic fallback behavior keep the app explorable, while live summaries and provider-backed synthesis require explicit credentials.

## Modes

| Mode | Use when | Configuration |
| --- | --- | --- |
| No key / mock | Local development, frontend work, smoke tests | Leave provider API keys empty |
| Z.AI / GLM | Low-cost paper summaries or synthesis checks | `LLM_PROVIDER=zai` plus `ZAI_API_KEY` |
| OpenAI | Alternative provider comparison | `LLM_PROVIDER=openai` plus `OPENAI_API_KEY` |

Example live setup:

```env
LLM_PROVIDER=zai
ZAI_API_KEY=your_zai_key
ZAI_SYNTHESIS_MODEL=glm-5.2
ZAI_CLASSIFIER_MODEL=glm-4.7-flashx
LLM_RUN_BUDGET_USD=2.0
```

Check provider pricing before long runs. Public model pricing and availability can change independently of this repository.

## Spend Boundaries

`LLM_RUN_BUDGET_USD` caps a single digest run. When the cap is reached, the run status becomes `budget_exhausted` instead of `success`.

Suggested starting caps:

| Workflow | Cap | Reason |
| --- | ---: | --- |
| Credential smoke | `$0.25` | Confirms live credentials without summarizing a large shortlist |
| Daily digest | `$1.00-$2.00` | Covers a small ranked shortlist |
| Manual research date | `$2.00-$5.00` | Allows a deliberately chosen date/category window |
| Backfill job | Start at `$1.00` | Backfills should be drained gradually through job status |

Set `LLM_RUN_BUDGET_USD=0` only when you intentionally want no cap.

## Operational Rules

- Keep provider keys out of `.env.example`, Docker build args, frontend `VITE_*` variables, screenshots, and docs.
- Run with no provider key for UI and API development.
- Use small `TOP_N` and `FULL_TEXT_TOP_K` values while testing live credentials.
- Prefer one date/category window before running a range backfill.
- Inspect `/stats` and `GET /digest/runs/{run_id}` before increasing budgets.
- Keep selected-paper synthesis source-linked; speculative output should be marked as speculation.

## Summary Validation and Repair

Live provider summaries are validated against the `PaperBreakdown` schema before storage. If validation fails and the configured provider supports repair, the backend makes one bounded repair call using `paper-summary-repair-v1`.

Repair metadata is stored on the associated `llm_calls` row:

- `summary_validation_status`: `valid`, `repaired`, or `fallback`
- `summary_validation_error`
- `summary_repair_attempted`
- `summary_repair_prompt_version`
- `summary_repair_error`

If repair fails, the backend stores a deterministic fallback summary and does not cache it. Successful repairs are cacheable and include the combined token/cost estimate for the original provider call plus repair.

## Accounting Surfaces

```txt
GET /stats
GET /digest/runs/{run_id}
```

Paper summaries use task `paper_summary`. Provider-backed selected-paper synthesis uses task `synthesis` and records the synthesis mode, source paper IDs, validation status, tokens, and estimated spend when provider usage metadata is available.
