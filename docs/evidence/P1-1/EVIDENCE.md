# Evidence: P1-1

Implemented-by: worker-core-p1
Date: 2026-10-13

## Commands
```bash
uv run python scripts/gate.py
uv run pytest tests/unit/core/ -v --cov=src/penpress/core --cov-report=term-missing
uv run python -c "import json; from penpress.core import get_schema; print(json.dumps(get_schema(), indent=2))"
```

## Results
- `scripts/gate.py` passed all checks:
  - Ruff lint: All checks passed.
  - Ruff format: All 53 files clean.
  - Mypy `--strict`: Clean across all source files.
  - Anti-stub forbid scanner: Clean (no TODO, no mocks, no placeholders).
  - State board validator: Clean.
  - Docs check: Clean.
  - Pytest: 72 passed, overall coverage 98.01%, coverage of `src/penpress/core` 98.5%.
- Hypothesis property testing:
  - Transform composition `T2(T1(p)) == (T2.T1)(p)` holds within 1e-9 tolerance across 100 random affine transforms.
  - Inverse round-trip `T_inv(T(p)) == p` holds within 1e-6 across scaled/rotated/translated affine instances.
  - Axis-aligned bounding box strictly encloses all stroke points.
  - Ramer-Douglas-Peucker simplification preserves endpoints and limits maximum perpendicular deviation to within epsilon.
  - Polyline resampling preserves endpoints exactly and preserves total arc length within 0.5%.
  - 1,000 randomized Page instances tested with `test_json_roundtrip_identity_1000_pages` without failure.
  - Negative tests explicitly verify rejection of NaN/inf coordinates, out-of-range pressure (<0 or >1), negative time offsets, strokes with < 2 points, empty paths, non-positive page dimensions, malformed JSON, and unknown `schema_version`.

## Printed Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "PenPressPage",
  "description": "Vector stroke page layout in millimetres for pen plotters",
  "type": "object",
  "required": [
    "schema_version",
    "width_mm",
    "height_mm",
    "paths"
  ],
  "properties": {
    "schema_version": {
      "type": "integer",
      "const": 1,
      "description": "Version of the PenPress document schema"
    },
    "width_mm": {
      "type": "number",
      "exclusiveMinimum": 0.0,
      "description": "Physical width of the page in millimetres"
    },
    "height_mm": {
      "type": "number",
      "exclusiveMinimum": 0.0,
      "description": "Physical height of the page in millimetres"
    },
    "paths": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "strokes"
        ],
        "properties": {
          "label": {
            "type": "string"
          },
          "strokes": {
            "type": "array",
            "items": {
              "type": "object",
              "required": [
                "pts"
              ],
              "properties": {
                "pts": {
                  "type": "array",
                  "minItems": 2,
                  "items": {
                    "type": "object",
                    "required": [
                      "x",
                      "y"
                    ],
                    "properties": {
                      "x": {
                        "type": "number"
                      },
                      "y": {
                        "type": "number"
                      },
                      "p": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0
                      },
                      "t": {
                        "type": "number",
                        "minimum": 0.0
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

## Acceptance checklist
- Hypothesis property tests (composition, inverse, bounds, RDP deviation, resample arc length): PASS
- JSON round-trip identity on 1000 random pages: PASS
- Loading an unknown schema_version raises a clear error: PASS
- NaN/inf/empty stroke inputs rejected with explicit errors: PASS
- `mypy --strict` clean: PASS
- Coverage of `core/` >= 95%: PASS (measured 98.5%)

## Deviations
None.

## Reviewer notes
