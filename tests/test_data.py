import json

import pytest

from mcp_witness.data import (
    InputError,
    cases,
    catalog,
    parse_json,
    validate_schema,
    validation_errors,
)


def test_snapshot_is_stable_under_object_and_tool_order():
    a = {"name": "a", "inputSchema": {"type": "object"}}
    b = {"inputSchema": {"type": "object"}, "name": "b"}
    assert catalog({"tools": [a, b]}) == catalog({"tools": [b, a]})


def test_snapshot_round_trip_and_tampering():
    snap = catalog({"tools": [{"name": "tool", "inputSchema": {"type": "object"}}]})
    assert catalog(snap) == snap
    snap["tools"][0]["name"] = "other"
    with pytest.raises(InputError, match="fingerprint"):
        catalog(snap)


def test_json_rpc_result_supported():
    assert catalog({"jsonrpc": "2.0", "id": 1, "result": {"tools": []}})["tools"] == []


@pytest.mark.parametrize(
    "value",
    [
        [],
        {},
        {"tools": None},
        {"tools": [{"name": "x"}]},
        {"tools": [{"name": "x", "inputSchema": None}]},
        {"tools": [], "nextCursor": "more"},
        {"tools": [], "formatVersion": 99},
        {"jsonrpc": "2.0", "result": {"tools": []}, "error": {}},
        {"tools": [{"name": "x", "inputSchema": {}, "annotations": {"readOnlyHint": "true"}}]},
        {"tools": [{"name": "x", "inputSchema": {}}, {"name": "x", "inputSchema": {}}]},
    ],
)
def test_bad_catalogs_fail_closed(value):
    with pytest.raises(InputError):
        catalog(value)


@pytest.mark.parametrize(
    "schema",
    [
        {"$schema": "http://json-schema.org/draft-07/schema#"},
        {"$ref": "https://example.invalid/schema.json"},
        {"$ref": "file:///private.json"},
        {"$ref": "#/$defs/missing"},
        {"$ref": "#anchor"},
        {"$id": "https://example.invalid/root"},
        {"$dynamicRef": "#node"},
        {"properties": {"x": {"$ref": "https://example.invalid/x"}}},
        {"$defs": {"unused": {"$ref": "https://example.invalid/x"}}},
        {"items": {"$schema": "http://json-schema.org/draft-07/schema#"}},
        {"type": "not-a-json-type"},
        {"required": "x"},
        {"$defs": {"notSchema": 7}, "$ref": "#/$defs/notSchema"},
    ],
)
def test_invalid_and_unsupported_schemas_fail_closed(schema):
    with pytest.raises(InputError):
        validate_schema(schema)


def test_refs_inside_instance_examples_are_not_schema_refs():
    validate_schema(
        {
            "examples": [{"$ref": "https://example.invalid/value"}],
            "default": {"$id": "ordinary application data"},
        }
    )


def test_escaped_local_pointer_supported():
    schema = {
        "$defs": {"a/b~c": {"type": "integer"}},
        "properties": {"x": {"$ref": "#/$defs/a~1b~0c"}},
    }
    validate_schema(schema)
    assert validation_errors(schema, {"x": "text"})[0]["keyword"] == "type"


def test_cyclic_refs_cannot_be_mistaken_for_success():
    validate_schema({"$ref": "#"})
    with pytest.raises(InputError):
        validation_errors({"$ref": "#"}, {})


def test_format_is_annotation():
    schema = {"properties": {"email": {"type": "string", "format": "email"}}}
    assert validation_errors(schema, {"email": "not an email"}) == []


@pytest.mark.parametrize(
    "text", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}', "{"]
)
def test_ambiguous_or_invalid_json_rejected(text):
    with pytest.raises(InputError):
        parse_json(text)


def test_deep_json_rejected():
    with pytest.raises(InputError, match="nesting"):
        parse_json("[" * 82 + "0" + "]" * 82)


@pytest.mark.parametrize(
    "value",
    [
        {"cases": []},
        {"cases": [{}]},
        {"cases": [{"id": "x", "tool": "x", "arguments": []}]},
        {"cases": [{"id": "x", "tool": "x", "arguments": {}, "expected": "unsupported"}]},
        {"cases": [{"id": "x", "tool": "x", "arguments": {}}] * 2},
    ],
)
def test_invalid_corpora_rejected(value):
    with pytest.raises(InputError):
        cases(value)


def test_errors_do_not_include_private_argument_values():
    errors = validation_errors({"properties": {"x": {"type": "integer"}}}, {"x": "PRIVATE_VALUE"})
    assert "PRIVATE_VALUE" not in json.dumps(errors)


@pytest.mark.parametrize(
    "target",
    [
        {"$ref": "https://example.invalid/hidden"},
        {"$schema": "http://json-schema.org/draft-07/schema#"},
        {"type": 99},
    ],
)
def test_ref_cannot_bypass_checks_via_unknown_schema_position(target):
    with pytest.raises(InputError):
        validate_schema({"x-custom": target, "$ref": "#/x-custom"})


@pytest.mark.parametrize("text", ['{"x":"\\ud800"}', '{"\\ud800":1}'])
def test_unpaired_unicode_is_rejected(text):
    with pytest.raises(InputError):
        parse_json(text)
