import json
import sys
from pathlib import Path

import pytest

from mcp_witness.cli import main

pytest.importorskip("mcp")
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/protocol_server.py"


def test_real_sdk_server_end_to_end(tmp_path):
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    server = [sys.executable, str(ROOT / "examples/invoice_server.py")]
    assert main(["capture", "--output", str(old), "--", *server]) == 0
    assert main(["capture", "--output", str(new), "--", *server, "--breaking"]) == 0
    report = tmp_path / "report.json"
    assert (
        main(
            [
                "check",
                "--baseline",
                str(old),
                "--candidate",
                str(new),
                "--cases",
                str(ROOT / "examples/cases.json"),
                "--format",
                "json",
                "--output",
                str(report),
            ]
        )
        == 1
    )
    assert json.loads(report.read_text())["summary"]["cases_failed"] == 2


def test_capture_collects_every_page(tmp_path):
    target = tmp_path / "snapshot.json"
    assert (
        main(["capture", "--output", str(target), "--", sys.executable, str(FIXTURE), "normal"])
        == 0
    )
    assert [t["name"] for t in json.loads(target.read_text())["tools"]] == ["first", "second"]


@pytest.mark.parametrize("mode", ["repeated-cursor", "crash", "timeout"])
def test_capture_failures_do_not_write_a_snapshot(tmp_path, capsys, mode):
    target = tmp_path / "out.json"
    timeout = "0.4" if mode == "timeout" else "10"
    assert (
        main(
            [
                "capture",
                "--output",
                str(target),
                "--timeout",
                timeout,
                "--",
                sys.executable,
                str(FIXTURE),
                mode,
            ]
        )
        == 2
    )
    assert not target.exists()
    output = capsys.readouterr()
    assert "PRIVATE_SERVER_STDERR" not in output.err
    assert "Traceback" not in output.err


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf", "301"])
def test_capture_invalid_timeout(tmp_path, timeout):
    assert (
        main(
            ["capture", "--output", str(tmp_path / "unused"), "--timeout", timeout, "--", "unused"]
        )
        == 2
    )


def test_capture_requires_explicit_command(tmp_path):
    assert main(["capture", "--output", str(tmp_path / "unused")]) == 2


def test_capture_existing_baseline_does_not_start_process(tmp_path):
    target = tmp_path / "baseline.json"
    target.write_text("keep me")
    assert main(["capture", "--output", str(target), "--", "does-not-exist"]) == 2
    assert target.read_text() == "keep me"
