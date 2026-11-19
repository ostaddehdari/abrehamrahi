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


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: inject_nginx.py /path/to/srun.ir.conf", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    move_legacy_backups(path)
    text = path.read_text(encoding="utf-8")
    if "include /etc/nginx/snippets/abrehamrahi.conf;" in text:
        print(f"Nginx include already exists in {path}")
        return 0
    lines = text.splitlines(keepends=True)
    server_start = None
    domain_line = None
    depth = 0
    depths: list[int] = []
    for index, line in enumerate(lines):
        clean = line.split("#", 1)[0]
        depths.append(depth)
        if re.search(r"\bserver\s*\{", clean) and server_start is None:
            server_start = index
        if server_start is not None and re.search(r"\bserver_name\b[^;]*\bsrun\.ir\b", clean):
            domain_line = index
            break
        depth += clean.count("{") - clean.count("}")
        if server_start is not None and depth == 0:
            server_start = None
    if domain_line is None or server_start is None:
        print(f"server block for srun.ir not found in {path}", file=sys.stderr)
        return 1

    depth = 0
    closing = None
    for index in range(server_start, len(lines)):
        clean = lines[index].split("#", 1)[0]
        depth += clean.count("{") - clean.count("}")
        if depth == 0 and index > server_start:
            closing = index
            break
    if closing is None:
        print("closing brace of server block not found", file=sys.stderr)
        return 1
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"{path.parent.name}-{path.name}.bak-{int(time.time())}"
    shutil.copy2(path, backup)
    lines.insert(closing, INCLUDE + "\n")
    path.write_text("".join(lines), encoding="utf-8")
    print(f"Updated {path}; backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

