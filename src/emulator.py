import argparse
import base64
import getpass
import shlex
import socket
import zipfile

if __package__:
    from .shell import Shell
else:
    from shell import Shell

def parse_arguments(args = None):
    parser = argparse.ArgumentParser(
        description="Эмулятор командной оболочки"
    )

    parser.add_argument(
        "--vfs",
        help="Путь к физическому расположению VFS",
    )

    parser.add_argument(
        "--script",
        help="Путь к стартовому скрипту",
    )

    return parser.parse_args(args)

def get_prompt():
    username = getpass.getuser()
    hostname = socket.gethostname()

    return f"{username}@{hostname}:~$ "

def execute_command(command, args, shell=None):
    """Execute in a supplied session, or a fresh empty session."""
    return (shell if shell is not None else Shell()).execute(command, args)

def parse_command(line):
    parts = shlex.split(line, comments=True)

    if not parts:
        return "", []

    command = parts[0]
    args = parts[1:]

    return command, args

def run_startup_script(script_path, shell=None):
    shell = shell if shell is not None else Shell()
    try:
        with open(script_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                print(f"{shell.prompt()}{line}")

                try:
                    command, args = parse_command(line)

                except ValueError:
                    print("Ошибка: некорректные кавычки")
                    continue

                if command and not execute_command(command, args, shell):
                    return False

    except (OSError, UnicodeError) as error:
        print(f"Ошибка стартового скрипта: {error}")

    return True
def read_archive(archive):
    """Build an in-memory VFS, rejecting ambiguous ZIP paths."""
    files, directories = {}, {""}
    for info in archive.infolist():
        path = info.orig_filename.rstrip("/")
        if not path:
            continue
        parts = path.split("/")
        if "\\" in path or any(p in ("", ".", "..") for p in parts):
            raise ValueError(f"недопустимый путь в ZIP: {info.filename}")
        for index in range(1, len(parts)):
            directories.add("/".join(parts[:index]))
        if info.is_dir():
            directories.add(path)
        else:
            files[path] = base64.b64encode(archive.read(info)).decode("ascii")
    if files.keys() & directories:
        raise ValueError("файл и каталог имеют одинаковый путь")
    return {"files": files, "directories": directories}


def load_vfs(vfs_path):
    try:
        with zipfile.ZipFile(vfs_path, "r") as archive:
            return read_archive(archive)

    except FileNotFoundError:
        print("Ошибка загрузки VFS: файл не найден")

    except zipfile.BadZipFile:
        print("Ошибка загрузки VFS: неверный формат ZIP")

    except (OSError, ValueError, RuntimeError, NotImplementedError) as error:
        print(f"Ошибка загрузки VFS: {error}")

    return None

def show_motd(vfs):
    motd_data = vfs["files"].get("motd")

    if motd_data is None:
        return

    try:
        data = base64.b64decode(motd_data)
        message = data.decode("utf-8")

    except UnicodeDecodeError:
        print("Ошибка: файл motd содержит некорректный текст")
        return

    print(message)

def main():
    config = parse_arguments()
    print("Параметры эмулятора:")
    print(f"VFS: {config.vfs}")
    print(f"Стартовый скрипт: {config.script}")

    vfs = None

    if config.vfs:
        vfs = load_vfs(config.vfs)

        if vfs is None:
            return

        print(f"VFS загружена: {config.vfs}")
        show_motd(vfs)

    shell = Shell(vfs)
    if config.script:
        if not run_startup_script(config.script, shell):
            return

    run_repl(shell)


def run_repl(shell):
    """Read commands until exit, EOF or a keyboard interrupt."""
    while True:
        try:
            line = input(shell.prompt())
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line.strip():
            continue

        try:

            command, args = parse_command(line)

        except ValueError:

            print("Ошибка: некорректные кавычки")
            continue


        if command and not execute_command(command, args, shell):
            break


if __name__ == '__main__':
    main()
