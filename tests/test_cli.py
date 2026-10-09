import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from mcp_witness.cli import main
from mcp_witness.data import InputError
from mcp_witness.importer import import_calls

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "examples/baseline.json"
BAD = ROOT / "examples/breaking.json"
CASES = ROOT / "examples/cases.json"


def args(candidate=BAD):
    return ["check", "--baseline", str(BASE), "--candidate", str(candidate), "--cases", str(CASES)]


@pytest.mark.parametrize("output_format", ["text", "json", "markdown", "junit"])
def test_cli_reports_regression_and_creates_report(tmp_path, output_format):
    destination = tmp_path / "reports" / f"result.{output_format}"
    assert main([*args(), "--format", output_format, "--output", str(destination)]) == 1
    report = destination.read_text(encoding="utf-8")
    assert "demo-001" not in report
    if output_format == "json":
        assert json.loads(report)["summary"]["cases_failed"] == 2
    elif output_format == "junit":
        root = ET.fromstring(report)
        assert int(root.attrib["failures"]) == 5
        assert int(root.attrib["tests"]) == 6
    else:
        assert "FAILED" in report


def test_cli_success_stdout(capsys):
    assert main(args(BASE)) == 0
    assert "3/3 recorded calls accepted" in capsys.readouterr().out


def test_report_cannot_overwrite_baseline(capsys):
    original = BASE.read_bytes()
    assert main([*args(), "--output", str(BASE)]) == 2
    assert "must not overwrite" in capsys.readouterr().err
    assert BASE.read_bytes() == original


def test_snapshot_write_overwrite_and_reload(tmp_path):
    destination = tmp_path / "snapshot.json"
    command = ["snapshot", str(BASE), "--output", str(destination)]
    assert main(command) == 0
    assert main(command) == 2
    assert main([*command, "--force"]) == 0
    assert (
        main(
            [
                "check",
                "--baseline",
                str(destination),
                "--candidate",
                str(destination),
                "--cases",
                str(CASES),
            ]
        )
        == 0
    )


def test_import_cannot_overwrite_input(tmp_path):
    trace = tmp_path / "trace.json"
    trace.write_text("{}", encoding="utf-8")
    assert main(["import-calls", str(trace), "--output", str(trace), "--force"]) == 2
    assert trace.read_text() == "{}"


def test_missing_file_returns_input_error(tmp_path, capsys):
    assert main(["snapshot", str(tmp_path / "missing"), "--output", str(tmp_path / "out")]) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_import_jsonl_preserves_arguments_and_omits_responses(tmp_path):
    output = tmp_path / "cases.json"
    assert main(["import-calls", str(ROOT / "examples/calls.jsonl"), "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert len(result["cases"]) == 2
    assert result["cases"][0]["arguments"] == {"invoice_id": "demo-001"}
    assert result["cases"][0]["id"] == "call-0002"


@pytest.mark.parametrize("wrapping", ["single", "array", "jsonl"])
def test_import_formats(wrapping):
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "ping"}}
    if wrapping == "array":
        text = json.dumps([request])
    elif wrapping == "jsonl":
        text = json.dumps(request) + "\n" + json.dumps(request)
    else:
        text = json.dumps(request)
    result = import_calls(text)
    assert result["cases"][0]["arguments"] == {}
    assert len(result["cases"]) == (2 if wrapping == "jsonl" else 1)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "[]",
        '{"method":"tools/call"}',
        '{"jsonrpc":"2.0","method":"tools/call","params":{}}',
        '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"x","arguments":[]}}',
        '{"jsonrpc":"2.0","id":true,"method":"tools/call","params":{"name":"x"}}',
        '{"jsonrpc":"2.0","id":1,"method":"ping"}\n{broken}',
    ],
)
def test_import_does_not_skip_malformed_records(text):
    with pytest.raises(InputError):
        import_calls(text)


def test_reports_escape_hostile_identifiers(tmp_path):
    baseline = tmp_path / "base.json"
    candidate = tmp_path / "next.json"
    samples = tmp_path / "cases.json"
    name = "<script>\x1b[31m|tool"
    baseline.write_text(json.dumps({"tools": [{"name": name, "inputSchema": {}}]}))
    candidate.write_text('{"tools": []}')
    samples.write_text(json.dumps({"cases": [{"id": name, "tool": name, "arguments": {}}]}))
    command = [
        "check",
        "--baseline",
        str(baseline),
        "--candidate",
        str(candidate),
        "--cases",
        str(samples),
    ]
    xml_output = tmp_path / "out.xml"
    assert main([*command, "--format", "junit", "--output", str(xml_output)]) == 1
    ET.fromstring(xml_output.read_text())
    md_output = tmp_path / "out.md"
    assert main([*command, "--format", "markdown", "--output", str(md_output)]) == 1
    assert "<script>" not in md_output.read_text(encoding="utf-8")
    assert "\x1b" not in md_output.read_text(encoding="utf-8")


def test_module_entrypoint_has_real_exit_code():
    result = subprocess.run(
        [sys.executable, "-m", "mcp_witness", *args()], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "case.input_rejected" in result.stdout


@pytest.mark.parametrize(
    "bad_record",
    [
        {"jsonrpc": "2.0"},
        {"jsonrpc": "2.0", "method": 42},
        {"jsonrpc": "2.0", "method": "ping", "params": []},
        {"jsonrpc": "2.0", "method": "ping", "result": {}},
    ],
)
def test_bad_record_alongside_good_call_is_not_ignored(bad_record):
    good = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "ping"}}
    with pytest.raises(InputError):
        import_calls(json.dumps([bad_record, good]))
