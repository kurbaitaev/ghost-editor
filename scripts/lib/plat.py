"""Cross-platform helpers (macOS, Linux, Windows) for the Python scripts.

- `tool(name)`  resolves a CLI on PATH, including the `.cmd` / `.exe` shims npm and pip install on Windows
                 (`npx` is `npx.cmd` there, which subprocess only finds by full path).
- `npx(*args)`  the argv for `npx <args>`, ready for subprocess.
- `venv_python(venv)`  the interpreter inside a venv (`bin/python` or `Scripts/python.exe`).
- `python_cmd()`  how to call Python on this machine, for messages shown to the user.
- `open_path(p)`  open a file in the default app (`open`, `xdg-open` or os.startfile).
"""
import os
import shutil
import subprocess
import sys

WIN = sys.platform == "win32"


def tool(name):
    p = shutil.which(name)
    if p:
        return p
    if WIN:
        for ext in (".cmd", ".exe", ".bat"):
            p = shutil.which(name + ext)
            if p:
                return p
    return name


def npx(*args):
    return [tool("npx"), *args]


def venv_python(venv):
    venv = os.path.expanduser(venv)
    if WIN:
        return os.path.join(venv, "Scripts", "python.exe")
    return os.path.join(venv, "bin", "python")


def python_cmd():
    return "python" if WIN else "python3"


def open_path(p):
    if WIN:
        os.startfile(p)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.run(["open", p])
    else:
        subprocess.run(["xdg-open", p])
