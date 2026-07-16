#!/usr/bin/env python3
"""Convert Apple linker output into a stable, deduplicated SeriousiOS report."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

SYMBOL_RE = re.compile(r'^\s*"([^"]+)", referenced from:$')
DUPLICATE_RE = re.compile(r"duplicate symbol '([^']+)'")
MISSING_LIBRARY_RE = re.compile(r"library '([^']+)' not found")
MISSING_FRAMEWORK_RE = re.compile(r"framework '([^']+)' not found")


def classify(symbol: str) -> str:
    normalized = symbol.lstrip("_")
    if normalized.startswith("SDL_"):
        return "SDL"
    if normalized.startswith(("ov_", "vorbis_", "ogg_")):
        return "Ogg/Vorbis"
    if normalized.startswith(("gl", "egl")):
        return "OpenGL/OpenGL ES"
    if normalized.startswith(("OBJC_", "UIApplication", "UIView", "UIWindow")):
        return "UIKit/Objective-C"
    if normalized.startswith(("Audio", "AVAudio", "alc", "al")):
        return "Audio"
    if normalized.startswith(("pthread_", "socket", "connect", "recv", "send")):
        return "libSystem"
    if normalized.startswith("Z") or normalized.startswith("_Z"):
        return "C++/Engine"
    return "Other"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("encounter", choices=("TFE", "TSE"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    text = args.log.read_text(encoding="utf-8", errors="replace")
    symbols = sorted(set(SYMBOL_RE.findall(text)))
    duplicates = sorted(set(DUPLICATE_RE.findall(text)))
    libraries = sorted(set(MISSING_LIBRARY_RE.findall(text)))
    frameworks = sorted(set(MISSING_FRAMEWORK_RE.findall(text)))
    categories = Counter(classify(symbol) for symbol in symbols)

    report = {
        "encounter": args.encounter,
        "link_succeeded": "dry-link-status" not in text and not symbols and "ld: " not in text,
        "undefined_symbol_count": len(symbols),
        "undefined_symbols": symbols,
        "category_counts": dict(sorted(categories.items())),
        "duplicate_symbols": duplicates,
        "missing_libraries": libraries,
        "missing_frameworks": frameworks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    markdown = [
        f"# {args.encounter} iOS dry-link report",
        "",
        f"Undefined symbols: `{len(symbols)}`",
        f"Duplicate symbols: `{len(duplicates)}`",
        "",
        "## Undefined symbols by subsystem",
        "",
        "| Subsystem | Count |",
        "|---|---:|",
    ]
    for category, count in sorted(categories.items()):
        markdown.append(f"| {category} | {count} |")

    if symbols:
        markdown.extend(["", "## Undefined symbols", ""])
        markdown.extend(f"- `{symbol}`" for symbol in symbols)
    if duplicates:
        markdown.extend(["", "## Duplicate symbols", ""])
        markdown.extend(f"- `{symbol}`" for symbol in duplicates)
    if libraries:
        markdown.extend(["", "## Missing libraries", ""])
        markdown.extend(f"- `{library}`" for library in libraries)
    if frameworks:
        markdown.extend(["", "## Missing frameworks", ""])
        markdown.extend(f"- `{framework}`" for framework in frameworks)

    args.output.with_suffix(".md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(
        f"{args.encounter}: {len(symbols)} undefined, {len(duplicates)} duplicates, "
        f"categories={dict(sorted(categories.items()))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
