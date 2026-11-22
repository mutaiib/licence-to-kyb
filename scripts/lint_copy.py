"""Check the interface strings in frontend/src/copy.ts against docs/ui-copy.md (ASD-STE100).

Usage: python3 scripts/lint_copy.py [path/to/copy.ts]

Checks each string value:
- sentence length: at most 25 words; at most 20 in an instruction (a key ending in
  `.instruction`, or a sentence that starts with an imperative verb)
- the filler words from the Filler rule
- no exclamation marks and no ellipses
- the "Do not use" column of the Term list
- a passive-voice heuristic: a form of "be" followed by a past participle

Exits 1 and prints `file:line: key: message` for each failure. Python 3.12 stdlib only.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COPY = ROOT / "frontend" / "src" / "copy.ts"

INSTRUCTION_WORDS = 20
DESCRIPTION_WORDS = 25

# Verbs that start an instruction sentence in the copy ("Upload the licence.").
IMPERATIVE_WORDS = (
    "approve correct compare enter examine find load open override reject reopen retry "
    "sign submit try upload use wait write"
)
IMPERATIVES = frozenset(IMPERATIVE_WORDS.split())

FILLER_WORDS = "please just simply easily quickly oops great awesome let's sorry unfortunately"
FILLER = frozenset(FILLER_WORDS.split())

# Term list, "Do not use" column (docs/ui-copy.md). Each entry is a regex on lower-cased text.
# The comments give the reason for each exception.
BANNED_TERMS: dict[str, str] = {
    r"\blicense[sd]?\b": "use 'licence'",
    r"\bpermits?\b": "use 'licence'",
    r"\bitems?\b": "use 'field'",
    r"\bentry\b|\bentries\b": "use 'field'",
    r"\battributes?\b": "use 'field'",
    # "personal data" names a legal category, not a field value (trace.masked).
    r"(?<!personal )\bdata\b": "use 'value'",
    r"\binfo\b": "use 'value'",
    # "reviewer" names the person and is allowed; "review" as a verb or action is not.
    r"\breview(s|ed|ing)?\b": "use 'examine'",
    r"\blook at\b": "use 'examine'",
    r"\binspect(s|ed|ing)?\b": "use 'examine'",
    r"\bfix(es|ed|ing)?\b": "use 'correct'",
    r"\bedit(s|ed|ing)?\b": "use 'correct'",
    r"\bupdat(e|es|ed|ing)\b": "use 'correct'",
    r"\baccept(s|ed|ing)?\b": "use 'approve'",
    r"\bconfirm(s|ed|ing)?\b": "use 'approve'",
    r"\bdecline[sd]?\b": "use 'reject'",
    r"\bden(y|ies|ied)\b": "use 'reject'",
    r"\brestor(e|es|ed|ing)\b": "use 'reopen'",
    r"\bundo\b": "use 'reopen'",
    r"\bsend(s|ing)?\b|\bsent\b": "use 'submit'",
    r"\bfinish(es|ed|ing)?\b": "use 'submit'",
    r"\bcomplet(e|es|ed|ing)\b": "use 'submit'",
    r"\badd(s|ed|ing)?\b": "use 'upload'",
    r"\battach(es|ed|ing)?\b": "use 'upload'",
    r"\bdrop(s|ped|ping)?\b": "use 'upload'",
    # "issue" is allowed as the licence's issue date and as "issuing authority" / "does not issue";
    # it is banned when it means a problem.
    r"\bissues?\b(?! date)(?! and expiry)(?<!not issue)": "use 'flagged'",
    r"\bproblems?\b": "use 'flagged'",
    r"\bshareholders?\b": "use 'owner'",
    r"\bpartners?\b": "use 'owner'",
    r"\bexpiration\b": "use 'expiry date'",
    r"\bvalid until\b": "use 'expiry date'",
    r"\bbypass(es|ed|ing)?\b": "use 'override'",
    r"\bignor(e|es|ed|ing)\b": "use 'override'",
    r"\blog ?(in|out)\b|\blogin\b|\blogged\b": "use 'sign in' or 'sign out'",
}
CASE_SENSITIVE_TERMS: dict[str, str] = {r"\bOK\b": "use 'approve'"}

BE_FORMS = r"(?:am|is|are|was|were|be|been|being)"
PARTICIPLE_WORDS = (
    "shown written done made given taken seen known found sent built kept held brought "
    "thought told left lost paid put set read run hidden stolen chosen broken driven begun"
)
IRREGULAR_PARTICIPLES = PARTICIPLE_WORDS.split()
PASSIVE = re.compile(
    rf"\b{BE_FORMS}\s+(?:not\s+|also\s+|now\s+|then\s+)?"
    rf"(\w+ed|{'|'.join(IRREGULAR_PARTICIPLES)})\b",
    re.IGNORECASE,
)
# "be + participle" pairs that are adjectives here, not passive voice.
PASSIVE_ALLOW = frozenset(
    {
        # "The licence is expired" describes a state (adjective), as in data-model.md.
        "is expired",
        # "You are signed in" describes a session state (adjective).
        "are signed",
    }
)

ENTRY = re.compile(r"""^\s*['"]([\w.]+)['"]\s*:\s*(.*)$""")
STRING = re.compile(r"""'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)\"""")
SENTENCE_END = re.compile(r"(?<=[.?])\s+")


