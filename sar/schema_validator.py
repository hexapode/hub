"""JSON Schema loader and validator for superAutoResearch formats."""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any


class SchemaValidationError(ValueError):
    """Raised when an object fails JSON Schema validation."""


SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


def load_schema(name: str) -> dict[str, Any]:
    filename = name if name.endswith(".json") else f"{name}.json"
    path = SCHEMAS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_dates(obj: Any) -> Any:
    """Convert datetime.date / datetime.datetime objects from TOML into ISO strings."""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _normalize_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_dates(x) for x in obj]
    return obj


def validate_against_schema(instance: Any, schema_name_or_dict: str | dict[str, Any]) -> None:
    schema = (
        load_schema(schema_name_or_dict)
        if isinstance(schema_name_or_dict, str)
        else schema_name_or_dict
    )
    normalized = _normalize_dates(instance)

    try:
        import jsonschema  # type: ignore

        try:
            jsonschema.validate(instance=normalized, schema=schema)
            return
        except jsonschema.ValidationError as exc:
            raise SchemaValidationError(exc.message) from exc
    except ImportError:
        pass

    _validate_node(normalized, schema, schema, path="$")


def _check_type(val: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(val, dict)
    if expected == "array":
        return isinstance(val, list)
    if expected == "string":
        return isinstance(val, str)
    if expected == "boolean":
        return isinstance(val, bool)
    if expected == "integer":
        return isinstance(val, int) and not isinstance(val, bool)
    if expected == "number":
        return isinstance(val, (int, float)) and not isinstance(val, bool)
    if expected == "null":
        return val is None
    return True


def _resolve_ref(ref: str, root_schema: dict[str, Any]) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise SchemaValidationError(f"Unsupported $ref: {ref}")
    parts = ref[2:].split("/")
    cur: Any = root_schema
    for p in parts:
        cur = cur[p]
    return cur


def _validate_node(
    val: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str,
) -> None:
    if "$ref" in schema:
        target = _resolve_ref(schema["$ref"], root_schema)
        _validate_node(val, target, root_schema, path)
        return

    if "allOf" in schema:
        for sub in schema["allOf"]:
            _validate_node(val, sub, root_schema, path)

    if "anyOf" in schema:
        errors = []
        for sub in schema["anyOf"]:
            try:
                _validate_node(val, sub, root_schema, path)
                break
            except SchemaValidationError as exc:
                errors.append(str(exc))
        else:
            raise SchemaValidationError(f"{path}: failed anyOf constraints ({'; '.join(errors)})")

    if "oneOf" in schema:
        matches = 0
        errors = []
        for sub in schema["oneOf"]:
            try:
                _validate_node(val, sub, root_schema, path)
                matches += 1
            except SchemaValidationError as exc:
                errors.append(str(exc))
        if matches != 1:
            raise SchemaValidationError(f"{path}: failed oneOf constraint (matched {matches})")

    if "if" in schema:
        cond_matched = True
        try:
            _validate_node(val, schema["if"], root_schema, path)
        except SchemaValidationError:
            cond_matched = False
        if cond_matched and "then" in schema:
            _validate_node(val, schema["then"], root_schema, path)
        elif not cond_matched and "else" in schema:
            _validate_node(val, schema["else"], root_schema, path)

    expected_type = schema.get("type")
    if expected_type is not None:
        types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_check_type(val, t) for t in types):
            raise SchemaValidationError(
                f"{path}: expected type {expected_type}, got {type(val).__name__} ({val!r})"
            )

    if "enum" in schema and val not in schema["enum"]:
        raise SchemaValidationError(f"{path}: {val!r} is not one of {schema['enum']}")

    if "const" in schema and val != schema["const"]:
        raise SchemaValidationError(f"{path}: expected const {schema['const']!r}, got {val!r}")

    if isinstance(val, str):
        if "minLength" in schema and len(val) < schema["minLength"]:
            raise SchemaValidationError(
                f"{path}: string shorter than minLength {schema['minLength']}"
            )
        if "maxLength" in schema and len(val) > schema["maxLength"]:
            raise SchemaValidationError(
                f"{path}: string longer than maxLength {schema['maxLength']}"
            )
        if "pattern" in schema and not re.search(schema["pattern"], val):
            raise SchemaValidationError(
                f"{path}: string {val!r} does not match pattern {schema['pattern']!r}"
            )

    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if "minimum" in schema and val < schema["minimum"]:
            raise SchemaValidationError(f"{path}: {val} < minimum {schema['minimum']}")
        if "maximum" in schema and val > schema["maximum"]:
            raise SchemaValidationError(f"{path}: {val} > maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and val <= schema["exclusiveMinimum"]:
            raise SchemaValidationError(
                f"{path}: {val} <= exclusiveMinimum {schema['exclusiveMinimum']}"
            )

    if isinstance(val, list):
        if "minItems" in schema and len(val) < schema["minItems"]:
            raise SchemaValidationError(f"{path}: array has fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(val) > schema["maxItems"]:
            raise SchemaValidationError(f"{path}: array has more than {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            seen = []
            for item in val:
                if item in seen:
                    raise SchemaValidationError(f"{path}: duplicate item in array: {item!r}")
                seen.append(item)
        if "items" in schema:
            for idx, item in enumerate(val):
                _validate_node(item, schema["items"], root_schema, f"{path}[{idx}]")

    if isinstance(val, dict):
        required = schema.get("required", [])
        for req_key in required:
            if req_key not in val:
                raise SchemaValidationError(f"{path}: missing required property '{req_key}'")
        props = schema.get("properties", {})
        addl = schema.get("additionalProperties", True)
        for k, v in val.items():
            if k in props:
                _validate_node(v, props[k], root_schema, f"{path}.{k}")
            elif addl is False:
                raise SchemaValidationError(f"{path}: unexpected additional property '{k}'")
            elif isinstance(addl, dict):
                _validate_node(v, addl, root_schema, f"{path}.{k}")
