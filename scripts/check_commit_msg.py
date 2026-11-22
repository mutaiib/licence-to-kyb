"""commit-msg hook: enforce Conventional Commits 1.0.0 (docs/engineering-practices.md §2).

Kept dependency-free so the hook works without Node. CI checks pull request titles too.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TYPES = "feat|fix|docs|test|refactor|perf|build|ci|chore|style|revert|eval"
PATTERN = re.compile(rf"^({TYPES})(\([a-z0-9][a-z0-9-]*\))?(!)?: [^\s].{{0,98}}$")


def check(message: str) -> str | None:
    first = message.splitlines()[0] if message.strip() else ""
    if first.startswith(("Merge ", 'Revert "', "fixup! ", "squash! ")):
        return None
    if not PATTERN.match(first):
        return (
            f"Commit title does not follow Conventional Commits: {first!r}\n"
            f"Use '<type>(<scope>): <summary>' with type one of: {TYPES.replace('|', ', ')}."
        )
    return None


def main() -> int:
    error = check(Path(sys.argv[1]).read_text("utf-8"))
    if error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
