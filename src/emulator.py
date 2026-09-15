import getpass
import socket
import shlex

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

def main():

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