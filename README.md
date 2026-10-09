# MCP Witness

**Turn recorded MCP tool calls into offline regression tests.**

[![CI](https://github.com/shyangar/mcp-witness/actions/workflows/ci.yml/badge.svg)](https://github.com/shyangar/mcp-witness/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

[中文说明](README.zh-CN.md) · [How checks work](docs/design.md) · [CI integration](docs/ci.md) · [Contributing](CONTRIBUTING.md)

An agent successfully calls `lookup_invoice({"invoice_id": "demo-001"})` today.
Tomorrow the server requires a `workspace` argument. The tool still exists, the
server starts, and its health check passes. Your saved workflow fails.

MCP Witness identifies the **specific previously valid call** rejected by the new
schema and gives CI a failing exit code. Changes without a concrete input witness
are marked **review**, so an empty test corpus never becomes a compatibility claim.

## Try it in one minute

Python 3.11 or newer. No account, model API key, inference calls, or running server
is needed for the offline checks. The project is an early alpha; install from this
repository (there is no claimed PyPI release).

```sh
git clone https://github.com/shyangar/mcp-witness.git
cd mcp-witness
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .

# Known-good catalog: exit 0.
mcp-witness check --baseline examples/baseline.json --candidate examples/baseline.json --cases examples/cases.json

# Breaking upgrade: exit 1 is the expected result.
mcp-witness check --baseline examples/baseline.json --candidate examples/breaking.json --cases examples/cases.json
```

The intentionally broken upgrade reports:

```text
MCP Witness: FAILED (fail on review)
1/3 recorded calls accepted; 2/2 baseline tools covered
2 breaking, 3 review, 0 info

[BREAKING] list_invoices: case.input_rejected case=list-pending
  A call accepted by the baseline is rejected by the candidate.
  keyword=enum at /status
[BREAKING] lookup_invoice: case.input_rejected case=lookup-existing
  A call accepted by the baseline is rejected by the candidate.
  keyword=required at <root>
```

## What you get

| Capability | What it does |
| --- | --- |
| Concrete regression witnesses | Validate each recorded call against the old and new input contracts; name the rejected case and constraint. |
| Conservative change review | Flag input/output schema, description, behavior hint and other metadata changes for review. |
| Coverage visibility | List baseline tools without samples; `--require-coverage` makes them review findings. |
| Offline by default | `snapshot`, `import-calls`, and `check` operate on local files. External schema references are rejected. |
| MCP discovery | Optional SDK transport captures a trusted stdio server's complete paginated tool catalog. It never calls tools. |
| CI reports | Text, JSON, Markdown and JUnit XML, with stable exit codes and no argument values in reports. |

## Use your own server

Capture a baseline from a server **you trust**. Starting a server executes its
code; discovery is not a sandbox. The SDK uses its default restricted environment;
it does not automatically forward arbitrary API credentials from your shell.

```sh
python -m pip install -e ".[capture]"
mcp-witness capture --output baseline.json -- python examples/invoice_server.py
mcp-witness capture --output candidate.json -- python examples/invoice_server.py --breaking
mcp-witness check --baseline baseline.json --candidate candidate.json --cases examples/cases.json
```

If your client already exports a complete `tools/list` result, use it directly or
normalize it into a fingerprinted snapshot:

```sh
mcp-witness snapshot tools-list.json --output baseline.json
```

Create a small corpus of sanitized successful calls. See
[examples/cases.json](examples/cases.json). A case has exactly `id`, `tool`, and
`arguments`:

```json
{
  "cases": [
    {
      "id": "lookup-existing",
      "tool": "lookup_invoice",
      "arguments": {"invoice_id": "demo-001"}
    }
  ]
}
```

You can also extract cases from MCP JSON-RPC `tools/call` requests in a JSON array,
single JSON object, or JSONL trace. Responses and other MCP messages are ignored;
malformed records cause an input error.

```sh
mcp-witness import-calls examples/calls.jsonl --output cases.local.json
```

**Imported arguments are copied verbatim.** Replace private data with synthetic
fixtures before committing them. Reports omit argument values, but tool names,
case IDs and property paths remain visible. Raw traces and `*.local.json` files
are ignored by the repository's Git configuration.

## CI policy

```sh
mcp-witness check --baseline baseline.json --candidate candidate.json --cases cases.json --require-coverage --format junit --output reports/mcp.xml
```

| Exit | Meaning |
| --- | --- |
| `0` | No finding meets the selected failure threshold. |
| `1` | A breaking or review finding blocks the selected policy. |
| `2` | Invalid corpus, unsupported schema, incomplete catalog, transport failure, or file error. |

Default `--fail-on review` fails on both review findings and witnessed breaks.
`--fail-on breaking` is an explicit weaker policy: only removed tools and rejected
known calls fail. It can pass despite an untested breaking change. An input corpus
that is invalid against the baseline exits `2`, not `1`.

Snapshots and imported corpora refuse overwrites unless `--force` is supplied.
Reports replace their output file, but cannot overwrite a check's input path.

## Boundaries

- This is **input contract replay**, not execution replay. It does not execute a
  recorded call, validate live output values, evaluate agent reasoning, or detect
  every behavioral or prompt-injection regression.
- Passing finite samples does not prove backward compatibility. Every schema
  change still requires review under the default policy, including additive ones.
- Draft 2020-12 JSON Schema is supported, including local JSON Pointer `$ref`
  references. Other dialects, external refs, `$id`, anchors and dynamic refs fail
  closed with exit `2`. `format` remains an annotation, not an enforced assertion.
- Schema comparisons preserve array order. Reordered enums or `required` arrays
  can therefore produce a harmless review finding; they do not become a witnessed
  break unless an actual call is rejected.
- The capture adapter supports **stdio only**. Streamable HTTP, live output
  assertions and other trace formats are on the [roadmap](ROADMAP.md).
- Inputs are bounded to 8 MiB and nesting depth 80, with 2,000 tools and 10,000
  cases. These limits do not make arbitrary schemas or server commands safe to run.

## Development

```sh
python -m pip install -e ".[dev,capture]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m build
```

Or use `uv sync --all-extras --locked` and prefix commands with `uv run`.
CI tests Linux, Windows and macOS, including an actual stdio MCP server round trip.
The sample invoice data is synthetic; it is not evidence of external adoption.

MIT licensed. Feedback is most useful as a **minimal sanitized failing call plus
old/new schemas**. See [CONTRIBUTING.md](CONTRIBUTING.md).
