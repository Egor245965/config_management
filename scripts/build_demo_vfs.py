"""Generate a disposable ZIP fixture for the stage 4 demos."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    """Write only the generated demo ZIP; preserve existing VFS archives."""
    root = Path(__file__).resolve().parents[1]
    output = root / "vfs" / "demo.zip"
    output.parent.mkdir(exist_ok=True)
    entries = {
        "motd": "Демонстрация этапа 4, вариант 7.\n",
        "lines.txt": "".join(f"Строка {i}\n" for i in range(1, 16)),
        "home/user/documents/file.txt": "Первая строка\nВторая строка\n",
        "My Documents/notes.txt": "Файл с пробелами в пути\n",
        "empty.txt": "",
        ".hidden": "Скрытый файл\n",
        "binary.bin": b"\x00\xff\xfe",
        "empty-dir/": "",
    }
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    print(f"Demo VFS: {output}")


if __name__ == "__main__":
    main()
