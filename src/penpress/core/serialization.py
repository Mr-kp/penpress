"""JSON serialization and deserialization helpers with validation."""

from __future__ import annotations

import json
from typing import Any

from penpress.core.primitives import (
    CURRENT_SCHEMA_VERSION,
    CoreGeometryError,
    Page,
)


def page_to_json(page: Page, indent: int | None = 2) -> str:
    """Serialize a Page to a formatted JSON string."""
    return json.dumps(page.to_dict(), indent=indent)


def page_from_json(json_str: str) -> Page:
    """Deserialize a Page from a JSON string, validating the schema version."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise CoreGeometryError(f"Malformed JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise CoreGeometryError(f"Expected top-level JSON object, got {type(data).__name__}")

    return Page.from_dict(data)


def get_schema() -> dict[str, Any]:
    """Return JSON Schema for Page format v1."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "PenPressPage",
        "description": "Vector stroke page layout in millimetres for pen plotters",
        "type": "object",
        "required": ["schema_version", "width_mm", "height_mm", "paths"],
        "properties": {
            "schema_version": {
                "type": "integer",
                "const": CURRENT_SCHEMA_VERSION,
                "description": "Version of the PenPress document schema",
            },
            "width_mm": {
                "type": "number",
                "exclusiveMinimum": 0.0,
                "description": "Physical width of the page in millimetres",
            },
            "height_mm": {
                "type": "number",
                "exclusiveMinimum": 0.0,
                "description": "Physical height of the page in millimetres",
            },
            "paths": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["strokes"],
                    "properties": {
                        "label": {"type": "string"},
                        "strokes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["pts"],
                                "properties": {
                                    "pts": {
                                        "type": "array",
                                        "minItems": 2,
                                        "items": {
                                            "type": "object",
                                            "required": ["x", "y"],
                                            "properties": {
                                                "x": {"type": "number"},
                                                "y": {"type": "number"},
                                                "p": {
                                                    "type": "number",
                                                    "minimum": 0.0,
                                                    "maximum": 1.0,
                                                },
                                                "t": {
                                                    "type": "number",
                                                    "minimum": 0.0,
                                                },
                                            },
                                        },
                                    }
                                },
                            },
                        },
                    },
                },
            },
        },
    }
