#!/usr/bin/env python3
"""Make the generated gameplay touch overlay NETRICSA-aware."""

from __future__ import annotations

import argparse
from pathlib import Path


OLD_VISIBILITY = r'''- (void)updateGameplayControlVisibility {
    const BOOL active = SeriousIOS_ApplicationGameplayControlsActive();
    for (UIButton* button in @[_fireButton, _jumpButton, _useButton, _skipButton, _pauseButton]) {
        button.hidden = !active;
    }
    if (!active && (_movementTouch != nil || _lookTouch != nil)) {
        [self releaseGameplayTouches];
    }
}'''

NEW_VISIBILITY = r'''- (void)updateGameplayControlVisibility {
    const BOOL active = SeriousIOS_ApplicationGameplayControlsActive();
    const BOOL computerActive = active && SeriousIOS_ApplicationComputerActive();

    _fireButton.hidden = !active || computerActive;
    _jumpButton.hidden = !active || computerActive;
    _useButton.hidden = !active || computerActive;
    _skipButton.hidden = !active || computerActive;
    _pauseButton.hidden = !active;
    [_pauseButton setTitle:(computerActive ? @"EXIT" : @"PAUSE")
                  forState:UIControlStateNormal];

    if ((!active || computerActive)
        && (_movementTouch != nil || _lookTouch != nil)) {
        [self releaseGameplayTouches];
    }
}'''

OLD_BEGAN = r'''- (void)touchesBegan:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    if (SeriousIOS_ApplicationGameplayControlsActive()) {
        [self beginGameplayTouches:touches];
        return;
    }
    [self routeMenuTouch:touches.anyObject activate:NO];
}'''

NEW_BEGAN = r'''- (void)touchesBegan:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    if (SeriousIOS_ApplicationComputerActive()) {
        return;
    }
    if (SeriousIOS_ApplicationGameplayControlsActive()) {
        [self beginGameplayTouches:touches];
        return;
    }
    [self routeMenuTouch:touches.anyObject activate:NO];
}'''

OLD_MOVED = r'''- (void)touchesMoved:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    if (SeriousIOS_ApplicationGameplayControlsActive()) {
        [self moveGameplayTouches:touches];
        return;
    }
    [self routeMenuTouch:touches.anyObject activate:NO];
}'''

NEW_MOVED = r'''- (void)touchesMoved:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    if (SeriousIOS_ApplicationComputerActive()) {
        return;
    }
    if (SeriousIOS_ApplicationGameplayControlsActive()) {
        [self moveGameplayTouches:touches];
        return;
    }
    [self routeMenuTouch:touches.anyObject activate:NO];
}'''

OLD_ENDED = r'''- (void)touchesEnded:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    if (SeriousIOS_ApplicationGameplayControlsActive()
        || _movementTouch != nil
        || _lookTouch != nil) {
        [self endGameplayTouches:touches];
        return;
    }
    [self routeMenuTouch:touches.anyObject activate:YES];
}'''

NEW_ENDED = r'''- (void)touchesEnded:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    if (SeriousIOS_ApplicationComputerActive()) {
        [self endGameplayTouches:touches];
        return;
    }
    if (SeriousIOS_ApplicationGameplayControlsActive()
        || _movementTouch != nil
        || _lookTouch != nil) {
        [self endGameplayTouches:touches];
        return;
    }
    [self routeMenuTouch:touches.anyObject activate:YES];
}'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_text(text: str) -> str:
    text = replace_once(
        text,
        OLD_VISIBILITY,
        NEW_VISIBILITY,
        "NETRICSA visibility",
    )
    text = replace_once(text, OLD_BEGAN, NEW_BEGAN, "NETRICSA touchesBegan")
    text = replace_once(text, OLD_MOVED, NEW_MOVED, "NETRICSA touchesMoved")
    text = replace_once(text, OLD_ENDED, NEW_ENDED, "NETRICSA touchesEnded")

    required = (
        'computerActive ? @"EXIT" : @"PAUSE"',
        "SeriousIOS_ApplicationComputerActive()",
        "_fireButton.hidden = !active || computerActive;",
        "if ((!active || computerActive)",
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"NETRICSA touch transform missing token: {token}")
    return text


def self_test() -> None:
    fixture = "\n\n".join(
        (OLD_VISIBILITY, OLD_BEGAN, OLD_MOVED, OLD_ENDED)
    )
    transformed = transform_text(fixture)
    assert transformed.count('computerActive ? @"EXIT" : @"PAUSE"') == 1
    assert transformed.count("SeriousIOS_ApplicationComputerActive()") == 4
    assert OLD_VISIBILITY not in transformed
    print("SeriousiOS NETRICSA touch self-test passed")


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
    source = args.host_source.resolve()
    if not source.is_file():
        raise SystemExit(f"host source does not exist: {source}")

    source.write_text(
        transform_text(source.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    print(f"Injected NETRICSA-aware touch controls into {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
