import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

from src.emulator import (
    execute_command,
    parse_arguments,
    parse_command,
    run_startup_script,
)

class TestEmulator(unittest.TestCase):

    def test_parse_ls(self):
        command, args = parse_command("ls")

        self.assertEqual(command, "ls")
        self.assertEqual(args, [])

    def test_parse_quoted_argument(self):
        command, args = parse_command('cd "My Documents"')

        self.assertEqual(command, "cd")
        self.assertEqual(args, ["My Documents"])

    def test_parse_multiple_arguments(self):
        command, args = parse_command("ls home documents")

        self.assertEqual(command, "ls")
        self.assertEqual(args, ["home", "documents"])

    def test_incorrect_quotes(self):
        with self.assertRaises(ValueError):
            parse_command('cd "My Documents')

    def test_exit(self):
        result = execute_command("exit", [])

        self.assertFalse(result)

    def test_exit_with_argument(self):
        output = StringIO()

        with redirect_stdout(output):
            result = execute_command("exit", ["hello"])

        self.assertTrue(result)
        self.assertIn(
            "Ошибка: exit не принимает аргументы",
            output.getvalue(),
        )

    def test_cd_with_too_many_arguments(self):
        output = StringIO()

        with redirect_stdout(output):
            result = execute_command("cd", ["home", "documents"])

        self.assertTrue(result)
        self.assertIn(
            "Ошибка: cd принимает не более одного аргумента",
            output.getvalue(),
        )

    def test_unknown_command(self):
        output = StringIO()

        with redirect_stdout(output):
            result = execute_command("abracadabra", [])

        self.assertTrue(result)
        self.assertIn(
            "Ошибка: неизвестная команда 'abracadabra'",
            output.getvalue(),
        )
    def test_parse_arguments(self):
        config = parse_arguments(
            [
                "--vfs",
                "vfs.zip",
                "--script",
                "startup.txt",
            ]
        )

        self.assertEqual(config.vfs, "vfs.zip")
        self.assertEqual(config.script, "startup.txt")
    def test_startup_script(self):
        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            encoding="utf-8",
            suffix=".txt",
        ) as file:
            file.write("# Комментарий\n")
            file.write("ls\n")
            file.write('cd "My Documents"\n')
            script_path = file.name

        output = StringIO()

        try:
            with redirect_stdout(output):
                result = run_startup_script(script_path)

            self.assertTrue(result)
            self.assertIn("ls []", output.getvalue())
            self.assertIn(
                "cd ['My Documents']",
                output.getvalue(),
            )
            self.assertNotIn(
                "# Комментарий",
                output.getvalue(),
            )

        finally:
            os.remove(script_path)
    def test_startup_script_not_found(self):
        output = StringIO()

        with redirect_stdout(output):
            result = run_startup_script("nonexistent_script.txt")

        self.assertTrue(result)
        self.assertIn(
            "Ошибка стартового скрипта",
            output.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
    