#!/usr/bin/env python3
"""Convert Apple linker output into a stable, deduplicated SeriousiOS report."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

SYMBOL_RE = re.compile(r'^\s*"([^"]+)", referenced from:$', re.MULTILINE)
DUPLICATE_RE = re.compile(r"duplicate symbol '([^']+)'")
MISSING_LIBRARY_RE = re.compile(r"library '([^']+)' not found")
MISSING_FRAMEWORK_RE = re.compile(r"framework '([^']+)' not found")
LINKER_ERROR_RE = re.compile(r"(?m)^ld: (.+)$")

SHADER_MATH_NAMES = (
    "MatrixVectorToMatrix12",
    "MatrixTranspose",
    "RotateVector",
    "TransformVertex",
)
HOST_GLOBALS = {"_hwndMain", "_pGame"}


def classify(symbol: str) -> str:
    normalized = symbol.lstrip("_")
    if normalized.startswith("SDL_"):
        return "SDL platform services"
    if symbol in HOST_GLOBALS:
        return "iOS host globals"
    if any(name in symbol for name in SHADER_MATH_NAMES):
        return "Shader math exports"
    if normalized.endswith("_DLLClass"):
        return "Entity registry"
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
    if symbol.startswith("__Z") or symbol.startswith("_Z"):
        return "C++/Engine"
    return "Other"


def read_status(path: Path | None, text: str) -> int:
    if path is not None and path.is_file():
        raw = path.read_text(encoding="utf-8", errors="replace").strip()
        try:
            return int(raw)
        except ValueError as error:
            raise RuntimeError(f"invalid link status in {path}: {raw!r}") from error
    return 1 if "ld: " in text else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("encounter", choices=("TFE", "TSE"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--status-file", type=Path)
    args = parser.parse_args()

    text = args.log.read_text(encoding="utf-8", errors="replace")
    status = read_status(args.status_file, text)
    symbols = sorted(set(SYMBOL_RE.findall(text)))
    duplicates = sorted(set(DUPLICATE_RE.findall(text)))
    libraries = sorted(set(MISSING_LIBRARY_RE.findall(text)))
    frameworks = sorted(set(MISSING_FRAMEWORK_RE.findall(text)))
    linker_errors = sorted(set(LINKER_ERROR_RE.findall(text)))
    categories = Counter(classify(symbol) for symbol in symbols)

    report = {
        "encounter": args.encounter,
        "link_status": status,
        "link_succeeded": status == 0,
        "undefined_symbol_count": len(symbols),
        "undefined_symbols": symbols,
        "category_counts": dict(sorted(categories.items())),
        "duplicate_symbols": duplicates,
        "missing_libraries": libraries,
        "missing_frameworks": frameworks,
        "linker_errors": linker_errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    markdown = [
        f"# {args.encounter} iOS dry-link report",
        "",
        f"Link status: `{status}`",
        f"Link succeeded: `{'yes' if status == 0 else 'no'}`",
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
    if linker_errors:
        markdown.extend(["", "## Linker errors", ""])
        markdown.extend(f"- `{error}`" for error in linker_errors)

    args.output.with_suffix(".md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(
        f"{args.encounter}: status={status}, {len(symbols)} undefined, "
        f"{len(duplicates)} duplicates, categories={dict(sorted(categories.items()))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
