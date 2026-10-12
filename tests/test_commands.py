"""Behavioral tests for stages 4 and 5."""

import base64
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from src.emulator import load_vfs, run_repl, run_startup_script
from src.shell import Shell, change_mode


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

    def test_cd_cannot_skip_missing_parent_with_dotdot(self):
        self.command("cd", "home/user")
        output = self.command("cd", "/missing/../home")
        self.assertIn("Ошибка", output)
        self.assertEqual(self.shell.vfs.cwd, "home/user")

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

    def test_head_count_with_option_terminator(self):
        output = self.command("head", "-n", "1", "--", "lines.txt")
        self.assertEqual(output, "line 1\n")
        self.assertIn("Ошибка", self.command("head", "-n", "1", "--"))

    def test_head_empty_unterminated_and_multiple_files(self):
        self.assertEqual(self.command("head", "empty.txt"), "")
        self.assertEqual(self.command("head", "no-newline.txt"), "one\ntwo")
        text = self.command("head", "missing", "home/user/note.txt")
        self.assertIn("Ошибка", text)
        self.assertIn("==> home/user/note.txt <==\nПривет\nМир\n", text)

    def test_head_relative_path(self):
        self.command("cd", "My Documents")
        self.assertEqual(self.command("head", "test.txt"), "spaces\n")

    def test_invalid_arguments(self):
        cases = [("ls", ["-z"]), ("who", ["x"]), ("head", []),
                 ("head", ["-n", "-1", "lines.txt"]),
                 ("head", ["-n", "x", "lines.txt"]),
                 ("head", ["-n"]), ("head", ["binary"]),
                 ("head", ["home"]), ("head", ["lines.txt/"]),
                 ("mkdir", []), ("mkdir", ["-x", "dir"]),
                 ("chmod", []), ("chmod", ["888", "lines.txt"]),
                 ("chmod", ["u+z", "lines.txt"])]
        for name, args in cases:
            with self.subTest(name=name, args=args):
                self.assertIn("Ошибка", self.command(name, *args))

    def test_mkdir_multiple_spaces_and_relative_paths(self):
        self.command("mkdir", "one", "two words")
        self.command("cd", "one")
        self.command("mkdir", "child/")
        self.assertIn("one/child", self.shell.vfs.directories)
        self.assertIn("two words", self.shell.vfs.directories)
        self.assertEqual(self.shell.vfs.modes["one"], 0o755)

    def test_mkdir_parents_and_existing(self):
        self.command("mkdir", "-p", "/new/a/b/")
        self.assertIn("new/a/b", self.shell.vfs.directories)
        self.assertEqual(self.command("mkdir", "-p", "new/a"), "")
        for path in ("new/a", "lines.txt", "missing/child", ""):
            self.assertIn("Ошибка", self.command("mkdir", path))
        self.assertIn("Ошибка", self.command("mkdir", "-p", "lines.txt/x"))

    def test_option_terminator(self):
        self.command("mkdir", "--", "-dir")
        self.assertIn("-dir", self.command("ls", "-a"))
        self.assertEqual(self.command("ls", "--", "-dir"), "")

    def test_chmod_numeric_and_symbolic(self):
        self.command("chmod", "600", "lines.txt", "empty.txt")
        self.assertEqual(self.shell.vfs.modes["lines.txt"], 0o600)
        self.command("chmod", "u+x,g+r,o=rx", "lines.txt")
        self.assertEqual(self.shell.vfs.modes["lines.txt"], 0o745)
        self.command("chmod", "a-rwx", "lines.txt")
        self.assertEqual(self.shell.vfs.modes["lines.txt"], 0)
        self.command("chmod", "u=rw", "lines.txt")
        self.assertIn("-rw-------", self.command("ls", "-l", "lines.txt"))

    def test_chmod_recursive_and_similar_prefix(self):
        self.command("mkdir", "home2")
        self.command("chmod", "-R", "700", "home")
        for path in ("home", "home/user", "home/user/note.txt"):
            self.assertEqual(self.shell.vfs.modes[path], 0o700)
        self.assertEqual(self.shell.vfs.modes["home2"], 0o755)

    def test_chmod_invalid_does_not_mutate(self):
        original = self.shell.vfs.modes.copy()
        self.command("chmod", "u+x,bad", "lines.txt")
        self.command("chmod", "600", "missing")
        self.assertEqual(self.shell.vfs.modes, original)

    def test_permissions_read_write_and_search(self):
        self.command("chmod", "000", "lines.txt")
        self.assertIn("доступ запрещён", self.command("head", "lines.txt"))
        self.command("chmod", "500", "home")
        self.assertIn("доступ запрещён", self.command("mkdir", "home/new"))
        self.command("chmod", "000", "home")
        self.assertIn("доступ запрещён", self.command("cd", "home"))
        self.assertIn("доступ запрещён", self.command("ls", "home"))
        self.command("chmod", "755", "home")
        self.assertEqual(self.command("cd", "home"), "")

    def test_chmod_mode_parser(self):
        self.assertEqual(change_mode(0o644, "0755"), 0o755)
        self.assertEqual(change_mode(0o777, "go="), 0o700)
        self.assertEqual(change_mode(0o644, "+x"), 0o755)

    def test_chmod_options_require_mode_and_path(self):
        for args in [("-R",), ("--",), ("-R", "--", "755")]:
            with self.subTest(args=args):
                self.assertIn("Ошибка", self.command("chmod", *args))
        self.assertEqual(self.command("chmod", "--", "600", "lines.txt"),
                         "")
        self.command("chmod", "-R", "--", "700", "home")
        self.assertEqual(self.shell.vfs.modes["lines.txt"], 0o600)
        self.assertEqual(self.shell.vfs.modes["home/user/note.txt"], 0o700)

    def test_script_state_comments_errors_and_exit(self):
        script = ('# comment\ncd home # inline\nmkdir work\n'
                  'unknown\ncd "bad\ncd work\nexit\nmkdir ignored\n')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "startup.txt"
            path.write_text(script, encoding="utf-8")
            with redirect_stdout(StringIO()) as output:
                result = run_startup_script(path, self.shell)
        self.assertFalse(result)
        self.assertEqual(self.shell.vfs.cwd, "home/work")
        self.assertNotIn("home/work/ignored", self.shell.vfs.directories)
        self.assertIn("некорректные кавычки", output.getvalue())

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

    def test_commands_leave_archive_and_host_unchanged(self):
        path = self.archive({"file.txt": "first\nsecond\n"})
        before = path.read_bytes()
        shell = Shell(load_vfs(path))
        with redirect_stdout(StringIO()):
            shell.execute("mkdir", ["virtual-only"])
            shell.execute("chmod", ["000", "file.txt"])
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((path.parent / "virtual-only").exists())
        reloaded = Shell(load_vfs(path))
        self.assertNotIn("virtual-only", reloaded.vfs.directories)
        self.assertEqual(reloaded.vfs.modes["file.txt"], 0o644)


if __name__ == "__main__":
    unittest.main()
