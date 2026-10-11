"""Virtual UNIX paths and owner permissions, stored entirely in memory."""

import base64


class VirtualFS:
    """Hold files, directories, permissions and the current directory."""

    def __init__(self, data=None):
        data = data if data is not None else {}
        self.files = data.setdefault("files", {})
        self.directories = data.setdefault("directories", {""})
        self.modes = data.setdefault("modes", {})
        self.cwd = ""
        for path in self.directories:
            self.modes.setdefault(path, 0o755)
        for path in self.files:
            self.modes.setdefault(path, 0o644)

    def exists(self, path):
        """Check a canonical internal path."""
        return path in self.directories or path in self.files

    def require(self, path, bits):
        """Check owner permission bits for the emulated session."""
        if not self.exists(path):
            raise ValueError(f"путь не найден: /{path}")
        if self.modes[path] & bits != bits:
            raise ValueError(f"доступ запрещён: /{path}")

    def resolve(self, value, allow_missing=False):
        """Resolve POSIX components without touching the host filesystem."""
        if not value:
            raise ValueError("пустой путь")
        parts = [] if value.startswith("/") else self.cwd.split("/")
        parts = [part for part in parts if part]
        components = value.split("/")
        for index, part in enumerate(components):
            parent = "/".join(parts)
            self.require_directory(parent)
            if part == "..":
                parts = parts[:-1]
            elif part not in ("", "."):
                parts.append(part)
            path = "/".join(parts)
            if not self.exists(path):
                if not allow_missing or index != len(components) - 1:
                    raise ValueError(f"путь не найден: {value}")
        path = "/".join(parts)
        if value.endswith("/"):
            self.require_directory(path)
        return path

    def require_directory(self, path):
        """Require a searchable directory."""
        if path not in self.directories:
            raise ValueError(f"не каталог: /{path}")
        self.require(path, 0o100)

    def children(self, path, include_hidden=False):
        """Return sorted direct children of a directory."""
        self.require_directory(path)
        self.require(path, 0o400)
        prefix = path + "/" if path else ""
        names = set()
        for item in self.directories | self.files.keys():
            if item.startswith(prefix) and item != path:
                name = item[len(prefix):]
                if "/" not in name:
                    if include_hidden or not name.startswith("."):
                        names.add(name)
        return sorted(names)

    def read_text(self, path):
        """Decode a readable UTF-8 file from its Base64 representation."""
        if path in self.directories:
            raise ValueError(f"это каталог: /{path}")
        self.require(path, 0o400)
        try:
            return base64.b64decode(self.files[path]).decode("utf-8")
        except UnicodeDecodeError as error:
            message = f"файл не является UTF-8 текстом: /{path}"
            raise ValueError(message) from error
