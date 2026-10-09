"""Bounded JSON input, canonical snapshots, and schema validation without network access."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry

MAX_BYTES = 8 * 1024 * 1024
MAX_TOOLS = 2000
MAX_CASES = 10000
DIALECT = "https://json-schema.org/draft/2020-12/schema"


class InputError(ValueError):
    """Invalid or unsupported input; never a demonstrated regression."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise InputError("Duplicate JSON object key")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise InputError("Non-finite JSON numbers are not supported")


def check_depth(value: Any, depth: int = 0) -> None:
    if depth > 80:
        raise InputError("JSON nesting exceeds the supported depth of 80")
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise InputError("JSON object keys must be strings")
        for key in value:
            check_depth(key, depth + 1)
        for child in value.values():
            check_depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            check_depth(child, depth + 1)
    elif isinstance(value, float) and not math.isfinite(value):
        raise InputError("Non-finite JSON numbers are not supported")
    elif isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError as exc:
            raise InputError("JSON contains an unpaired Unicode surrogate") from exc
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise InputError("Input contains a value that cannot be represented as JSON")


def parse_json(text: str) -> Any:
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
        check_depth(value)
        return value
    except (json.JSONDecodeError, RecursionError, UnicodeError) as exc:
        raise InputError("Invalid JSON or unsupported nesting") from exc


