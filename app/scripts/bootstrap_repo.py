from __future__ import annotations

import subprocess
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    commands = [
        ["git", "init"],
        ["git", "checkout", "-b", "main"],
    ]
    for command in commands:
        subprocess.run(command, cwd=root, check=False)


if __name__ == "__main__":
    main()
