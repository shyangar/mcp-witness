# Security policy

This is an early alpha. Security fixes are made on `main`; no long-term support
branches or service-level response guarantees are currently offered.

Report a suspected vulnerability through
[GitHub private vulnerability reporting](https://github.com/shyangar/mcp-witness/security/advisories/new).
Include a minimal reproduction with synthetic data. Please avoid posting an
unfixed vulnerability with private data in a public issue.

## Trust model

- `check`, `snapshot` and `import-calls` read local JSON. External schema retrieval
  is disabled. The tool does not call an AI model or collect telemetry.
- `capture` **executes the supplied server program** with the current user's
  privileges. It is discovery-only from the MCP client's perspective, not a
  sandbox or a guarantee that the server has no startup side effects.
- Server schemas can contain computationally expensive expressions. Input size
  limits do not make this a general hostile-code or denial-of-service boundary.
- Imported arguments are retained verbatim. Reports omit values but expose tool
  names, case IDs and field locations. Review files before publishing them.
- A snapshot hash is an integrity aid, not authentication. Review changes to
  baselines and corpora, and use branch protection in consuming repositories.
- Tool annotations are server declarations. They do not grant permission and do
  not prove that a tool is safe or non-destructive.

See [the design document](docs/design.md) for supported and unsupported schema
features and the distinction between input checks and actual tool behavior.
