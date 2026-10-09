# Design: a witness is stronger than a guess

MCP tools expose input schemas and may expose output schemas. Clients can list
tools, and servers may change that list. The protocol's discovery and schema
validation requirements are the foundation for this project. See the
[MCP tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

The narrow problem is a **consumer's previously accepted call becoming invalid
after a server upgrade**. A process health check cannot establish that this call
is still accepted. A generic JSON diff can show a change, but it does not always
show its effect on a consumer.

## Decision model

```text
reviewed baseline catalog + recorded input cases
                      |
          validate cases against baseline
             invalid -> input error (2)
                      |
          validate cases against candidate
             rejected -> breaking witness
                      |
   combine with removed tools, metadata/schema drift and coverage
                      |
      apply threshold -> report -> exit 0 or 1
```

We intentionally do not attempt a general JSON Schema subsumption proof.
Combinators, conditional schemas, references and extensible vocabularies make
simple field-by-field compatibility claims unreliable. The implementation uses
`jsonschema` for instance validation and separates two classes of evidence:

- **Breaking:** a tool disappeared, or an input valid against the baseline is
  rejected by the candidate.
- **Review:** an input/output schema, description, effective behavior hint, or
  other metadata changed. Some such changes are compatible. Passing samples do
  not establish compatibility outside the corpus.

New tools are informational. Tools without samples are listed explicitly;
`--require-coverage` elevates them to review. Descriptions are compared exactly,
without a semantic model or a claim about model behavior. Schema array order is
preserved, so reordering an enum may require a harmless review.

## Scope of a snapshot

The fingerprint covers sorted tool definitions, preserving all metadata and
schema content. It detects accidental file changes and enables reproducible
reports. It is **not a signature, provenance claim or approval record**. A
contributor can edit a snapshot and recompute its hash. Enforce baseline ownership
through Git review and retrieve the baseline from a trusted revision in CI.

The file importer rejects a nonempty pagination cursor. The SDK adapter reads all
pages, detects repeated cursors, and imposes page/tool/time limits. Neither path
calls `tools/call`. The SDK handles MCP initialization and negotiated protocol
behavior; a server must advertise tool capability.

## Supported JSON Schema subset

Validation uses Draft 2020-12; schemas without a dialect use that draft. Ordinary
keywords such as `required`, `enum`, `anyOf`, `oneOf`, `if`/`then`, array and numeric
constraints, and `unevaluatedProperties` are evaluated by `jsonschema`.

Only local JSON Pointer `$ref` values are supported. Unknown dialects, external
refs, `$id`, anchors and dynamic refs return input errors. Instance examples and
defaults containing keys such as `$ref` are data, not schemas. Format annotations
are not assertions; custom vocabulary assertions are not implemented. Unresolvable
or non-terminating references encountered during validation cannot produce a pass.

## Privacy and trust boundaries

Offline commands do not retrieve URLs, send telemetry or call models. The capture
command executes a supplied server, whose code can access the filesystem and
network under the current user. Only run servers you trust. Arbitrary schemas may
contain expensive regular expressions; this program is not a hostile-input sandbox.

Schema validation errors are reduced to keyword and location. Argument values,
full exception messages, and server stderr are not placed in reports. Tool names,
case IDs and paths remain present. Imported corpora retain arguments verbatim;
choose synthetic values before sharing. An 8 MiB file limit, nesting depth limit
and collection limits bound ordinary input size, not all computation.

## Existing work and positioning

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) is the protocol's
interactive inspection tool. [mcpdrift](https://github.com/gdworks-studio/mcpdrift)
already provides catalog drift checks. MCP Witness does not claim to invent schema
diffing. Its initial focus is an offline **consumer input corpus**, validated first
against the baseline, with reproducible witness IDs, explicit coverage and review
findings. Use an inspector for interactive diagnosis and a broader test framework
for live behavioral testing.

## What would demonstrate usefulness

The bundled fixtures and SDK server prove the mechanics locally. They do not prove
adoption or a reduction in production incidents. Useful next evidence would be a
maintainer using the CLI in an independent repository, a reproducible real upgrade
regression, or an external contribution that expands the corpus. Track those with
public links and permission to share; do not substitute synthetic examples for
user evidence.
