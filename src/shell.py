"""Commands for stages 4 and 5 of variant 7."""

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


def change_mode(mode, expression):
    """Apply an octal mode or symbolic u/g/o/a +/-/= rwx clauses."""
    if re.fullmatch(r"[0-7]{3,4}", expression):
        return int(expression, 8)
    for clause in expression.split(","):
        match = re.fullmatch(r"([ugoa]*)([+=-])([rwx]*)", clause)
        if not match:
            raise ValueError(f"неверный режим прав: {expression}")
        who, operator, permissions = match.groups()
        who = "ugo" if not who or "a" in who else who
        bits = sum(bit for char, bit in zip("rwx", (4, 2, 1))
                   if char in permissions)
        for group, shift in (("u", 6), ("g", 3), ("o", 0)):
            if group in who:
                mask = bits << shift
                if operator == "=":
                    mode = (mode & ~(7 << shift)) | mask
                elif operator == "+":
                    mode |= mask
                else:
                    mode &= ~mask
    return mode


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
                    ("ls", "cd", "who", "head", "mkdir", "chmod")}
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

    def mkdir(self, args):
        """Create one or more directories; -p creates parent directories."""
        flags, paths = options(args, "p")
        if not paths:
            raise ValueError("mkdir: укажите каталог")
        for value in paths:
            try:
                self.vfs.mkdir(value, "p" in flags)
            except ValueError as error:
                print(f"Ошибка: mkdir: {error}")

    def chmod(self, args):
        """Change mode bits in memory; -R also changes descendants."""
        recursive = bool(args and args[0] == "-R")
        args = args[1:] if recursive else args
        if args and args[0] == "--":
            args = args[1:]
        if len(args) < 2:
            raise ValueError("chmod: ожидаются РЕЖИМ и ПУТЬ")
        expression = args[0]
        change_mode(0, expression)
        for value in args[1:]:
            try:
                path = self.vfs.resolve(value)
                targets = [path]
                if recursive and path in self.vfs.directories:
                    prefix = path + "/" if path else ""
                    targets += [item for item in self.vfs.modes
                                if item != path and item.startswith(prefix)]
                for item in targets:
                    old_mode = self.vfs.modes[item]
                    self.vfs.modes[item] = change_mode(old_mode, expression)
            except ValueError as error:
                print(f"Ошибка: chmod: {error}")
