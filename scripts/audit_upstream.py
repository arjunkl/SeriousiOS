#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "upstream/SeriousSamClassic")
FILES = [
    ROOT / "SamTFE/Sources/CMakeLists.txt",
    ROOT / "SamTSE/Sources/CMakeLists.txt",
]

REQUIRED_PATTERNS = {
    "desktop Apple conflation": r"if\(APPLE\)",
    "runtime shared entity modules": r"add_library\(\$\{ENTITIESMPLIB\}\s+SHARED",
    "runtime shared game modules": r"add_library\(\$\{GAMEMPLIB\}\s+SHARED",
    "dynamic lookup": r"undefined dynamic_lookup",
    "cross-build ECC override": r"if\(NOT ECC\)",
    "portable C option": r"option\(USE_ASM",
}

errors: list[str] = []
for path in FILES:
    if not path.is_file():
        errors.append(f"missing expected upstream file: {path}")
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    for label, pattern in REQUIRED_PATTERNS.items():
        if re.search(pattern, text, flags=re.MULTILINE) is None:
            errors.append(f"{path}: expected architecture marker disappeared: {label}")

if errors:
    print("Upstream architecture audit failed:")
    for error in errors:
        print(f"  - {error}")
    sys.exit(1)

print("Upstream architecture markers verified.")
print("This gate does not claim iOS compatibility; it confirms that the pinned repair plan still matches upstream structure.")
