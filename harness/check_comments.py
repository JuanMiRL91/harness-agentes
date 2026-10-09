"""Comment gate: length and density of comments in the files about to be committed.

Three rules (see `harness/docs/conventions.md`, "Comments"):

1. Length: no comment block (consecutive `#`/`//` lines or `/* */`) exceeds MAX_LINES.
2. Density: a file with >= MIN_CODE_LINES lines of code stays under MAX_RATIO comment
   lines per code line (1 per 5).
3. Module and class docstrings: in a .py of >= MIN_FILE_LINES_DOCSTRING lines they stay
   under MAX_RATIO_DOCSTRING of the file. Function docstrings are excluded (their contract).

Scope: `.py` under DIRS_PY and `.ts`/`.tsx`/`.js`/`.jsx` under DIRS_JS (`.d.ts` excluded).
Pragmas (`# noqa`, `# type:`...) do not count. Runs ONLY on changed files (`--staged` from
the pre-commit hook, `--working` from close.sh) so legacy code blocks nothing until it
is touched. `--all` is a global report. Skip once: `git commit --no-verify`.

Usage: ``python3 harness/check_comments.py (--staged | --working | --all | path...)``
(exit 1 on findings).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent.parent

MAX_LINES = 2
MAX_RATIO = 0.2
MIN_CODE_LINES = 15
MAX_RATIO_DOCSTRING = 0.3
MIN_FILE_LINES_DOCSTRING = 20

DIRS_PY = ("core", "ui", "harness", "tests", "scripts")
DIRS_JS = ("ui",)
JS_EXT = (".ts", ".tsx", ".js", ".jsx")
PRAGMAS = ("#!", "# noqa", "# type:", "# pragma", "# fmt:", "# ruff", "# pylint")

GREEN = "\033[0;32m"
RED = "\033[0;31m"
NC = "\033[0m"


@dataclass
class Measure:
    code: int = 0
    comment: int = 0
    blocks: list[tuple[int, int]] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        return self.comment / self.code if self.code else 0.0


@dataclass
class DocstringMeasure:
    total: int = 0
    docstring: int = 0

    @property
    def ratio(self) -> float:
        return self.docstring / self.total if self.total else 0.0


def in_scope(path: str) -> bool:
    path = path.replace("\\", "/")
    if path.endswith(".py"):
        return path.split("/", 1)[0] in DIRS_PY
    if path.endswith(JS_EXT) and not path.endswith(".d.ts"):
        return any(path.startswith(d + "/") for d in DIRS_JS) and "node_modules" not in path
    return False


def _is_py_comment(line: str) -> bool:
    return line.startswith("#") and not line.startswith(PRAGMAS)


def measure(text: str, js: bool) -> Measure:
    """Counts code/comment lines and locates each comment block (1-based start, length)."""
    m = Measure()
    start = -1
    length = 0
    in_block = False

    def close_block() -> None:
        nonlocal start, length
        if length:
            m.blocks.append((start, length))
        start, length = -1, 0

    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if js and in_block:
            m.comment += 1
            length += 1
            if "*/" in line:
                in_block = False
            continue
        if js and line.startswith(("/*", "{/*")):
            if start == -1:
                start = n
            m.comment += 1
            length += 1
            if "*/" not in line:
                in_block = True
            continue
        if line.startswith("//") if js else _is_py_comment(line):
            if start == -1:
                start = n
            m.comment += 1
            length += 1
            continue
        close_block()
        m.code += 1
    close_block()
    return m


def _docstring_span(node: ast.Module | ast.ClassDef) -> tuple[int, int] | None:
    if not node.body:
        return None
    first = node.body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return first.lineno, first.end_lineno or first.lineno
    return None


def measure_docstrings(text: str) -> DocstringMeasure:
    """Module + class docstring lines (NOT function ones) against the file's total."""
    m = DocstringMeasure(total=len(text.splitlines()))
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return m
    for node in [tree, *(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))]:
        span = _docstring_span(node)
        if span:
            m.docstring += span[1] - span[0] + 1
    return m


