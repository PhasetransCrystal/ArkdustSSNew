"""Publish only generated reports without checking out or modifying the source branch."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ARTIFACTS = ("badge.svg", "stats.json", "tree.md")


def run(root: Path, *args: str, data: bytes | None = None) -> bytes:
    env = os.environ.copy()
    env.update({"GIT_AUTHOR_NAME": "github-actions[bot]",
                "GIT_AUTHOR_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
                "GIT_COMMITTER_NAME": "github-actions[bot]",
                "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com"})
    return subprocess.check_output(["git", "-C", str(root), *args], input=data, env=env)


def remote_tip(root: Path, remote: str, ref: str) -> str | None:
    result = subprocess.run(["git", "-C", str(root), "ls-remote", "--exit-code", remote, ref],
                            capture_output=True, check=False)
    if result.returncode == 2:
        return None
    result.check_returncode()
    return result.stdout.decode().split()[0]


def publish(root: Path, output: Path, source_branch: str,
            branch: str = "wordcount-stats", remote: str = "origin") -> str:
    if branch == source_branch:
        raise ValueError("The statistics branch must not be the source branch")
    for name in (branch, source_branch):
        run(root, "check-ref-format", f"refs/heads/{name}")
    report = json.loads((output / "stats.json").read_text(encoding="utf-8"))
    source = report["source_commit"]
    if report["working_tree_modified"]:
        raise ValueError("Refusing to publish statistics containing uncommitted changes")
    if source != run(root, "rev-parse", "HEAD").decode().strip():
        raise ValueError("Report source does not match checked-out HEAD")
    source_ref = f"refs/heads/{source_branch}"
    if remote_tip(root, remote, source_ref) != source:
        return "Skipped: the source branch has a newer or different commit."

    target_ref = f"refs/heads/{branch}"
    parent = remote_tip(root, remote, target_ref)
    if parent:
        run(root, "fetch", "--no-tags", "--depth=1", remote, target_ref)
        parent = run(root, "rev-parse", "FETCH_HEAD").decode().strip()
        paths = set(run(root, "ls-tree", "-r", "--name-only", "-z", parent).decode().split("\0")) - {""}
        if paths - set(ARTIFACTS):
            raise ValueError("Statistics branch contains unrelated files; refusing to overwrite it")

    entries = []
    for name in ARTIFACTS:
        blob = run(root, "hash-object", "-w", "--stdin", data=(output / name).read_bytes()).decode().strip()
        entries.append(f"100644 blob {blob}\t{name}\0".encode())
    tree = run(root, "mktree", "-z", data=b"".join(entries)).decode().strip()
    if parent and tree == run(root, "rev-parse", f"{parent}^{{tree}}").decode().strip():
        return "Unchanged: published artifacts already match."
    args = ["commit-tree", tree]
    if parent:
        args.extend(["-p", parent])
    args.extend(["-m", f"docs: update word counts for {source[:12]}"])
    commit = run(root, *args).decode().strip()
    # Recheck immediately before publication. Never force-push over another writer.
    if remote_tip(root, remote, source_ref) != source:
        return "Skipped: the source branch advanced during generation."
    run(root, "push", remote, f"{commit}:{target_ref}")
    return f"Published reports to {branch} ({commit[:12]})."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=HERE.parents[1])
    parser.add_argument("--output", type=Path, default=HERE / "output")
    parser.add_argument("--source-branch", required=True)
    parser.add_argument("--branch", default="wordcount-stats")
    parser.add_argument("--remote", default="origin")
    args = parser.parse_args()
    print(publish(args.root.resolve(), args.output, args.source_branch, args.branch, args.remote))


if __name__ == "__main__":
    main()
