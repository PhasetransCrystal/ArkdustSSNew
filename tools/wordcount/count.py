"""Count tracked Markdown text without stripping markup. Python 3.11+, stdlib only."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

VERSION = 1
HERE = Path(__file__).resolve().parent


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args])


def glob_regex(pattern: str) -> re.Pattern:
    """Root-relative, case-sensitive glob: *, ?, **; **/ also matches zero dirs."""
    pattern = pattern.removeprefix("/")
    if not pattern or "\\" in pattern or ".." in pattern.split("/"):
        raise ValueError(f"Invalid glob: {pattern!r}")
    if pattern.endswith("/"):
        pattern += "**"
    parts = []
    i = 0
    while i < len(pattern):
        if pattern[i:i + 3] == "**/":
            parts.append("(?:.*/)?")
            i += 3
        elif pattern[i:i + 2] == "**":
            parts.append(".*")
            i += 2
        elif pattern[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(parts))


def validate_config(config: dict) -> None:
    roots = config["roots"]
    if not roots:
        raise ValueError("At least one root is required")
    seen = set()
    for entry in roots:
        path = entry["path"]
        if (not path or "\\" in path or ":" in path
                or PurePosixPath(path).is_absolute()
                or any(p in ("", ".", "..") for p in path.split("/"))):
            raise ValueError(f"Invalid root path: {path!r}")
        if entry["type"] not in ("file", "directory") or path in seen:
            raise ValueError(f"Invalid or duplicate root: {entry!r}")
        seen.add(path)
    for name in ("include", "exclude"):
        for pattern in config[name]:
            glob_regex(pattern)


def selected(path: str, config: dict) -> bool:
    in_scope = any(
        path == entry["path"] if entry["type"] == "file"
        else path.startswith(entry["path"] + "/")
        for entry in config["roots"]
    )
    return (in_scope
            and any(glob_regex(p).fullmatch(path) for p in config["include"])
            and not any(glob_regex(p).fullmatch(path) for p in config["exclude"]))


def count_text(data: bytes) -> tuple[int, int]:
    # Ignore a UTF-8 BOM and normalize line endings; invalid UTF-8 is an error.
    text = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return sum(not ch.isspace() for ch in text), len(text)


def directory(path: str, name: str | None = None) -> dict:
    return {"type": "directory", "name": name or PurePosixPath(path).name,
            "path": path, "characters": 0, "raw_characters": 0,
            "files": 0, "children": []}


def build_tree(records: list[dict], config: dict) -> dict:
    tree = directory("", "世界观文档")
    nodes = {"": tree}

    def ensure_dir(path: str) -> dict:
        if path not in nodes:
            parent = str(PurePosixPath(path).parent)
            parent = "" if parent == "." else parent
            node = directory(path)
            ensure_dir(parent)["children"].append(node)
            nodes[path] = node
        return nodes[path]

    for entry in config["roots"]:
        if entry["type"] == "directory":
            ensure_dir(entry["path"])
    for record in records:
        parent = str(PurePosixPath(record["path"]).parent)
        ensure_dir("" if parent == "." else parent)["children"].append(record)

    def aggregate(node: dict) -> None:
        if node["type"] == "file":
            return
        node["children"].sort(key=lambda child: (child["type"] != "directory", child["name"]))
        for child in node["children"]:
            aggregate(child)
        for key in ("characters", "raw_characters", "files"):
            node[key] = sum(child[key] for child in node["children"])

    aggregate(tree)
    return tree


def collect(root: Path, config: dict) -> dict:
    validate_config(config)
    paths = sorted(set(p.decode("utf-8") for p in git(root, "ls-files", "-z").split(b"\0") if p))
    records = []
    for path in paths:
        if not selected(path, config):
            continue
        file = root / path
        if file.is_symlink() or not file.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Symlinks are not supported: {path}")
        # Do not silently omit unreadable or locally deleted tracked files.
        data = file.read_bytes()
        characters, raw = count_text(data)
        records.append({"type": "file", "name": PurePosixPath(path).name,
                        "path": path, "characters": characters, "raw_characters": raw,
                        "files": 1, "sha256": hashlib.sha256(data).hexdigest()})
    tree = build_tree(records, config)
    changed = set(p.decode("utf-8") for p in git(root, "diff", "HEAD", "--name-only", "-z").split(b"\0") if p)
    return {
        "schema_version": 1,
        "counter_version": VERSION,
        "source_commit": git(root, "rev-parse", "HEAD").decode().strip(),
        "source_mode": "tracked-working-tree",
        "working_tree_modified": any(selected(p, config) for p in changed),
        "counting_policy": {
            "characters": "Unicode code points excluding all str.isspace() whitespace; Markdown syntax retained",
            "raw_characters": "Unicode code points including whitespace; line endings normalized to LF",
            "encoding": "UTF-8; optional BOM ignored; invalid input fails",
            "files": "One matching tracked file is one document, including empty files",
        },
        "scope": config,
        "totals": {key: tree[key] for key in ("characters", "raw_characters", "files")},
        "tree": tree,
    }


def render_tree(report: dict) -> str:
    tree = report["tree"]

    def label(node: dict) -> str:
        # Keep control characters in unusual Git filenames from corrupting the report.
        name = node["name"].replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        text = f'{name} — {node["characters"]:,} 字符'
        return text + (f' / {node["files"]} 篇' if node["type"] == "directory" else "")

    lines = [label(tree)]

    def visit(node: dict, prefix: str) -> None:
        for index, child in enumerate(node.get("children", [])):
            last = index == len(node["children"]) - 1
            lines.append(prefix + ("└── " if last else "├── ") + label(child))
            visit(child, prefix + ("    " if last else "│   "))

    visit(tree, "")
    # An indented code block is safe even when filenames contain backticks.
    body = "\n".join("    " + line for line in lines)
    dirty = "是（本地预览）" if report["working_tree_modified"] else "否"
    return ("# 世界观文档字数统计\n\n"
            "按非空白 Unicode 字符计数，保留 Markdown 语法和标点；一份 Markdown 文件计一篇。\n\n"
            f'来源提交：`{report["source_commit"]}`  \n'
            f"统计范围内包含未提交修改：{dirty}\n\n"
            f"{body}\n\n"
            "零篇目录可能尚未创建、没有已跟踪的 Markdown 文件，或全部被过滤。\n\n"
            "完整机器可读数据：[stats.json](stats.json)。\n")


def render_badge(characters: int) -> str:
    label, value = "characters", f"{characters:,}"
    left, right = 82, max(54, len(value) * 8 + 16)
    width = left + right
    title = html.escape(f"Non-whitespace characters: {value}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="22" '
            f'viewBox="0 0 {width} 22" role="img" aria-label="{title}">\n'
            f'<title>{title}</title>\n'
            f'<rect width="{width}" height="22" rx="3" fill="#444"/>\n'
            f'<path d="M{left} 0h{right - 3}q3 0 3 3v16q0 3 -3 3h-{right - 3}z" fill="#39776b"/>\n'
            '<g fill="#fff" text-anchor="middle" font-family="Verdana,Arial,sans-serif" font-size="11">\n'
            f'<text x="{left / 2}" y="15">{label}</text>\n'
            f'<text x="{left + right / 2}" y="15">{value}</text>\n'
            '</g>\n</svg>\n')


def write_report(report: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "stats.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        "tree.md": render_tree(report),
        "badge.svg": render_badge(report["totals"]["characters"]),
    }
    for name, content in artifacts.items():
        (output / name).write_text(content, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=HERE.parents[1])
    parser.add_argument("--config", type=Path, default=HERE / "config.json")
    parser.add_argument("--output", type=Path, default=HERE / "output")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    report = collect(args.root.resolve(), config)
    write_report(report, args.output)
    print(json.dumps(report["totals"], ensure_ascii=True))
    print(f"Report written to: {args.output}")


if __name__ == "__main__":
    main()
