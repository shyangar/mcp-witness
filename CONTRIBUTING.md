# Contributing

The most useful contribution is a small real-world contract failure that can be
reproduced with synthetic data. File a bug with the old tool definition, candidate
definition, one input case, and the expected classification. Please do not attach
production traces, credentials, or customer data.

## Development setup

```sh
git clone https://github.com/shyangar/mcp-witness.git
cd mcp-witness
uv sync --all-extras --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -m build
```

Without uv, create a virtual environment and install `.[dev,capture]` with pip.
The capture tests use a real local FastMCP server and a protocol fixture; there is
no external service, API key or paid inference requirement. Without the optional
MCP extra, capture integration tests are skipped explicitly.

## Implementation guidelines

- Separate observed input rejection from changes requiring review. A passing
  sample corpus is not proof of general compatibility.
- Invalid baselines, incomplete pagination and unsupported schemas must exit `2`.
- Do not put argument values or raw third-party exception messages into reports.
- Use the MCP SDK for transport behavior; do not add a second protocol stack.
- Changes to behavior need focused tests. Keep docs and examples aligned with the
  actual CLI. Add dependencies only when they solve a demonstrated need.
- Keep report output deterministic; avoid timestamps, absolute workspace paths,
  random IDs, and environment-specific metadata in snapshots.

## Review and releases

Small pull requests are easier to assess. Describe the concrete before/after
behavior and relevant validation. A maintainer reviews a passing CI run before
tagging a release. Versions before 1.0 may change report schemas or CLI behavior;
the changelog will identify changes. No release or response-time SLA is promised.

Contributions are provided under the repository's MIT license. Be respectful,
address the technical issue, and do not post private information about others.
