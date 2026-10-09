# Roadmap

Roadmap entries are proposals, not implemented capabilities or delivery promises.

## Available in 0.1.0

- Offline baseline/candidate checks against a recorded input corpus.
- Concrete rejected-call witnesses and conservative schema/metadata review.
- Coverage reporting and configurable blocking thresholds.
- Canonical snapshots, MCP JSON/JSONL import, and stdio SDK discovery.
- JSON, Markdown, JUnit and terminal reports; tests across operating systems.

## Next: validate with maintainers

1. Help one independent MCP maintainer integrate a reviewed baseline and a small
   sanitized corpus. Record actual feedback before expanding the interface.
2. Collect minimal fixtures for real version upgrades, with permission and links
   to upstream issues where appropriate. Do not claim synthetic fixtures are
   production incidents.
3. Measure setup friction, false review findings, and useful witnessed regressions.
   Publish only numbers that can be reproduced.

## Candidate engineering work

| Proposal | Acceptance evidence |
| --- | --- |
| Streamable HTTP discovery | SDK integration tests for authentication, pagination, timeout and session cleanup; no credentials in logs. |
| Candidate output assertions | Saved candidate outputs checked against explicit consumer expectations, with input/output evidence clearly distinguished. |
| Additional trace adapters | Real sanitized fixture for a documented format, deterministic IDs, no silent record loss. |
| Less noisy schema changes | A tested classification for set-like schema arrays that does not rewrite arbitrary instance values. |
| Consumer CI examples | At least one independent repository can adopt the workflow using a pinned version. |

We do not plan to add a hosted account, paid inference requirement or automatic
baseline approval to the offline core.
