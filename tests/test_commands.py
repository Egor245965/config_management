"""Behavioral tests for stage 4."""

import base64
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from src.emulator import load_vfs, run_repl, run_startup_script
from src.shell import Shell


class TestCommands(unittest.TestCase):
    def setUp(self):
        contents = {
            "lines.txt": "".join(f"line {i}\n" for i in range(1, 13)),
            "home/user/note.txt": "Привет\nМир\n",
            ".hidden": "secret",
            "empty.txt": "",
            "no-newline.txt": "one\ntwo",
            "My Documents/test.txt": "spaces\n",
        }
        files = {name: base64.b64encode(text.encode()).decode()
                 for name, text in contents.items()}
        files["binary"] = base64.b64encode(b"\xff\x00").decode()
        self.shell = Shell({
            "files": files,
            "directories": {"", "home", "home/user", "My Documents"},
        })

    def command(self, name, *args):
        output = StringIO()
        with redirect_stdout(output):
            result = self.shell.execute(name, list(args))
        self.assertTrue(result)
        return output.getvalue()

    def test_ls_lists_only_direct_visible_children(self):
        lines = self.command("ls").splitlines()
        self.assertIn("home", lines)
        self.assertNotIn("home/user", lines)
        self.assertNotIn(".hidden", lines)
        self.assertEqual(lines, sorted(lines))

    def test_ls_all_long_and_file(self):
        text = self.command("ls", "-al")
        self.assertIn("-rw-r--r-- .hidden", text)
        self.assertIn("drwxr-xr-x .\n", text)
        self.assertEqual(self.command("ls", "lines.txt"), "lines.txt\n")

    def test_ls_multiple_paths_continues_after_error(self):
        text = self.command("ls", "missing", "home")
        self.assertIn("Ошибка", text)
        self.assertIn("user", text)

    def test_cd_relative_absolute_parent_and_root(self):
        self.command("cd", "home/user")
        self.assertEqual(self.shell.vfs.cwd, "home/user")
        self.command("cd", ".././user/..")
        self.assertEqual(self.shell.vfs.cwd, "home")
        self.command("cd", "/../../My Documents")
        self.assertEqual(self.shell.vfs.cwd, "My Documents")
        self.command("cd")
        self.assertEqual(self.shell.vfs.cwd, "")

    def test_cd_failure_preserves_directory(self):
        for path in ("missing", "lines.txt", "lines.txt/..", ""):
            with self.subTest(path=path):
                self.assertIn("Ошибка", self.command("cd", path))
                self.assertEqual(self.shell.vfs.cwd, "")

    def test_who_session_identity(self):
        text = self.command("who")
        self.assertIn(self.shell.username, text)
        self.assertIn(self.shell.hostname, text)
        self.assertIn(self.shell.started, text)

    def test_head_default_and_count(self):
        text = self.command("head", "lines.txt")
        self.assertEqual(text, "".join(f"line {i}\n" for i in range(1, 11)))
        self.assertEqual(self.command("head", "-n", "0", "lines.txt"), "")
        text = self.command("head", "-n", "1", "home/user/note.txt")
        self.assertEqual(text, "Привет\n")

    def test_head_count_requires_number_and_file(self):
        cases = [("-n",), ("-n", "2"), ("-n", "bad", "lines.txt")]
        for args in cases:
            with self.subTest(args=args):
                self.assertIn("Ошибка", self.command("head", *args))

    def test_head_empty_unterminated_and_multiple_files(self):
        self.assertEqual(self.command("head", "empty.txt"), "")
        self.assertEqual(self.command("head", "no-newline.txt"), "one\ntwo")
        text = self.command("head", "missing", "home/user/note.txt")
        self.assertIn("Ошибка", text)
        self.assertIn("==> home/user/note.txt <==\nПривет\nМир\n", text)

    def test_head_relative_path(self):
        self.command("cd", "My Documents")
        self.assertEqual(self.command("head", "test.txt"), "spaces\n")


    def test_repl_eof(self):
        with patch("builtins.input", side_effect=EOFError):
            with redirect_stdout(StringIO()):
                run_repl(self.shell)


class TestArchive(unittest.TestCase):
    def archive(self, entries):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "fixture.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in entries.items():
                info = zipfile.ZipInfo()
                info.filename = name
                archive.writestr(info, data)
        return path

    def test_empty_nested_directory_has_parents(self):
        path = self.archive({"a/b/c/": ""})
        self.assertEqual(load_vfs(path)["directories"],
                         {"", "a", "a/b", "a/b/c"})

    def test_invalid_archive_paths(self):
        for name in ("/abs", "../escape", "a/../b", "a\\b"):
            with self.subTest(name=name):
                path = self.archive({name: "text"})
                with redirect_stdout(StringIO()) as output:
                    self.assertIsNone(load_vfs(path))
                self.assertIn("Ошибка загрузки VFS", output.getvalue())

    def test_conflicting_file_and_directory(self):
        path = self.archive({"a": "file", "a/b": "child"})
        with redirect_stdout(StringIO()):
            self.assertIsNone(load_vfs(path))


if __name__ == "__main__":
    unittest.main()
