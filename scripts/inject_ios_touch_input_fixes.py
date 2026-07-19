#!/usr/bin/env python3
"""Correct touch behavior, add optional fire/pause UI, then inject clean profiling."""

from __future__ import annotations

import argparse
from pathlib import Path

import inject_ios_fire_gestures
import inject_ios_high_refresh
import inject_ios_pause_return
import inject_ios_performance_profiler_driver


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
    # The generated Objective-C++ is semantically stable, but two alignment
    # spaces differ from the transform fixture. Normalize only those declarations
    # so behavior does not depend on cosmetic indentation.
    actual_label = '''    UILabel* gyroLabel = [self controlsEditorLabelWithText:@"Gyro aiming"
                                                       font:[UIFont systemFontOfSize:14.0 weight:UIFontWeightSemibold]];'''
    normalized_label = '''    UILabel* gyroLabel = [self controlsEditorLabelWithText:@"Gyro aiming"
                                                        font:[UIFont systemFontOfSize:14.0 weight:UIFontWeightSemibold]];'''
    text = replace_once(
        text, actual_label, normalized_label, "gyro label formatting normalization")

    actual_lookup = '''    UIView* gyroLabelView = [self descendantViewWithAccessibilityIdentifier:@"gyro-enabled-label"
                                                                      inView:_controlsEditorPanel];'''
    normalized_lookup = '''    UIView* gyroLabelView = [self descendantViewWithAccessibilityIdentifier:@"gyro-enabled-label"
                                                                       inView:_controlsEditorPanel];'''
    text = replace_once(
        text, actual_lookup, normalized_lookup, "gyro lookup formatting normalization")
    return text


def prepare_computer_touch_finish_call(text: str) -> str:
    # touchesEnded has separate computer and ordinary-gameplay branches. Mark the
    # computer branch first so the fire transform sees exactly one ordinary call.
    old = '''    if (SeriousIOS_ApplicationComputerActive()) {
        [self endGameplayTouches:touches];
        return;
    }'''
    new = '''    if (SeriousIOS_ApplicationComputerActive()) {
        [self endGameplayTouches:touches cancelled:NO];
        return;
    }'''
    return replace_once(text, old, new, "computer touch-finish branch")


def repair_normal_touch_finish_calls(text: str) -> str:
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
    inject_ios_pause_return.self_test()
    inject_ios_performance_profiler_driver.self_test()
    inject_ios_high_refresh.self_test()
    print("SeriousiOS touch, optional-fire, pause-return, and clean high-refresh self-tests passed")


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
    text = prepare_computer_touch_finish_call(text)
    text = inject_ios_fire_gestures.transform_text(text)
    text = repair_normal_touch_finish_calls(text)
    text = inject_ios_pause_return.transform_text(text)
    text = inject_ios_performance_profiler_driver.transform_text(text)
    text = inject_ios_high_refresh.transform_text(text)
    path.write_text(text, encoding="utf-8")
    print(f"Corrected touch input and injected clean adaptive high refresh in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
