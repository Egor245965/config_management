"""Commands for stage 4 of variant 7."""

import getpass
import re
import socket
import stat
from datetime import datetime

if __package__:
    from .virtual_fs import VirtualFS
else:
    from virtual_fs import VirtualFS


def options(args, allowed):
    """Parse short switches, preserving operands after --."""
    flags, paths = set(), []
    stopped = False
    for arg in args:
        if arg == "--" and not stopped:
            stopped = True
        elif arg.startswith("-") and arg != "-" and not stopped:
            if not set(arg[1:]) <= set(allowed):
                raise ValueError(f"неизвестная опция: {arg}")
            flags.update(arg[1:])
        else:
            paths.append(arg)
    return flags, paths


class Shell:
    """One emulated login session shared by the script and REPL."""

    def __init__(self, data=None):
        self.vfs = VirtualFS(data)
        self.username = getpass.getuser()
        self.hostname = socket.gethostname()
        self.started = datetime.now().strftime("%Y-%m-%d %H:%M")

    def prompt(self):
        """Display real host identity and the virtual working directory."""
        return f"{self.username}@{self.hostname}:/{self.vfs.cwd}$ "

    def execute(self, command, args):
        """Report command errors; return False only for a valid exit."""
        commands = {name: getattr(self, name) for name in
                    ("ls", "cd", "who", "head")}
        try:
            if command == "exit":
                if args:
                    raise ValueError("exit не принимает аргументы")
                return False
            if command not in commands:
                raise ValueError(f"неизвестная команда '{command}'")
            commands[command](args)
        except ValueError as error:
            print(f"Ошибка: {error}")
        return True

    def cd(self, args):
        """Change the virtual directory; no operand selects the root."""
        if len(args) > 1:
            raise ValueError("cd принимает не более одного аргумента")
        path = self.vfs.resolve(args[0] if args else "/")
        self.vfs.require_directory(path)
        self.vfs.cwd = path

    def ls(self, args):
        """List files; -a includes dot names and -l displays permissions."""
        flags, paths = options(args, "al")
        for value in paths or ["."]:
            try:
                self.list_path(value, flags, len(paths) > 1)
            except ValueError as error:
                print(f"Ошибка: ls: {error}")

    def list_path(self, value, flags, header):
        """Print one ls operand."""
        path = self.vfs.resolve(value)
        if header:
            print(f"{value}:")
        if path in self.vfs.directories:
            names = self.vfs.children(path, "a" in flags)
            entries = [(name, "/".join(filter(None, (path, name))))
                       for name in names]
            if "a" in flags:
                entries = [(".", path), ("..", path.rpartition("/")[0])]
                entries += [(name, "/".join(filter(None, (path, name))))
                            for name in names]
        else:
            entries = [(value, path)]
        for name, item in entries:
            prefix = ""
            if "l" in flags:
                kind = (stat.S_IFDIR if item in self.vfs.directories
                        else stat.S_IFREG)
                prefix = stat.filemode(kind | self.vfs.modes[item]) + " "
            print(prefix + name)

    def who(self, args):
        """Show the sole emulated session using the host's real identity."""
        if args:
            raise ValueError("who не принимает аргументы")
        print(f"{self.username} console {self.started} ({self.hostname})")

    def head(self, args):
        """Print ten lines by default, or a nonnegative count via -n."""
        count = 10
        if args and args[0] == "-n":
            if len(args) < 3 or not re.fullmatch(r"[0-9]+", args[1]):
                raise ValueError("head: ожидается -n ЧИСЛО ФАЙЛ")
            count, args = int(args[1]), args[2:]
        _, paths = options(args, "")
        if not paths:
            raise ValueError("head: укажите файл")
        for value in paths:
            try:
                text = self.vfs.read_text(self.vfs.resolve(value))
                if len(paths) > 1:
                    print(f"==> {value} <==")
                print("".join(text.splitlines(keepends=True)[:count]), end="")
            except ValueError as error:
                print(f"Ошибка: head: {error}")
