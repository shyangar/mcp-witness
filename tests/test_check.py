from copy import deepcopy

import pytest

from mcp_witness.check import check
from mcp_witness.data import InputError, cases, catalog


def tool(schema=None, name="lookup", **extra):
    return {"name": name, "inputSchema": schema or {"type": "object"}, **extra}


def snap(*tools):
    return catalog({"tools": list(tools)})


def corpus(arguments=None, name="lookup"):
    return cases({"cases": [{"id": "known-good", "tool": name, "arguments": arguments or {}}]})


def test_unchanged_catalog_passes():
    baseline = snap(tool())
    result = check(baseline, baseline, corpus())
    assert result["status"] == "passed"
    assert result["findings"] == []
    assert result["summary"]["cases_passed"] == 1


@pytest.mark.parametrize(
    ("constraint", "value", "keyword"),
    [
        ({"type": "integer"}, "7", "type"),
        ({"enum": ["paid"]}, "pending", "enum"),
        ({"const": "paid"}, "pending", "const"),
        ({"minimum": 10}, 9, "minimum"),
        ({"exclusiveMinimum": 10}, 10, "exclusiveMinimum"),
        ({"maximum": 9}, 10, "maximum"),
        ({"multipleOf": 3}, 4, "multipleOf"),
        ({"minLength": 3}, "ab", "minLength"),
        ({"maxLength": 3}, "abcd", "maxLength"),
        ({"pattern": "^[A-Z]+$"}, "abc", "pattern"),
        ({"minItems": 2}, [1], "minItems"),
        ({"maxItems": 1}, [1, 2], "maxItems"),
        ({"uniqueItems": True}, [1, 1], "uniqueItems"),
        ({"items": {"type": "integer"}}, ["a"], "type"),
        ({"anyOf": [{"const": 1}, {"const": 2}]}, 3, "anyOf"),
        ({"oneOf": [{"type": "number"}, {"type": "integer"}]}, 1, "oneOf"),
        ({"not": {"const": "blocked"}}, "blocked", "not"),
        ({"contains": {"const": "ready"}}, ["pending"], "contains"),
    ],
)
def test_concrete_tightening_witnesses(constraint, value, keyword):
    old = snap(tool())
    new = snap(tool({"type": "object", "properties": {"value": constraint}}))
    result = check(old, new, corpus({"value": value}))
    witnessed = [f for f in result["findings"] if f["code"] == "case.input_rejected"]
    assert result["status"] == "failed"
    assert len(witnessed) == 1
    assert witnessed[0]["case_id"] == "known-good"
    assert witnessed[0]["errors"][0]["keyword"] == keyword


def test_required_field_added():
    result = check(
        snap(tool()), snap(tool({"type": "object", "required": ["workspace"]})), corpus()
    )
    assert result["summary"]["breaking"] == 1
    assert result["summary"]["review"] == 1


def test_nested_required_and_local_ref():
    schema = {
        "type": "object",
        "$defs": {"address": {"type": "object", "required": ["city"]}},
        "properties": {"address": {"$ref": "#/$defs/address"}},
    }
    result = check(snap(tool()), snap(tool(schema)), corpus({"address": {}}))
    finding = next(f for f in result["findings"] if f["code"] == "case.input_rejected")
    assert finding["errors"][0]["instance_path"] == ["address"]


def test_unevaluated_properties_and_conditionals():
    schema = {
        "type": "object",
        "properties": {"kind": {"const": "bill"}},
        "if": {"required": ["kind"]},
        "then": {"required": ["amount"]},
        "unevaluatedProperties": False,
    }
    result = check(snap(tool()), snap(tool(schema)), corpus({"kind": "bill"}))
    assert result["summary"]["cases_failed"] == 1


def test_invalid_baseline_case_is_setup_error():
    baseline = snap(tool({"type": "object", "required": ["invoice_id"]}))
    with pytest.raises(InputError, match="rejected by the baseline"):
        check(baseline, baseline, corpus())


def test_unknown_baseline_tool_is_setup_error():
    with pytest.raises(InputError, match="absent from the baseline"):
        check(snap(tool()), snap(tool()), corpus(name="unknown"))


def test_removed_tool_breaks_even_without_its_own_case():
    old = snap(tool(), tool(name="second"))
    result = check(old, snap(tool()), corpus(), fail_on="breaking")
    assert result["status"] == "failed"
    assert result["summary"]["uncovered_tools"] == ["second"]
    assert any(f["code"] == "tool.removed" for f in result["findings"])


def test_removed_tool_marks_its_case_failed():
    result = check(snap(tool()), snap(), corpus())
    assert result["summary"]["cases_failed"] == 1


def test_additive_change_requires_review_without_claiming_a_break():
    candidate = snap(tool({"type": "object", "properties": {"optional": {"type": "string"}}}))
    strict = check(snap(tool()), candidate, corpus())
    relaxed = check(snap(tool()), candidate, corpus(), fail_on="breaking")
    assert strict["status"] == "failed"
    assert strict["summary"]["breaking"] == 0
    assert strict["summary"]["cases_failed"] == 0
    assert relaxed["status"] == "passed"


@pytest.mark.parametrize("field", ["description", "outputSchema", "execution", "_meta", "title"])
def test_changed_contract_metadata_requires_review(field):
    old = tool()
    value = {"type": "object"} if field == "outputSchema" else {"value": "new"}
    if field in {"description", "title"}:
        value = "new text"
    candidate = tool(**{field: value})
    result = check(snap(old), snap(candidate), corpus())
    assert result["summary"]["review"] == 1
    assert result["summary"]["breaking"] == 0


@pytest.mark.parametrize(
    ("hint", "before", "after"),
    [
        ("readOnlyHint", True, False),
        ("destructiveHint", False, True),
        ("idempotentHint", True, False),
        ("openWorldHint", False, True),
    ],
)
def test_behavior_hints_are_reviewed(hint, before, after):
    result = check(
        snap(tool(annotations={hint: before})), snap(tool(annotations={hint: after})), corpus()
    )
    finding = result["findings"][0]
    assert finding["code"] == "tool.behavior_changed"
    assert finding["before"] == before
    assert finding["after"] == after


def test_absent_hint_and_explicit_default_are_equivalent():
    result = check(snap(tool()), snap(tool(annotations={"readOnlyHint": False})), corpus())
    assert result["status"] == "passed"


def test_missing_read_only_hint_uses_conservative_default():
    result = check(snap(tool(annotations={"readOnlyHint": True})), snap(tool()), corpus())
    assert result["findings"][0]["code"] == "tool.behavior_changed"


def test_no_sample_is_visible_and_coverage_can_block():
    baseline = snap(tool(), tool(name="other"))
    assert check(baseline, baseline, corpus())["status"] == "passed"
    result = check(baseline, baseline, corpus(), require_coverage=True)
    assert result["status"] == "failed"
    assert result["summary"]["uncovered_tools"] == ["other"]


def test_new_tool_is_informational():
    result = check(snap(tool()), snap(tool(), tool(name="new")), corpus())
    assert result["status"] == "passed"
    assert result["summary"]["info"] == 1


def test_checks_do_not_mutate_the_call_corpus():
    samples = corpus({"private": ["example"]})
    original = deepcopy(samples)
    check(snap(tool()), snap(tool()), samples)
    assert samples == original
