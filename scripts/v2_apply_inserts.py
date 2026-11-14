#!/usr/bin/env python3
"""Insert an extra R/L exchange before each listed record's final line (dataset v2 revision helper)."""
import json, re, sys
from pathlib import Path
batch, inserts = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
text = batch.read_text(encoding="utf-8").replace("\r\n", "\n")
parts = re.split(r"(?m)^(?=### )", text)
done = 0
for i, part in enumerate(parts):
    if not part.startswith("### "):
        continue
    rid = part[4:].split("|", 1)[0].strip()
    if rid not in inserts:
        continue
    head, *lines = [ln for ln in part.rstrip("\n").split("\n")]
    lines = [ln for ln in lines if ln.strip()]
    pos = len(lines) - 1 if lines[-1].startswith("R:") else len(lines)
    lines[pos:pos] = inserts[rid] if lines[-1].startswith("R:") else inserts[rid]
    parts[i] = "\n".join([head] + lines) + "\n"
    done += 1
batch.write_text("".join(parts), encoding="utf-8")
print(f"inserted into {done} records")