def read_text(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise InputError("Input exceeds the 8 MiB limit")
        return raw.decode("utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise InputError("Cannot read input as UTF-8") from exc


def read_json(path: Path) -> Any:
    return parse_json(read_text(path))


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def digest(tools: list[dict]) -> str:
    return hashlib.sha256(canonical(tools).encode("utf-8")).hexdigest()


def write_text(path: Path, text: str, *, force: bool = False) -> None:
    """Use exclusive creation by default, or atomic replacement on explicit overwrite."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not force:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return
    fd, temporary = tempfile.mkstemp(prefix=".mcp-witness-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path: Path, value: Any, *, force: bool = False) -> None:
    write_text(
        path, json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n", force=force
    )


def _schema_nodes(schema: Any):
    """Walk schema positions only; example/default values are instance data."""
    if not isinstance(schema, dict):
        return
    yield schema
    for key in ("$defs", "properties", "patternProperties", "dependentSchemas"):
        value = schema.get(key, {})
        if isinstance(value, dict):
            for child in value.values():
                yield from _schema_nodes(child)
    for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
        value = schema.get(key, [])
        if isinstance(value, list):
            for child in value:
                yield from _schema_nodes(child)
    for key in (
        "items",
        "additionalProperties",
        "unevaluatedProperties",
        "unevaluatedItems",
        "contains",
        "propertyNames",
        "not",
        "if",
        "then",
        "else",
        "contentSchema",
    ):
        yield from _schema_nodes(schema.get(key))


def _pointer_target(schema: dict, reference: str) -> Any:
    fragment = unquote(reference[1:])
    if fragment == "":
        return schema
    if not fragment.startswith("/"):
        raise InputError("Only local JSON Pointer $ref values are supported")
    target: Any = schema
    try:
        for part in fragment[1:].split("/"):
            # RFC 6901 escaping. Invalid escapes are rejected, not guessed.
            if "~" in part.replace("~0", "").replace("~1", ""):
                raise InputError("Invalid JSON Pointer escape in $ref")
            key = part.replace("~1", "/").replace("~0", "~")
            if isinstance(target, list):
                if not key.isdecimal() or (len(key) > 1 and key[0] == "0"):
                    raise InputError("Invalid array index in $ref")
                target = target[int(key)]
            else:
                target = target[key]
        return target
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise InputError("Unresolved local schema reference") from exc


def validate_schema(schema: Any) -> None:
    if not isinstance(schema, dict):
        raise InputError("Tool schemas must be JSON objects")
    check_depth(schema)
    try:
        Draft202012Validator.check_schema(schema)
    except (SchemaError, RecursionError) as exc:
        raise InputError("Invalid Draft 2020-12 JSON Schema") from exc
    pending = list(_schema_nodes(schema))
    seen = set()
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if "$schema" in node and node["$schema"].rstrip("#") != DIALECT:
            raise InputError("Only JSON Schema Draft 2020-12 is supported")
        if any(key in node for key in ("$id", "$anchor", "$dynamicAnchor", "$dynamicRef")):
            raise InputError("Schema identifiers, anchors and dynamic references are unsupported")
        if "$ref" in node:
            ref = node["$ref"]
            if not isinstance(ref, str) or not ref.startswith("#"):
                raise InputError("External schema references are disabled; bundle local $defs")
            target = _pointer_target(schema, ref)
            if not isinstance(target, (dict, bool)):
                raise InputError("Schema reference does not point to a schema")
            try:
                Draft202012Validator.check_schema(target)
            except (SchemaError, RecursionError) as exc:
                raise InputError("Referenced value is not a valid Draft 2020-12 schema") from exc
            # A ref can point outside standard schema positions, including under
            # a custom keyword. Validate that target before following it.
            pending.extend(_schema_nodes(target))


def validation_errors(schema: dict, instance: Any) -> list[dict]:
    """Return locations and keywords, never values or jsonschema's value-bearing messages."""
    validator = Draft202012Validator(schema, registry=Registry())
    errors = []
    try:
        for error in validator.iter_errors(instance):
            errors.append(
                {
                    "instance_path": list(error.absolute_path),
                    "schema_path": list(error.absolute_schema_path),
                    "keyword": str(error.validator),
                }
            )
            if len(errors) >= 20:
                break
    except Exception as exc:
        # Unresolvable/cyclic references, invalid regex, etc. must never become a pass.
        raise InputError(
            "Schema could not be evaluated safely; inspect references and patterns"
        ) from exc
    return sorted(errors, key=canonical)


def catalog(value: Any) -> dict:
    check_depth(value)
    if not isinstance(value, dict):
        raise InputError("Catalog must be an object containing tools")
    if "result" in value:
        if "error" in value or value.get("jsonrpc") != "2.0":
            raise InputError("Invalid tools/list JSON-RPC response")
        value = value["result"]
    if not isinstance(value, dict) or not isinstance(value.get("tools"), list):
        raise InputError("Catalog must contain a tools array")
    if value.get("nextCursor") is not None:
        raise InputError("Incomplete tools/list page: collect every page before comparison")
    if "formatVersion" in value and (
        type(value["formatVersion"]) is not int or value["formatVersion"] != 1
    ):
        raise InputError("Unsupported snapshot formatVersion")
    if len(value["tools"]) > MAX_TOOLS:
        raise InputError("Catalog exceeds the 2000 tool limit")
    names = set()
    for tool in value["tools"]:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str) or not tool["name"]:
            raise InputError("Every tool must have a nonempty string name")
        if tool["name"] in names:
            raise InputError("Duplicate tool name")
        names.add(tool["name"])
        for field in ("description", "title"):
            if field in tool and not isinstance(tool[field], str):
                raise InputError("Tool description and title must be strings")
        validate_schema(tool.get("inputSchema"))
        if "outputSchema" in tool:
            validate_schema(tool["outputSchema"])
        annotations = tool.get("annotations", {})
        if not isinstance(annotations, dict):
            raise InputError("Tool annotations must be an object")
        for hint in ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"):
            if hint in annotations and not isinstance(annotations[hint], bool):
                raise InputError("Tool behavior hints must be booleans")
    tools = sorted(value["tools"], key=lambda tool: tool["name"])
    fingerprint = digest(tools)
    if "sha256" in value and value["sha256"] != fingerprint:
        raise InputError("Snapshot fingerprint does not match its tools")
    return {"formatVersion": 1, "sha256": fingerprint, "tools": tools}


def cases(value: Any) -> list[dict]:
    if not isinstance(value, dict) or not isinstance(value.get("cases"), list):
        raise InputError("Corpus must be an object with a cases array")
    result = value["cases"]
    if not 1 <= len(result) <= MAX_CASES:
        raise InputError("Corpus must contain between 1 and 10000 cases")
    ids = set()
    for case in result:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"]:
            raise InputError("Each case requires a nonempty string id")
        if case["id"] in ids:
            raise InputError("Duplicate case id")
        ids.add(case["id"])
        if not isinstance(case.get("tool"), str) or not case["tool"]:
            raise InputError("Each case requires a tool name")
        if not isinstance(case.get("arguments"), dict):
            raise InputError("Case arguments must be a JSON object")
        if set(case) - {"id", "tool", "arguments"}:
            raise InputError("Unknown case field; only id, tool and arguments are supported")
    check_depth(result)
    return result
