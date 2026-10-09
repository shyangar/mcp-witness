# Changelog

## 0.1.0 — 2026-10-09

Initial alpha release.

- Replay known MCP input calls against old and candidate JSON Schema contracts.
- Report removed tools, witnessed invalid calls, schema and metadata changes,
  and missing tool coverage with configurable CI thresholds.
- Import complete `tools/list` exports and MCP `tools/call` JSON/JSONL traces.
- Discover trusted stdio servers using the MCP Python SDK, including pagination
  and timeout handling; discovery never invokes tools.
- Export text, JSON, Markdown and JUnit XML reports without argument values.
- Include synthetic invoice examples, an SDK server, bilingual documentation,
  packaging and cross-platform CI.

Limitations: input-only replay, Draft 2020-12 with local pointer references,
stdio-only discovery, no live output validation, and no general compatibility
proof. See the README for details.
