# CI integration

Commit a reviewed baseline and sanitized input corpus. Generate the candidate
from the version under test or export its complete `tools/list` response. Run:

```sh
mcp-witness check --baseline baseline.json --candidate candidate.json --cases cases.json --require-coverage --format junit --output reports/mcp.xml
```

An exit of `1` should fail the job. An exit of `2` is a setup failure and should
also fail the job. Do not use `continue-on-error` for the real regression check.
Upload the report with `if: always()` so it is available after failure.

## Prevent a PR from quietly replacing its own baseline

Keep your baseline in `mcp/baseline.json` on the protected base branch. Use the
reviewed base revision, not a same-PR replacement. This example assumes your
repository already installs MCP Witness from a pinned release commit and builds
`mcp/candidate.json` in an earlier step:

```yaml
permissions:
  contents: read

steps:
  - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
    with:
      fetch-depth: 0
  # Install your pinned mcp-witness dependency and export the candidate here.
  - name: Check contract against the reviewed baseline
    shell: bash
    env:
      BASE_SHA: ${{ github.event.pull_request.base.sha }}
    run: |
      mkdir -p reports
      git show "$BASE_SHA:mcp/baseline.json" > reports/reviewed-baseline.json
      mcp-witness check \
        --baseline reports/reviewed-baseline.json \
        --candidate mcp/candidate.json \
        --cases mcp/cases.json \
        --require-coverage \
        --format junit \
        --output reports/mcp.xml
  - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
    if: always()
    with:
      name: mcp-contract-report
      path: reports/mcp.xml
```

This is a **pull_request-event fragment**, not a complete workflow. On push or
manual runs, select an explicit trusted baseline revision. Review changes to the
corpus too: removing failing cases weakens a test suite. A SHA-256 fingerprint
does not replace review or branch protection.

Prefer a locally exported candidate in CI. Capturing a server starts code from the
checkout; use ordinary isolated CI with no production credentials. Avoid
`pull_request_target` with untrusted pull request code.

## Reading outcomes

`case.input_rejected` has an exact case ID and schema keyword. Reproduce it with
the corresponding case locally. If the old call should remain supported, restore
the server's compatible contract. If the change is intentional, migrate clients,
then review the baseline and corpus update together.

`schema.output_changed`, descriptions, and behavior hints need manual inspection.
There is no command that silently blesses a baseline. `snapshot --force` is only a
file operation; the actual approval belongs in code review.

JUnit failures mirror the selected threshold. JSON reports include summary counts,
findings, case statuses and the two snapshot fingerprints. Markdown can be used in
a job summary. None of these reports execute or assess live tool behavior.