@dataclass(frozen=True)
class Entry:
    key: str
    value: str
    line: int


def parse_copy(text: str) -> list[Entry]:
    """Read `'key': 'value',` pairs from the `copy` object. A value may start on the next line."""
    entries: list[Entry] = []
    lines = text.splitlines()
    body = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if not body:
            body = line.startswith("export const copy")
            i += 1
            continue
        if line.startswith("}"):
            break
        match = ENTRY.match(line)
        if match:
            key, rest = match.group(1), match.group(2).strip()
            start = i
            if not rest and i + 1 < len(lines):
                i += 1
                rest = lines[i].strip()
            value = STRING.search(rest)
            if value is None:
                entries.append(Entry(key, "", start + 1))
            else:
                raw = value.group(1) if value.group(1) is not None else value.group(2)
                entries.append(Entry(key, raw.replace("\\'", "'").replace('\\"', '"'), start + 1))
        i += 1
    return entries


def sentences(value: str) -> list[str]:
    return [s.strip() for s in SENTENCE_END.split(value.strip()) if s.strip()]


def words(sentence: str) -> list[str]:
    return [w for w in re.split(r"\s+", sentence) if re.search(r"[\w{}]", w)]


def is_instruction(key: str, sentence: str) -> bool:
    first = words(sentence)[:1]
    starts_imperative = bool(first) and first[0].lower().strip(",") in IMPERATIVES
    return key.endswith(".instruction") or (starts_imperative and sentence.endswith("."))


def check_length(key: str, value: str) -> list[str]:
    problems: list[str] = []
    for sentence in sentences(value):
        count = len(words(sentence))
        limit = INSTRUCTION_WORDS if is_instruction(key, sentence) else DESCRIPTION_WORDS
        if count > limit:
            problems.append(f"sentence has {count} words (limit {limit}): {sentence!r}")
    return problems


def check_style(value: str) -> list[str]:
    problems = [f"filler word {w!r}" for w in re.findall(r"[a-z']+", value.lower()) if w in FILLER]
    if "!" in value:
        problems.append("exclamation mark")
    if "..." in value or "\u2026" in value:
        problems.append("ellipsis")
    return problems


def check_terms(value: str) -> list[str]:
    hits = [
        (hit.group(0), advice)
        for pattern, advice in BANNED_TERMS.items()
        for hit in re.finditer(pattern, value.lower())
    ] + [
        (hit.group(0), advice)
        for pattern, advice in CASE_SENSITIVE_TERMS.items()
        for hit in re.finditer(pattern, value)
    ]
    return [f"term {term!r} is not allowed: {advice}" for term, advice in hits]


def check_voice(value: str) -> list[str]:
    problems: list[str] = []
    for hit in PASSIVE.finditer(value):
        phrase = re.sub(r"\s+(not|also|now|then)\s+", " ", hit.group(0).lower())
        if phrase not in PASSIVE_ALLOW:
            problems.append(f"possible passive voice {hit.group(0)!r}: use active voice")
    return problems


def check(entry: Entry) -> list[str]:
    if not entry.value:
        return ["value is empty or not a plain string literal"]
    return (
        check_length(entry.key, entry.value)
        + check_style(entry.value)
        + check_terms(entry.value)
        + check_voice(entry.value)
    )


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_COPY
    entries = parse_copy(path.read_text("utf-8"))
    if not entries:
        print(f"{path}: no strings found in `export const copy`")
        return 1
    failures = 0
    seen: set[str] = set()
    for entry in entries:
        problems = check(entry)
        if entry.key in seen:
            problems.append("duplicate key")
        seen.add(entry.key)
        for problem in problems:
            failures += 1
            print(f"{path}:{entry.line}: {entry.key}: {problem}")
    if failures:
        print(f"{failures} copy problem(s) in {len(entries)} strings")
        return 1
    print(f"copy check passed: {len(entries)} strings")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