def _git(*args: str) -> list[str]:
    out = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def staged_files() -> list[str]:
    return _git("diff", "--cached", "--name-only", "--diff-filter=d")


def working_files() -> list[str]:
    changed = _git("diff", "--name-only", "--diff-filter=d", "HEAD")
    new = _git("ls-files", "--others", "--exclude-standard")
    return sorted(set(changed) | set(new))


def all_files() -> list[str]:
    return _git("ls-files")


def check(
    paths: list[str],
) -> tuple[list[str], list[tuple[float, str, Measure]], list[tuple[float, str, DocstringMeasure]]]:
    """Returns (length violations, density violations, module/class docstring violations)."""
    long_: list[str] = []
    dense: list[tuple[float, str, Measure]] = []
    docstrings: list[tuple[float, str, DocstringMeasure]] = []
    for path in paths:
        if not in_scope(path):
            continue
        file = ROOT / path
        if not file.is_file():
            continue
        is_py = path.endswith(".py")
        text = file.read_text(encoding="utf-8", errors="replace")
        m = measure(text, js=not is_py)
        for start, length in m.blocks:
            if length > MAX_LINES:
                long_.append(f"  {path}:{start} ({length} lines)")
        if m.code >= MIN_CODE_LINES and m.ratio > MAX_RATIO:
            dense.append((m.ratio, path, m))
        if is_py:
            md = measure_docstrings(text)
            if md.total >= MIN_FILE_LINES_DOCSTRING and md.ratio > MAX_RATIO_DOCSTRING:
                docstrings.append((md.ratio, path, md))
    dense.sort(key=lambda t: t[0], reverse=True)
    docstrings.sort(key=lambda t: t[0], reverse=True)
    return long_, dense, docstrings


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--staged"]:
        paths, mode = staged_files(), "staged"
    elif args == ["--working"]:
        paths, mode = working_files(), "changed vs HEAD"
    elif args == ["--all"]:
        paths, mode = all_files(), "in the repo"
    elif args and not args[0].startswith("--"):
        paths, mode = args, "given"
    else:
        print(__doc__)
        return 2

    paths = [p for p in paths if in_scope(p)]
    long_, dense, docstrings = check(paths)
    if not long_ and not dense and not docstrings:
        print(f"{GREEN}[OK]{NC}   check_comments: {len(paths)} file(s) {mode} with no long "
              f"(>{MAX_LINES} lines) or dense (>{MAX_RATIO:g} per code line) comments and no "
              f"oversized module/class docstrings (>{MAX_RATIO_DOCSTRING:g} of the file)")
        return 0

    if long_:
        print(f"{RED}[FAIL]{NC} check_comments: comments longer than {MAX_LINES} lines:")
        print("\n".join(long_))
    if dense:
        print(f"{RED}[FAIL]{NC} check_comments: files with too many comments "
              f"(max {MAX_RATIO:g} per code line, from {MIN_CODE_LINES} code lines):")
        for ratio, path, m in dense:
            print(f"  {path} - {m.comment} comment / {m.code} code (ratio {ratio:.2f})")
    if docstrings:
        print(f"{RED}[FAIL]{NC} check_comments: oversized module/class docstrings "
              f"(max {MAX_RATIO_DOCSTRING:g} of the file, from {MIN_FILE_LINES_DOCSTRING} lines):")
        for ratio, path, md in docstrings:
            print(f"  {path} - {md.docstring} docstring / {md.total} lines (ratio {ratio:.2f})")
    print(
        "\nNames say the what. Delete comments that repeat a name, a type or the line below;\n"
        "keep only the non-obvious why, in 1-2 lines. Function docstrings do not count (they\n"
        "are the contract); long module/class prose moves to harness/docs/architecture.md.\n"
        "Skip once: git commit --no-verify"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
