"""Distinguish observed regressions from changes that still need human review."""

from __future__ import annotations

from typing import Any

from mcp_witness.data import InputError, canonical, validation_errors

LEVELS = {"info": 0, "review": 1, "breaking": 2}
HINT_DEFAULTS = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": True,
}


def blocks(severity: str, fail_on: str) -> bool:
    return LEVELS[severity] >= LEVELS[fail_on]


def check(
    baseline: dict,
    candidate: dict,
    corpus: list[dict],
    *,
    fail_on: str = "review",
    require_coverage: bool = False,
) -> dict:
    old = {tool["name"]: tool for tool in baseline["tools"]}
    new = {tool["name"]: tool for tool in candidate["tools"]}
    findings: list[dict[str, Any]] = []
    checks: list[dict] = []

    def add(code: str, severity: str, tool: str, message: str, **evidence: Any) -> None:
        findings.append(
            {
                "code": code,
                "severity": severity,
                "tool": tool,
                "message": message,
                **evidence,
            }
        )

    # A fixture that never worked is a setup problem, not evidence of a regression.
    for case in corpus:
        if case["tool"] not in old:
            raise InputError("Corpus references a tool absent from the baseline")
        if validation_errors(old[case["tool"]]["inputSchema"], case["arguments"]):
            raise InputError(
                "Corpus contains arguments rejected by the baseline; repair the fixture"
            )

    for name in sorted(old.keys() - new.keys()):
        add("tool.removed", "breaking", name, "A previously available tool was removed.")
    for name in sorted(new.keys() - old.keys()):
        add("tool.added", "info", name, "A new tool was added; existing calls do not cover it.")
    for name in sorted(old.keys() & new.keys()):
        before, after = old[name], new[name]
        for field in ("inputSchema", "outputSchema"):
            if canonical(before.get(field)) != canonical(after.get(field)):
                add(
                    "schema.input_changed" if field == "inputSchema" else "schema.output_changed",
                    "review",
                    name,
                    "Schema changed. Finite input samples cannot prove general compatibility."
                    if field == "inputSchema"
                    else "Output contract changed. Input replay does not validate output behavior.",
                    field=field,
                )
        if before.get("description") != after.get("description"):
            add(
                "tool.description_changed",
                "review",
                name,
                "Description changed; review how an agent may select or use this tool.",
            )
        left, right = before.get("annotations", {}), after.get("annotations", {})
        for hint, default in HINT_DEFAULTS.items():
            if left.get(hint, default) != right.get(hint, default):
                add(
                    "tool.behavior_changed",
                    "review",
                    name,
                    "A declared behavior hint changed; hints are not authorization guarantees.",
                    field=hint,
                    before=left.get(hint, default),
                    after=right.get(hint, default),
                )
        left_extra = {k: v for k, v in left.items() if k not in HINT_DEFAULTS}
        right_extra = {k: v for k, v in right.items() if k not in HINT_DEFAULTS}
        if canonical(left_extra) != canonical(right_extra):
            add("tool.annotations_changed", "review", name, "Additional tool annotations changed.")
        known = {"name", "description", "inputSchema", "outputSchema", "annotations"}
        before_extra = {k: v for k, v in before.items() if k not in known}
        after_extra = {k: v for k, v in after.items() if k not in known}
        if canonical(before_extra) != canonical(after_extra):
            add(
                "tool.metadata_changed",
                "review",
                name,
                "Other tool metadata changed; inspect the snapshot diff.",
            )

    for case in sorted(corpus, key=lambda item: item["id"]):
        name = case["tool"]
        if name not in new:
            checks.append({"id": case["id"], "tool": name, "status": "failed"})
            continue
        errors = validation_errors(new[name]["inputSchema"], case["arguments"])
        checks.append({"id": case["id"], "tool": name, "status": "failed" if errors else "passed"})
        if errors:
            add(
                "case.input_rejected",
                "breaking",
                name,
                "A call accepted by the baseline is rejected by the candidate.",
                case_id=case["id"],
                errors=errors,
            )

    covered = {case["tool"] for case in corpus}
    uncovered = sorted(old.keys() - covered)
    for name in uncovered:
        add(
            "coverage.missing",
            "review" if require_coverage else "info",
            name,
            "No recorded input case covers this baseline tool.",
        )
    findings.sort(
        key=lambda f: (-LEVELS[f["severity"]], f["tool"], f["code"], f.get("case_id", ""))
    )
    counts = {level: sum(f["severity"] == level for f in findings) for level in LEVELS}
    failed = any(blocks(f["severity"], fail_on) for f in findings)
    return {
        "formatVersion": 1,
        "status": "failed" if failed else "passed",
        "policy": {"fail_on": fail_on, "require_coverage": require_coverage},
        "baseline_sha256": baseline["sha256"],
        "candidate_sha256": candidate["sha256"],
        "summary": {
            **counts,
            "cases": len(checks),
            "cases_passed": sum(case["status"] == "passed" for case in checks),
            "cases_failed": sum(case["status"] == "failed" for case in checks),
            "baseline_tools": len(old),
            "covered_tools": len(covered),
            "uncovered_tools": uncovered,
        },
        "findings": findings,
        "cases": checks,
    }
