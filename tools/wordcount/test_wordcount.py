"""Self-contained unit and Git integration tests; never access the real remote."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

import count
import publish

CONFIG = {
    "roots": [{"path": "Exile.md", "type": "file"},
              {"path": "设定", "type": "directory"},
              {"path": "剧情", "type": "directory"}],
    "include": ["**/*.md"], "exclude": [],
}


class CountingTests(unittest.TestCase):
    def test_whitespace_markup_unicode_and_bom(self):
        text = "\ufeff# 中 文\tA\r\n[名](url)\u3000😀\n"
        self.assertEqual(count.count_text(text.encode()), (13, 19))
        self.assertEqual(count.count_text("中\r\n文".encode()), count.count_text("中\n文".encode()))
        self.assertEqual(count.count_text(b" \r\n\t"), (0, 3))
        with self.assertRaises(UnicodeDecodeError):
            count.count_text(b"\xff")

    def test_filters(self):
        config = copy.deepcopy(CONFIG)
        config["exclude"] = ["/设定/草稿/", "**/*.草稿.md"]
        for path in ("Exile.md", "设定/第一篇.md", "设定/深层/第二篇.md", "剧情/正文.md"):
            self.assertTrue(count.selected(path, config), path)
        for path in ("README.md", "其它/草稿.md", "设定/a.png", "设定/草稿/a.md", "设定/a.草稿.md"):
            self.assertFalse(count.selected(path, config), path)
        self.assertTrue(count.glob_regex("设定/**/a?.md").fullmatch("设定/a1.md"))
        self.assertFalse(count.glob_regex("设定/*.md").fullmatch("设定/子目录/a.md"))

    def test_invalid_roots(self):
        for path in ("../outside", "/absolute", "C:/file", "设定/../其它"):
            config = copy.deepcopy(CONFIG)
            config["roots"][0]["path"] = path
            with self.assertRaises(ValueError):
                count.validate_config(config)

    def test_badge_is_valid_svg(self):
        for number in (0, 123456, 999999999999):
            svg = count.render_badge(number)
            ET.fromstring(svg)
            self.assertIn(f"{number:,}", svg)


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.write("Exile.md", "# 中 文\n")  # 3 non-whitespace characters
        self.write("设定/子目录/a.md", "甲乙")
        self.write("设定/空.md", "")
        self.write("README.md", "excluded")
        self.git("add", ".")
        self.git("commit", "-m", "initial")
        self.write("设定/untracked.md", "not yet tracked")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)

    def write(self, path, text):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8", newline="\n")

    def test_tracked_scope_tree_and_reproducibility(self):
        report = count.collect(self.root, CONFIG)
        self.assertEqual(report["totals"]["characters"], 5)
        self.assertEqual(report["totals"]["files"], 3)
        self.assertFalse(report["working_tree_modified"])
        nodes = {child["name"]: child for child in report["tree"]["children"]}
        self.assertEqual(nodes["剧情"]["files"], 0)
        self.assertEqual(nodes["设定"]["characters"], 2)
        self.assertEqual(nodes["设定"]["files"], 2)
        self.assertEqual(report, count.collect(self.root, CONFIG))
        output = Path(self.temp.name) / "output"
        count.write_report(report, output)
        self.assertEqual(json.loads((output / "stats.json").read_text(encoding="utf-8")), report)
        self.assertIn("子目录", (output / "tree.md").read_text(encoding="utf-8"))

    def test_modification_addition_deletion_and_rename(self):
        self.write("Exile.md", "改变\n")
        self.assertTrue(count.collect(self.root, CONFIG)["working_tree_modified"])
        self.git("rm", "设定/空.md")
        self.git("mv", "设定/子目录/a.md", "设定/改名.md")
        self.write("剧情/新增.md", "新增三个字")
        self.git("add", "Exile.md", "剧情/新增.md")
        report = count.collect(self.root, CONFIG)
        self.assertEqual(report["totals"]["characters"], 9)
        self.assertEqual(report["totals"]["files"], 3)
        (self.root / "Exile.md").unlink()
        with self.assertRaises(FileNotFoundError):
            count.collect(self.root, CONFIG)

    def setup_remote(self):
        remote = Path(self.temp.name) / "remote.git"
        subprocess.check_output(["git", "init", "--bare", str(remote)], stderr=subprocess.PIPE)
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "origin", "main")
        return remote

    def test_publish_create_noop_update_and_stale(self):
        remote = self.setup_remote()
        output = Path(self.temp.name) / "output"
        count.write_report(count.collect(self.root, CONFIG), output)
        head = self.git("rev-parse", "HEAD")
        status = self.git("status", "--porcelain")
        self.assertIn("Published", publish.publish(self.root, output, "main"))
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual(self.git("status", "--porcelain"), status)
        published = subprocess.check_output(["git", "--git-dir", str(remote), "show", "wordcount-stats:stats.json"])
        self.assertEqual(json.loads(published)["totals"]["characters"], 5)
        self.assertIn("Unchanged", publish.publish(self.root, output, "main"))
        self.write("Exile.md", "更多文本")
        self.git("add", "Exile.md")
        self.git("commit", "-m", "update")
        self.git("push", "origin", "main")
        count.write_report(count.collect(self.root, CONFIG), output)
        self.assertIn("Published", publish.publish(self.root, output, "main"))
        self.git("checkout", "--detach", head.decode().strip())
        count.write_report(count.collect(self.root, CONFIG), output)
        self.assertIn("Skipped", publish.publish(self.root, output, "main"))

    def test_publish_guards(self):
        self.setup_remote()
        output = Path(self.temp.name) / "output"
        self.write("Exile.md", "未提交")
        count.write_report(count.collect(self.root, CONFIG), output)
        with self.assertRaises(ValueError):
            publish.publish(self.root, output, "main")
        with self.assertRaises(ValueError):
            publish.publish(self.root, output, "main", branch="main")
        self.git("checkout", "--", "Exile.md")
        count.write_report(count.collect(self.root, CONFIG), output)
        self.git("push", "origin", "HEAD:refs/heads/wordcount-stats")
        with self.assertRaises(ValueError):
            publish.publish(self.root, output, "main")


if __name__ == "__main__":
    unittest.main()
