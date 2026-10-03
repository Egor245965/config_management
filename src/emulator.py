import argparse
import base64
import getpass
import shlex
import socket
import zipfile

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

def execute_command(command, args):
    if command == "ls":
        print("ls", args)
    elif command == "cd":
        if len(args) > 1:
            print("Ошибка: cd принимает не более одного аргумента")
        else:
            print("cd", args)
    elif command == "exit":
        if args:
            print("Ошибка: exit не принимает аргументы")
            return True
        return False
    else:
        print(f"Ошибка: неизвестная команда '{command}'")
    return True

def parse_command(line):
    parts = shlex.split(line)

    command = parts[0]
    args = parts[1:]

    return command, args

def run_startup_script(script_path):
    try:
        with open(script_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                print(f"{get_prompt()}{line}")

                try:
                    command, args = parse_command(line)

                except ValueError:
                    print("Ошибка: некорректные кавычки")
                    continue

                if not execute_command(command, args):
                    return False

    except OSError as error:
        print(f"Ошибка стартового скрипта: {error}")

    return True
def load_vfs(vfs_path):
    try:
        with zipfile.ZipFile(vfs_path, "r") as archive:
            files = {}
            directories = {""}

            for info in archive.infolist():
                path = info.filename.rstrip("/")

                if not path:
                    continue

                if info.is_dir():
                    directories.add(path)
                    continue

                parts = path.split("/")

                for i in range(1, len(parts)):
                    directory = "/".join(parts[:i])
                    directories.add(directory)

                data = archive.read(info.filename)

                files[path] = base64.b64encode(data).decode("ascii")

            return {
                "files": files,
                "directories": directories,
            }

    except FileNotFoundError:
        print("Ошибка загрузки VFS: файл не найден")

    except zipfile.BadZipFile:
        print("Ошибка загрузки VFS: неверный формат ZIP")

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
    print(f"Старотовый скрипт: {config.script}")

    vfs = None

    if config.vfs:
        vfs = load_vfs(config.vfs)

        if vfs is None:
            return

        print(f"VFS загружена: {config.vfs}")
        show_motd(vfs)

    if config.script:
        if not run_startup_script(config.script):
            return

    while True:
        line = input(get_prompt())
        if not line.strip():
            continue

        try:

            command, args = parse_command(line)

        except ValueError:

            print("Ошибка: некорректные кавычки")
            continue


        if not execute_command(command, args):
            break
        

if __name__ == '__main__':
    main()