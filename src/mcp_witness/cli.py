"""CLI entrypoint with stable 0/pass, 1/policy failure, 2/input failure exits."""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
from pathlib import Path

from mcp_witness import __version__
from mcp_witness.capture import capture
from mcp_witness.check import check
from mcp_witness.data import (
    InputError,
    cases,
    catalog,
    read_json,
    read_text,
    write_json,
    write_text,
)
from mcp_witness.importer import import_calls
from mcp_witness.report import render


def _destination(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true", help="Replace an existing output file")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Offline MCP contract regression tests with call evidence"
    )
    root.add_argument("--version", action="version", version=f"mcp-witness {__version__}")
    commands = root.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser(
        "snapshot", help="Validate and canonicalize a complete tools/list export"
    )
    snapshot.add_argument("input", type=Path)
    _destination(snapshot)
    discover = commands.add_parser("capture", help="Discover a trusted stdio server's tool catalog")
    _destination(discover)
    discover.add_argument("--timeout", type=float, default=30)
    discover.add_argument("server_command", nargs=argparse.REMAINDER)
    ingest = commands.add_parser(
        "import-calls", help="Extract input cases from MCP JSON/JSONL traces"
    )
    ingest.add_argument("input", type=Path)
    _destination(ingest)
    verify = commands.add_parser(
        "check", help="Compare catalogs and replay recorded input validation"
    )
    verify.add_argument("--baseline", type=Path, required=True)
    verify.add_argument("--candidate", type=Path, required=True)
    verify.add_argument("--cases", type=Path, required=True)
    verify.add_argument("--fail-on", choices=("review", "breaking"), default="review")
    verify.add_argument(
        "--require-coverage",
        action="store_true",
        help="Mark baseline tools without cases as review findings",
    )
    verify.add_argument("--format", choices=("text", "json", "markdown", "junit"), default="text")
    verify.add_argument("--output", type=Path, help="Write report to this file instead of stdout")
    return root


def main(argv: list[str] | None = None) -> int:
    # Windows terminals may not encode every valid Unicode tool/case name.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    args = parser().parse_args(argv)
    try:
        if args.command in {"snapshot", "import-calls"}:
            if args.input.resolve() == args.output.resolve():
                raise InputError("Input and output must be different files")
            value = (
                catalog(read_json(args.input))
                if args.command == "snapshot"
                else import_calls(read_text(args.input))
            )
            write_json(args.output, value, force=args.force)
            print(
                "Snapshot written."
                if args.command == "snapshot"
                else "Cases written. Arguments are copied verbatim; sanitize before sharing.",
                file=sys.stderr,
            )
        elif args.command == "capture":
            command = args.server_command
            if command and command[0] == "--":
                command = command[1:]
            if not math.isfinite(args.timeout) or args.timeout <= 0 or args.timeout > 300:
                raise InputError("Timeout must be greater than 0 and at most 300 seconds")
            if args.output.exists() and not args.force:
                raise InputError("Output exists; use --force to replace it")
            snapshot = asyncio.run(capture(command, args.timeout))
            write_json(args.output, snapshot, force=args.force)
            print("Snapshot written. No tool calls were made.", file=sys.stderr)
        else:
            if args.output and args.output.resolve() in {
                args.baseline.resolve(),
                args.candidate.resolve(),
                args.cases.resolve(),
            }:
                raise InputError("Report output must not overwrite an input file")
            report = check(
                catalog(read_json(args.baseline)),
                catalog(read_json(args.candidate)),
                cases(read_json(args.cases)),
                fail_on=args.fail_on,
                require_coverage=args.require_coverage,
            )
            text = render(report, args.format)
            if args.output:
                write_text(args.output, text, force=True)
            else:
                sys.stdout.write(text)
            return 1 if report["status"] == "failed" else 0
        return 0
    except InputError as exc:
        print(f"mcp-witness: {exc}", file=sys.stderr)
        return 2
    except OSError:
        print(
            "mcp-witness: file or process operation failed; check paths and permissions",
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        print("mcp-witness: interrupted", file=sys.stderr)
        return 130
