#!/usr/bin/env python3
"""Replace digital gameplay touch bindings with the virtual analog controller."""

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
        '''- (void)releaseMovementKeys {
    SeriousIOS_QueueSDLKey('w', false);
    SeriousIOS_QueueSDLKey('s', false);
    SeriousIOS_QueueSDLKey('a', false);
    SeriousIOS_QueueSDLKey('d', false);
}''',
        '''- (void)releaseMovementKeys {
    SeriousIOS_SetVirtualMovement(0.0f, 0.0f);
}''',
        "movement release",
    )

    text = replace_once(
        text,
        '''- (void)gameplayFireDown {
    SeriousIOS_QueueSDLMouseButton(1, true);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=fire state=down");
}

- (void)gameplayFireUp {
    SeriousIOS_QueueSDLMouseButton(1, false);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=fire state=up");
}''',
        '''- (void)gameplayFireDown {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_FIRE, true);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=fire state=down source=virtual_controller");
}

- (void)gameplayFireUp {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_FIRE, false);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=fire state=up source=virtual_controller");
}''',
        "fire action",
    )

    text = replace_once(
        text,
        '''- (void)gameplayJumpDown {
    SeriousIOS_QueueSDLKey(' ', true);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=jump state=down");
}

- (void)gameplayJumpUp {
    SeriousIOS_QueueSDLKey(' ', false);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=jump state=up");
}''',
        '''- (void)gameplayJumpDown {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_JUMP, true);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=jump state=down source=virtual_controller");
}

- (void)gameplayJumpUp {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_JUMP, false);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=jump state=up source=virtual_controller");
}''',
        "jump action",
    )

    text = replace_once(
        text,
        '''- (void)gameplayUseDown {
    SeriousIOS_QueueSDLKey('\\r', true);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=use state=down");
}

- (void)gameplayUseUp {
    SeriousIOS_QueueSDLKey('\\r', false);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=use state=up");
}''',
        '''- (void)gameplayUseDown {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_USE, true);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=use state=down source=virtual_controller");
}

- (void)gameplayUseUp {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_USE, false);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=use state=up source=virtual_controller");
}''',
        "use action",
    )

    text = replace_once(
        text,
        '''        if (touch == _movementTouch) {
            const CGFloat horizontal = MAX(-1.0, MIN(1.0, (point.x - _movementOrigin.x) / movementRadius));
            const CGFloat vertical = MAX(-1.0, MIN(1.0, (_movementOrigin.y - point.y) / movementRadius));
            const CGFloat deadZone = 0.20;
            SeriousIOS_QueueSDLKey('w', vertical > deadZone);
            SeriousIOS_QueueSDLKey('s', vertical < -deadZone);
            SeriousIOS_QueueSDLKey('d', horizontal > deadZone);
            SeriousIOS_QueueSDLKey('a', horizontal < -deadZone);
        } else if (touch == _lookTouch) {''',
        '''        if (touch == _movementTouch) {
            const CGFloat rawRight = (point.x - _movementOrigin.x) / movementRadius;
            const CGFloat rawForward = (_movementOrigin.y - point.y) / movementRadius;
            const CGFloat rawMagnitude = hypot(rawRight, rawForward);
            const CGFloat boundedMagnitude = MIN(1.0, rawMagnitude);
            const CGFloat radialDeadZone = 0.16;
            CGFloat forward = 0.0;
            CGFloat right = 0.0;
            if (boundedMagnitude > radialDeadZone && rawMagnitude > 0.0001) {
                const CGFloat scaledMagnitude =
                    (boundedMagnitude - radialDeadZone) / (1.0 - radialDeadZone);
                const CGFloat directionScale = scaledMagnitude / rawMagnitude;
                forward = rawForward * directionScale;
                right = rawRight * directionScale;
            }
            SeriousIOS_SetVirtualMovement((float)forward, (float)right);
        } else if (touch == _lookTouch) {''',
        "radial analog movement",
    )

    forbidden = (
        "SeriousIOS_QueueSDLKey('w'",
        "SeriousIOS_QueueSDLKey('s'",
        "SeriousIOS_QueueSDLKey('a'",
        "SeriousIOS_QueueSDLKey('d'",
    )
    for token in forbidden:
        if token in text:
            raise RuntimeError(f"digital movement binding remains: {token}")

    required = (
        "SeriousIOS_SetVirtualMovement((float)forward, (float)right)",
        "radialDeadZone = 0.16",
        "SERIOUSIOS_ACTION_FIRE",
        "SERIOUSIOS_ACTION_JUMP",
        "SERIOUSIOS_ACTION_USE",
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"analog touch transform missing token: {token}")
    return text


def self_test() -> None:
    fixture = r'''- (void)releaseMovementKeys {
    SeriousIOS_QueueSDLKey('w', false);
    SeriousIOS_QueueSDLKey('s', false);
    SeriousIOS_QueueSDLKey('a', false);
    SeriousIOS_QueueSDLKey('d', false);
}
- (void)gameplayFireDown {
    SeriousIOS_QueueSDLMouseButton(1, true);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=fire state=down");
}

- (void)gameplayFireUp {
    SeriousIOS_QueueSDLMouseButton(1, false);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=fire state=up");
}
- (void)gameplayJumpDown {
    SeriousIOS_QueueSDLKey(' ', true);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=jump state=down");
}

- (void)gameplayJumpUp {
    SeriousIOS_QueueSDLKey(' ', false);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=jump state=up");
}
- (void)gameplayUseDown {
    SeriousIOS_QueueSDLKey('\r', true);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=use state=down");
}

- (void)gameplayUseUp {
    SeriousIOS_QueueSDLKey('\r', false);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=use state=up");
}
        if (touch == _movementTouch) {
            const CGFloat horizontal = MAX(-1.0, MIN(1.0, (point.x - _movementOrigin.x) / movementRadius));
            const CGFloat vertical = MAX(-1.0, MIN(1.0, (_movementOrigin.y - point.y) / movementRadius));
            const CGFloat deadZone = 0.20;
            SeriousIOS_QueueSDLKey('w', vertical > deadZone);
            SeriousIOS_QueueSDLKey('s', vertical < -deadZone);
            SeriousIOS_QueueSDLKey('d', horizontal > deadZone);
            SeriousIOS_QueueSDLKey('a', horizontal < -deadZone);
        } else if (touch == _lookTouch) {'''
    transformed = transform_text(fixture)
    assert "radialDeadZone = 0.16" in transformed
    assert "SERIOUSIOS_ACTION_FIRE" in transformed
    assert "SeriousIOS_QueueSDLKey('w'" not in transformed
    print("SeriousiOS analog touch transform self-test passed")


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
    print(f"Injected virtual analog gameplay controls into {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
