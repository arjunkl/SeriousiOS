#!/usr/bin/env python3
"""Correct gyro direction and allow simultaneous gameplay touch actions."""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_text(text: str) -> str:
    text = replace_once(
        text,
        "    button.exclusiveTouch = YES;",
        "    button.exclusiveTouch = NO;",
        "simultaneous control touches",
    )
    text = replace_once(
        text,
        "    const double accumulatedX = yawRate * deltaTime * pointsPerRadian + _gyroRemainderX;",
        "    const double accumulatedX = -yawRate * deltaTime * pointsPerRadian + _gyroRemainderX;",
        "gyro horizontal direction",
    )
    text = replace_once(
        text,
        "    const double accumulatedY = pitchRate * deltaTime * pointsPerRadian + _gyroRemainderY;",
        "    const double accumulatedY = -pitchRate * deltaTime * pointsPerRadian + _gyroRemainderY;",
        "gyro vertical direction",
    )
    text = replace_once(
        text,
        '            "gyro_configured available=1 enabled=%d update_hz=100 sensitivity=%.3f",',
        '            "gyro_configured available=1 enabled=%d update_hz=100 sensitivity=%.3f axis_sign=-1",',
        "gyro direction diagnostic",
    )

    required = (
        "button.exclusiveTouch = NO;",
        "const double accumulatedX = -yawRate * deltaTime * pointsPerRadian",
        "const double accumulatedY = -pitchRate * deltaTime * pointsPerRadian",
        "axis_sign=-1",
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"touch input fix missing token: {token}")

    forbidden = (
        "button.exclusiveTouch = YES;",
        "const double accumulatedX = yawRate * deltaTime * pointsPerRadian",
        "const double accumulatedY = pitchRate * deltaTime * pointsPerRadian",
    )
    for token in forbidden:
        if token in text:
            raise RuntimeError(f"obsolete touch input behavior remains: {token}")
    return text


def self_test() -> None:
    fixture = '''    button.exclusiveTouch = YES;
    const double accumulatedX = yawRate * deltaTime * pointsPerRadian + _gyroRemainderX;
    const double accumulatedY = pitchRate * deltaTime * pointsPerRadian + _gyroRemainderY;
            "gyro_configured available=1 enabled=%d update_hz=100 sensitivity=%.3f",
'''
    transformed = transform_text(fixture)
    assert "button.exclusiveTouch = NO;" in transformed
    assert "-yawRate * deltaTime" in transformed
    assert "-pitchRate * deltaTime" in transformed
    assert "axis_sign=-1" in transformed
    print("SeriousiOS gyro-direction and simultaneous-touch self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("host_source", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        if args.host_source is None:
            return 0
    if args.host_source is None:
        parser.error("host_source is required unless only --self-test is used")

    path = args.host_source.resolve()
    if not path.is_file():
        raise SystemExit(f"host source does not exist: {path}")
    path.write_text(transform_text(path.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"Corrected gyro direction and enabled simultaneous touch actions in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
