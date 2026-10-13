"""Anti-toy scanner. Fails when source or tests contain shortcut patterns.

Usage: python scripts/forbid.py [paths...]   (default: src tests)
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SRC_TEXT_PATTERNS = [
    (re.compile(r"\b(TODO|FIXME|XXX|HACK)\b"), "unfinished-marker"),
    (re.compile(r"NotImplementedError"), "not-implemented"),
    (re.compile(r"\b(lorem ipsum|placeholder|dummy|stub(bed)?)\b", re.I), "placeholder-word"),
    (re.compile(r"(?<![A-Za-z])(mock|fake)", re.I), "mock-in-src"),
    (re.compile(r"^\s*#\s*(def|class|import|from|return|if|for|while)\b.*"), "commented-out-code"),
]
TEST_TEXT_PATTERNS = [
    (re.compile(r"pytest\.mark\.(skip|skipif|xfail)"), "skipped-test"),
    (re.compile(r"pytest\.(skip|xfail)\("), "skipped-test"),
    (re.compile(r"assert\s+True\b"), "vacuous-assert"),
    (re.compile(r"assert\s+1\s*==\s*1\b"), "vacuous-assert"),
]
ALLOW_MARK = "forbid: allow"


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str
    text: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.text.strip()}"


def _is_exempt_function(node: ast.AST, class_stack: list[ast.ClassDef]) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    for deco in node.decorator_list:
        name = ast.unparse(deco)
        if "abstractmethod" in name or "overload" in name:
            return True
    for cls in class_stack:
        for base in cls.bases:
            if "Protocol" in ast.unparse(base) or "ABC" in ast.unparse(base):
                return True
    return False


def _empty_body(body: list[ast.stmt]) -> bool:
    stmts = [
        s
        for s in body
        if not (
            isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str)
        )
    ]
    if not stmts:
        return True
    if len(stmts) == 1:
        s = stmts[0]
        if isinstance(s, ast.Pass):
            return True
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and s.value.value is Ellipsis:
            return True
    return False


def _walk(node: ast.AST, stack: list[ast.ClassDef], rel: str, out: list[Violation], lines: list[str]) -> None:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            _walk(child, [*stack, child], rel, out, lines)
            continue
        if (
            isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            and _empty_body(child.body)
            and not _is_exempt_function(child, stack)
            and ALLOW_MARK not in lines[child.lineno - 1]
        ):
            out.append(Violation(rel, child.lineno, "empty-function", f"def {child.name} has no real body"))
        _walk(child, stack, rel, out, lines)


def scan_file(path: Path, kind: str, root: Path = ROOT) -> list[Violation]:
    rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    patterns = SRC_TEXT_PATTERNS if kind == "src" else TEST_TEXT_PATTERNS
    out: list[Violation] = []
    for number, line in enumerate(lines, 1):
        if ALLOW_MARK in line:
            continue
        for regex, rule in patterns:
            if regex.search(line):
                out.append(Violation(rel, number, rule, line))
    if kind == "src":
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            out.append(Violation(rel, exc.lineno or 0, "syntax-error", str(exc)))
            return out
        _walk(tree, [], rel, out, lines)
    return out


def scan(paths: list[Path], root: Path = ROOT) -> list[Violation]:
    violations: list[Violation] = []
    for base in paths:
        if not base.exists():
            continue
        kind = "tests" if "tests" in base.parts else "src"
        for file in sorted(base.rglob("*.py")):
            if "vendor" in file.parts or ".venv" in file.parts:
                continue
            violations.extend(scan_file(file, kind, root))
    return violations


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv] or [ROOT / "src", ROOT / "tests"]
    violations = scan(paths)
    for violation in violations:
        print(violation, file=sys.stderr)
    if violations:
        print(f"forbid: {len(violations)} violation(s)", file=sys.stderr)
        return 1
    print("forbid: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
