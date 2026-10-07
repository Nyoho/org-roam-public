#!/usr/bin/env python3
"""Check that public org-roam notes do not depend on anything outside this repository.

Reports, as file:line, every
  - id: link whose target :ID: is not defined in this repository,
  - roam: link (resolved by title, so it cannot be verified),
  - file link, #+INCLUDE or #+SETUPFILE that uses an absolute or home path,
    escapes the repository, or points to a missing file.

Exit status is 1 when any problem is found.
"""

import os
import re
import sys

SKIP_DIRS = {".git", "ltximg", "ltxpng"}
ID_RE = re.compile(r"^\s*:ID:\s+(\S+)", re.IGNORECASE | re.MULTILINE)
# Match only the target part so that links whose description wraps onto the next line are still found.
LINK_RE = re.compile(r"\[\[([^\[\]]+)\]")
KEYWORD_RE = re.compile(r"^\s*#\+(INCLUDE|SETUPFILE):\s*(.+?)\s*$", re.IGNORECASE)
BLOCK_BEGIN_RE = re.compile(r"^\s*#\+begin_(src|example|export)\b", re.IGNORECASE)
BLOCK_END_RE = re.compile(r"^\s*#\+end_(src|example|export)\b", re.IGNORECASE)
FILE_TYPES = ("file:", "file+sys:", "file+emacs:", "attachment:")


def org_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".org"):
                yield os.path.join(dirpath, name)


def active_lines(text):
    """Yield (line number, line) outside src/example/export blocks, where links are inert."""
    in_block = False
    for number, line in enumerate(text.splitlines(), 1):
        if in_block:
            if BLOCK_END_RE.match(line):
                in_block = False
            continue
        if BLOCK_BEGIN_RE.match(line):
            in_block = True
            continue
        yield number, line


def check_path(root, source, path):
    path = path.split("::", 1)[0]
    if not path:
        return None
    if path.startswith(("/", "~")):
        return f"absolute or home path: {path}"
    target = os.path.realpath(os.path.join(os.path.dirname(source), path))
    if os.path.commonpath([root, target]) != root:
        return f"path escapes the repository: {path}"
    if not os.path.exists(target):
        return f"missing target: {path}"
    return None


def link_problem(root, source, target, ids):
    if target.startswith("id:"):
        node_id = target[3:].split("::", 1)[0]
        return None if node_id in ids else f"id link to a node outside this repository: {node_id}"
    if target.startswith("roam:"):
        return f"roam link cannot be verified: {target}"
    for prefix in FILE_TYPES:
        if target.startswith(prefix):
            if prefix == "attachment:":
                return f"attachment link is not supported here: {target}"
            return check_path(root, source, target[len(prefix):])
    if target.startswith(("/", "./", "../", "~")):
        return check_path(root, source, target)
    return None


def keyword_problem(root, source, keyword, value):
    if keyword.upper() == "SETUPFILE" and re.match(r"https?://", value):
        return None
    m = re.match(r'"([^"]+)"|(\S+)', value)
    problem = check_path(root, source, m.group(1) or m.group(2))
    return f"#+{keyword.upper()}: {problem}" if problem else None


def main():
    root = os.path.realpath(sys.argv[1] if len(sys.argv) > 1 else
                            os.path.join(os.path.dirname(__file__), ".."))
    texts = {}
    for path in org_files(root):
        with open(path, encoding="utf-8", errors="replace") as f:
            texts[path] = f.read()
    ids = {m.group(1) for text in texts.values() for m in ID_RE.finditer(text)}

    problems = []
    for path, text in sorted(texts.items()):
        relative = os.path.relpath(path, root)
        for number, line in active_lines(text):
            for m in LINK_RE.finditer(line):
                problem = link_problem(root, path, m.group(1).strip(), ids)
                if problem:
                    problems.append(f"{relative}:{number}: {problem}")
            m = KEYWORD_RE.match(line)
            if m:
                problem = keyword_problem(root, path, m.group(1), m.group(2))
                if problem:
                    problems.append(f"{relative}:{number}: {problem}")

    for problem in problems:
        print(problem)
    print(f"checked {len(texts)} files, {len(ids)} IDs: {len(problems)} problem(s)",
          file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
