#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
import sys
import time
from pathlib import Path

INCLUDE = "    include /etc/nginx/snippets/abrehamrahi.conf;"
BACKUP_DIR = Path("/var/backups/abrehamrahi/nginx")


def move_legacy_backups(path: Path) -> None:
    """Move old backups out of directories loaded by nginx.conf."""
    legacy_backups = sorted(path.parent.glob(path.name + ".bak-*"))
    if not legacy_backups:
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for backup in legacy_backups:
        destination = BACKUP_DIR / f"{path.parent.name}-{backup.name}"
        if destination.exists():
            destination = BACKUP_DIR / f"{destination.name}-{int(time.time())}"
        shutil.move(str(backup), destination)
        print(f"Moved legacy Nginx backup out of the active config directory: {destination}")


def find_server_blocks(lines: list[str]) -> list[tuple[int, int]]:
    blocks: list[tuple[int, int]] = []
    depth = 0
    server_start: int | None = None
    server_base_depth = 0
    for index, line in enumerate(lines):
        clean = line.split("#", 1)[0]
        if server_start is None and re.search(r"\bserver\s*\{", clean):
            server_start = index
            server_base_depth = depth
        depth += clean.count("{") - clean.count("}")
        if server_start is not None and depth == server_base_depth:
            blocks.append((server_start, index))
            server_start = None
    return blocks


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: inject_nginx.py /path/to/srun.ir.conf", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    move_legacy_backups(path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    matching_blocks: list[tuple[int, int]] = []
    for start, end in find_server_blocks(lines):
        block = "".join(lines[start : end + 1])
        if re.search(r"\bserver_name\b[^;]*\bsrun\.ir\b", block):
            matching_blocks.append((start, end))
    if not matching_blocks:
        print(f"server block for srun.ir not found in {path}", file=sys.stderr)
        return 1

    missing_include: list[tuple[int, int]] = []
    for start, end in matching_blocks:
        block = "".join(lines[start : end + 1])
        if "include /etc/nginx/snippets/abrehamrahi.conf;" not in block:
            missing_include.append((start, end))
    if not missing_include:
        print(f"Nginx include already exists in all srun.ir server blocks in {path}")
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"{path.parent.name}-{path.name}.bak-{int(time.time())}"
    shutil.copy2(path, backup)
    for _start, closing in reversed(missing_include):
        lines.insert(closing, INCLUDE + "\n")
    path.write_text("".join(lines), encoding="utf-8")
    print(
        f"Updated {len(missing_include)} srun.ir server block(s) in {path}; "
        f"backup: {backup}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

