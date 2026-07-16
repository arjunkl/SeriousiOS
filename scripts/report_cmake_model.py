#!/usr/bin/env python3
"""Read CMake File API output and validate the SeriousiOS runtime-only graph."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED = {
    "TFE": {"Engine", "Entities", "Game", "Shaders", "engine_safemath"},
    "TSE": {"EngineMP", "EntitiesMP", "GameMP", "ShadersMP", "engine_safemathMP"},
}


def load_codemodel(build: Path) -> tuple[dict, Path]:
    reply_dir = build / ".cmake" / "api" / "v1" / "reply"
    indexes = sorted(reply_dir.glob("index-*.json"))
    if not indexes:
        raise FileNotFoundError(f"no CMake File API index under {reply_dir}")
    index = json.loads(indexes[-1].read_text(encoding="utf-8"))
    codemodel_ref = index.get("reply", {}).get("codemodel-v2")
    if not codemodel_ref:
        raise RuntimeError("CMake did not return codemodel-v2")
    codemodel_path = reply_dir / codemodel_ref["jsonFile"]
    return json.loads(codemodel_path.read_text(encoding="utf-8")), reply_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("build", type=Path)
    parser.add_argument("encounter", choices=("TFE", "TSE"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    build = args.build.resolve()
    codemodel, reply_dir = load_codemodel(build)
    configurations = codemodel.get("configurations", [])
    if not configurations:
        raise RuntimeError("CMake codemodel contains no configurations")

    # Xcode emits multiple configurations with the same target topology. Use
    # the first and record its name, then verify the runtime target types.
    configuration = configurations[0]
    targets: list[dict[str, object]] = []
    for target_ref in configuration.get("targets", []):
        target_path = reply_dir / target_ref["jsonFile"]
        target = json.loads(target_path.read_text(encoding="utf-8"))
        targets.append(
            {
                "name": target.get("name"),
                "type": target.get("type"),
                "artifacts": target.get("artifacts", []),
                "source_directory": target.get("paths", {}).get("source"),
                "build_directory": target.get("paths", {}).get("build"),
            }
        )

    by_name = {str(target["name"]): target for target in targets}
    missing = EXPECTED[args.encounter] - by_name.keys()
    if missing:
        raise RuntimeError(
            f"{args.encounter}: missing expected runtime targets: {sorted(missing)}"
        )

    wrong_types = {
        name: by_name[name]["type"]
        for name in sorted(EXPECTED[args.encounter])
        if by_name[name]["type"] != "STATIC_LIBRARY"
    }
    if wrong_types:
        raise RuntimeError(
            f"{args.encounter}: runtime targets are not static libraries: {wrong_types}"
        )

    executables = sorted(
        str(target["name"]) for target in targets if target["type"] == "EXECUTABLE"
    )
    if executables:
        raise RuntimeError(
            f"{args.encounter}: runtime-only graph contains executables: {executables}"
        )

    report = {
        "encounter": args.encounter,
        "configuration": configuration.get("name", ""),
        "expected_runtime_targets": sorted(EXPECTED[args.encounter]),
        "target_count": len(targets),
        "targets": sorted(targets, key=lambda item: str(item["name"])),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    markdown = [
        f"# {args.encounter} iOS CMake codemodel",
        "",
        f"Configuration: `{report['configuration']}`",
        "",
        "| Target | Type |",
        "|---|---|",
    ]
    for target in report["targets"]:
        markdown.append(f"| `{target['name']}` | `{target['type']}` |")
    args.output.with_suffix(".md").write_text("\n".join(markdown) + "\n", encoding="utf-8")

    print(
        f"{args.encounter}: {len(targets)} targets, "
        f"{len(EXPECTED[args.encounter])} required static runtime libraries, no executables"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
