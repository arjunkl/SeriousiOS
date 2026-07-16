#!/usr/bin/env python3
"""Inventory the pinned SeriousSamClassic build graph before iOS transformation."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

COMMAND_RE = re.compile(
    r"(?is)\b(add_library|add_executable|target_link_libraries)\s*\((.*?)\)"
)
TOKEN_RE = re.compile(r'"([^"]*)"|([^\s]+)')
LIBRARY_KINDS = {"STATIC", "SHARED", "MODULE", "OBJECT", "INTERFACE"}
LOADER_TOKENS = (
    "dlopen(",
    "dlsym(",
    "LoadLibrary",
    "GetProcAddress",
    "CUnixDynamicLoader",
    "CDynamicLoader",
)
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".inl", ".mm"}


def tokens(body: str) -> list[str]:
    body = re.sub(r"(?m)#.*$", "", body)
    result: list[str] = []
    for quoted, bare in TOKEN_RE.findall(body):
        token = quoted or bare
        if token:
            result.append(token)
    return result


def parse_cmake(path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    targets: list[dict[str, object]] = []
    links: list[dict[str, object]] = []

    for command, body in COMMAND_RE.findall(text):
        args = tokens(body)
        if not args:
            continue
        if command == "add_executable":
            targets.append(
                {"name": args[0], "kind": "EXECUTABLE", "cmake": str(path)}
            )
        elif command == "add_library":
            kind = "UNSPECIFIED"
            if len(args) > 1 and args[1].upper() in LIBRARY_KINDS:
                kind = args[1].upper()
            targets.append({"name": args[0], "kind": kind, "cmake": str(path)})
        else:
            dependencies = [
                item
                for item in args[1:]
                if item.upper() not in {"PUBLIC", "PRIVATE", "INTERFACE", "LINK_PUBLIC", "LINK_PRIVATE"}
            ]
            links.append(
                {
                    "target": args[0],
                    "dependencies": dependencies,
                    "cmake": str(path),
                }
            )
    return targets, links


def loader_hits(root: Path) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), 1):
            matched = [token for token in LOADER_TOKENS if token in line]
            if matched:
                hits.append(
                    {
                        "path": str(path.relative_to(root)),
                        "line": line_number,
                        "tokens": matched,
                        "text": line.strip()[:240],
                    }
                )
    return hits


def encounter_report(upstream: Path, encounter: str) -> dict[str, object]:
    source_root = upstream / f"Sam{encounter}" / "Sources"
    if not source_root.is_dir():
        raise FileNotFoundError(source_root)

    targets: list[dict[str, object]] = []
    links: list[dict[str, object]] = []
    for cmake in source_root.rglob("CMakeLists.txt"):
        found_targets, found_links = parse_cmake(cmake)
        for item in found_targets:
            item["cmake"] = str(Path(str(item["cmake"])).relative_to(upstream))
        for item in found_links:
            item["cmake"] = str(Path(str(item["cmake"])).relative_to(upstream))
        targets.extend(found_targets)
        links.extend(found_links)

    counts: dict[str, int] = {}
    for target in targets:
        kind = str(target["kind"])
        counts[kind] = counts.get(kind, 0) + 1

    if counts.get("SHARED", 0) < 3:
        raise RuntimeError(f"{encounter}: expected at least three shared runtime modules")
    if counts.get("EXECUTABLE", 0) < 1:
        raise RuntimeError(f"{encounter}: expected a game executable")

    return {
        "source_root": str(source_root.relative_to(upstream)),
        "target_counts": counts,
        "targets": targets,
        "link_edges": links,
        "dynamic_loader_hits": loader_hits(source_root),
    }


def write_markdown(report: dict[str, object], output: Path) -> None:
    lines = [
        "# SeriousSamClassic dependency graph baseline",
        "",
        f"Pinned commit: `{report['commit']}`",
        "",
    ]
    for encounter in ("TFE", "TSE"):
        data = report["encounters"][encounter]  # type: ignore[index]
        lines.extend(
            [
                f"## {encounter}",
                "",
                f"Targets: `{sum(data['target_counts'].values())}`",  # type: ignore[index]
                f"Link declarations: `{len(data['link_edges'])}`",  # type: ignore[index]
                f"Dynamic-loader references: `{len(data['dynamic_loader_hits'])}`",  # type: ignore[index]
                "",
                "| Kind | Count |",
                "|---|---:|",
            ]
        )
        for kind, count in sorted(data["target_counts"].items()):  # type: ignore[index]
            lines.append(f"| {kind} | {count} |")
        lines.extend(["", "### Shared modules", ""])
        for target in data["targets"]:  # type: ignore[index]
            if target["kind"] == "SHARED":
                lines.append(f"- `{target['name']}` from `{target['cmake']}`")
        lines.extend(["", "### Dynamic-loader references", ""])
        for hit in data["dynamic_loader_hits"][:40]:  # type: ignore[index]
            lines.append(
                f"- `{hit['path']}:{hit['line']}`: `{', '.join(hit['tokens'])}`"
            )
        lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    upstream = args.upstream.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True
    ).strip()

    report: dict[str, object] = {
        "commit": commit,
        "encounters": {
            "TFE": encounter_report(upstream, "TFE"),
            "TSE": encounter_report(upstream, "TSE"),
        },
    }
    (args.output / "dependency-graph.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    write_markdown(report, args.output / "dependency-graph.md")
    print((args.output / "dependency-graph.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
