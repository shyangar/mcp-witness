"""Portable CI reports. Argument values and raw schema messages are never rendered."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

from mcp_witness.check import blocks


def _safe(value: object) -> str:
    return re.sub(r"[\x00-\x1f\x7f-\x9f\ud800-\udfff\ufffe\uffff]", "?", str(value))


def render_text(report: dict) -> str:
    summary = report["summary"]
    lines = [
        f"MCP Witness: {report['status'].upper()} (fail on {report['policy']['fail_on']})",
        f"{summary['cases_passed']}/{summary['cases']} recorded calls accepted; "
        f"{summary['covered_tools']}/{summary['baseline_tools']} baseline tools covered",
        f"{summary['breaking']} breaking, {summary['review']} review, {summary['info']} info",
        "",
    ]
    for finding in report["findings"]:
        witness = f" case={_safe(finding['case_id'])}" if "case_id" in finding else ""
        lines.append(
            f"[{finding['severity'].upper()}] {_safe(finding['tool'])}: "
            f"{finding['code']}{witness}\n  {finding['message']}"
        )
        for error in finding.get("errors", []):
            location = (
                "/"
                + "/".join(
                    str(part).replace("~", "~0").replace("/", "~1")
                    for part in error["instance_path"]
                )
                if error["instance_path"]
                else "<root>"
            )
            lines.append(f"  keyword={_safe(error['keyword'])} at {_safe(location)}")
    lines.append(
        "\nOnly recorded inputs were validated. "
        "Tool behavior and general compatibility are unproven."
    )
    return "\n".join(lines) + "\n"


def _md(value: object) -> str:
    text = _safe(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for char in ("\\", "|", "`", "*", "_", "[", "]"):
        text = text.replace(char, "\\" + char)
    return text


def render_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        f"## MCP Witness: {report['status'].upper()}",
        "",
        f"**{s['cases_passed']}/{s['cases']}** recorded calls accepted. "
        f"**{s['covered_tools']}/{s['baseline_tools']}** baseline tools covered.",
        "",
        f"Policy: fail on **{report['policy']['fail_on']}**. "
        f"Findings: {s['breaking']} breaking, {s['review']} review, {s['info']} info.",
        "",
        "| Severity | Tool | Finding | Witness |",
        "| --- | --- | --- | --- |",
    ]
    for finding in report["findings"]:
        lines.append(
            f"| {finding['severity']} | {_md(finding['tool'])} | "
            f"{finding['code']} | {_md(finding.get('case_id', '—'))} |"
        )
    lines.extend(
        ["", "Recorded input checks do not prove tool behavior or general compatibility.", ""]
    )
    return "\n".join(lines)


def render_junit(report: dict) -> str:
    suite = ET.Element("testsuite", name="mcp-witness")
    failures = 0
    for case in report["cases"]:
        item = ET.SubElement(
            suite, "testcase", name=_safe(case["id"]), classname=_safe(case["tool"])
        )
        if case["status"] == "failed":
            ET.SubElement(item, "failure", message="Previously valid tool call no longer accepted")
            failures += 1
    for index, finding in enumerate(report["findings"], 1):
        if finding["code"] == "case.input_rejected":
            continue  # Already represented by the concrete test case.
        item = ET.SubElement(
            suite, "testcase", name=f"{finding['code']}.{index}", classname=_safe(finding["tool"])
        )
        if blocks(finding["severity"], report["policy"]["fail_on"]):
            ET.SubElement(item, "failure", message=finding["message"])
            failures += 1
        else:
            ET.SubElement(item, "system-out").text = finding["message"]
    suite.set("tests", str(len(suite)))
    suite.set("failures", str(failures))
    suite.set("errors", "0")
    return ET.tostring(suite, encoding="unicode", xml_declaration=True) + "\n"


def render(report: dict, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if output_format == "markdown":
        return render_markdown(report)
    if output_format == "junit":
        return render_junit(report)
    return render_text(report)
