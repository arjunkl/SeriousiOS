#!/usr/bin/env python3
"""Correct gyro direction, enable simultaneous touches, then add optional fire gestures."""

from __future__ import annotations

import argparse
from pathlib import Path

import inject_ios_fire_gestures


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


def normalize_generated_host_for_fire_transform(text: str) -> str:
    # The generated Objective-C++ is semantically stable, but one alignment space
    # differs from the transform fixture. Normalize only that declaration so the
    # feature transform does not depend on cosmetic indentation.
    actual = '''    UILabel* gyroLabel = [self controlsEditorLabelWithText:@"Gyro aiming"
                                                       font:[UIFont systemFontOfSize:14.0 weight:UIFontWeightSemibold]];'''
    normalized = '''    UILabel* gyroLabel = [self controlsEditorLabelWithText:@"Gyro aiming"
                                                        font:[UIFont systemFontOfSize:14.0 weight:UIFontWeightSemibold]];'''
    text = replace_once(text, actual, normalized, "gyro label formatting normalization")
    return text


def repair_normal_touch_finish_calls(text: str) -> str:
    # The host has two ordinary touches-ended branches: one for the computer
    # state and one for gameplay. The fire transform intentionally makes the
    # finish method cancellation-aware; ensure every ordinary branch passes NO.
    remaining = "[self endGameplayTouches:touches];"
    replacement = "[self endGameplayTouches:touches cancelled:NO];"
    if remaining in text:
        text = text.replace(remaining, replacement)
    if remaining in text:
        raise RuntimeError("uncategorized touch-finish call remains")
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
    inject_ios_fire_gestures.self_test()
    print("SeriousiOS gyro, simultaneous-touch, and optional-fire self-tests passed")


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
    text = transform_text(path.read_text(encoding="utf-8"))
    text = normalize_generated_host_for_fire_transform(text)
    text = inject_ios_fire_gestures.transform_text(text)
    text = repair_normal_touch_finish_calls(text)
    path.write_text(text, encoding="utf-8")
    print(f"Corrected gyro, simultaneous touches, and optional firing in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
