from __future__ import annotations

SYNTHESIS_SECTIONS = (
    "argument_map",
    "contradictions",
    "evidence_matrix",
    "open_questions",
    "extension_ideas",
    "replication_or_ablation_plan",
    "caveats",
)


def audit_synthesis_source_refs(data: dict[str, object], source_paper_ids: list[int]) -> list[str]:
    issues: list[str] = []
    allowed = set(source_paper_ids)

    for section in SYNTHESIS_SECTIONS:
        entries = data.get(section)
        if not isinstance(entries, list):
            issues.append(f"{section} must be a list.")
            continue

        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                issues.append(f"{section}[{index}] must be an object.")
                continue

            refs = entry.get("source_paper_ids")
            speculative = entry.get("speculative") is True
            if speculative and (refs is None or refs == []):
                entry["source_paper_ids"] = []
                continue

            if not isinstance(refs, list) or not refs:
                issues.append(f"{section}[{index}] is missing source_paper_ids.")
                continue

            try:
                normalized_refs = [int(ref) for ref in refs]
            except (TypeError, ValueError):
                issues.append(f"{section}[{index}] has non-integer source_paper_ids.")
                continue

            if not set(normalized_refs).issubset(allowed):
                issues.append(f"{section}[{index}] references papers outside the selection.")
                continue

            entry["source_paper_ids"] = normalized_refs

    return issues


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
