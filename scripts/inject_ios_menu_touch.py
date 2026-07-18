#!/usr/bin/env python3
"""Inject native menu and minimal eDuke32-style gameplay touch controls."""

from __future__ import annotations

import argparse
from pathlib import Path


GAMEPLAY_IVARS = '''    UIButton* _fireButton;
    UIButton* _jumpButton;
    UIButton* _useButton;
    UIButton* _skipButton;
    UIButton* _pauseButton;
    UITouch* _movementTouch;
    UITouch* _lookTouch;
    CGPoint _movementOrigin;
    CGPoint _lookPrevious;
'''

GAMEPLAY_BUTTONS = r'''    _fireButton = [UIButton buttonWithType:UIButtonTypeSystem];
    _jumpButton = [UIButton buttonWithType:UIButtonTypeSystem];
    _useButton = [UIButton buttonWithType:UIButtonTypeSystem];
    _skipButton = [UIButton buttonWithType:UIButtonTypeSystem];
    _pauseButton = [UIButton buttonWithType:UIButtonTypeSystem];

    for (UIButton* button in @[_fireButton, _jumpButton, _useButton, _skipButton, _pauseButton]) {
        UIButtonConfiguration* configuration = [UIButtonConfiguration filledButtonConfiguration];
        configuration.cornerStyle = UIButtonConfigurationCornerStyleCapsule;
        configuration.baseBackgroundColor = [UIColor colorWithWhite:0.05 alpha:0.58];
        configuration.baseForegroundColor = UIColor.whiteColor;
        button.configuration = configuration;
        button.hidden = YES;
        button.alpha = 0.82;
        button.titleLabel.font = [UIFont systemFontOfSize:14.0 weight:UIFontWeightBold];
        [self addSubview:button];
    }

    [_fireButton setTitle:@"FIRE" forState:UIControlStateNormal];
    [_jumpButton setTitle:@"JUMP" forState:UIControlStateNormal];
    [_useButton setTitle:@"USE" forState:UIControlStateNormal];
    [_skipButton setTitle:@"SKIP" forState:UIControlStateNormal];
    [_pauseButton setTitle:@"PAUSE" forState:UIControlStateNormal];

    [_fireButton addTarget:self action:@selector(gameplayFireDown)
          forControlEvents:UIControlEventTouchDown];
    [_fireButton addTarget:self action:@selector(gameplayFireUp)
          forControlEvents:UIControlEventTouchUpInside | UIControlEventTouchUpOutside | UIControlEventTouchCancel];
    [_jumpButton addTarget:self action:@selector(gameplayJumpDown)
          forControlEvents:UIControlEventTouchDown];
    [_jumpButton addTarget:self action:@selector(gameplayJumpUp)
          forControlEvents:UIControlEventTouchUpInside | UIControlEventTouchUpOutside | UIControlEventTouchCancel];
    [_useButton addTarget:self action:@selector(gameplayUseDown)
          forControlEvents:UIControlEventTouchDown];
    [_useButton addTarget:self action:@selector(gameplayUseUp)
          forControlEvents:UIControlEventTouchUpInside | UIControlEventTouchUpOutside | UIControlEventTouchCancel];
    [_skipButton addTarget:self action:@selector(gameplaySkip)
          forControlEvents:UIControlEventTouchUpInside];
    [_pauseButton addTarget:self action:@selector(gameplayPause)
          forControlEvents:UIControlEventTouchUpInside];
'''

TOUCH_METHODS = r'''- (void)layoutGameplayControls {
    const CGRect bounds = self.bounds;
    const CGFloat width = CGRectGetWidth(bounds);
    const CGFloat height = CGRectGetHeight(bounds);
    if (width <= 0.0 || height <= 0.0) {
        return;
    }

    const CGFloat unit = MIN(width, height);
    const CGFloat actionSize = MAX(56.0, MIN(84.0, unit * 0.145));
    const CGFloat fireSize = actionSize * 1.18;
    const CGFloat margin = MAX(14.0, unit * 0.025);
    const CGFloat gap = MAX(9.0, unit * 0.015);

    _fireButton.frame = CGRectMake(
        width - margin - fireSize,
        height - margin - fireSize,
        fireSize,
        fireSize);
    _jumpButton.frame = CGRectMake(
        CGRectGetMinX(_fireButton.frame) - gap - actionSize,
        height - margin - actionSize,
        actionSize,
        actionSize);
    _useButton.frame = CGRectMake(
        width - margin - actionSize,
        CGRectGetMinY(_fireButton.frame) - gap - actionSize,
        actionSize,
        actionSize);

    const CGFloat topButtonWidth = MAX(70.0, actionSize * 1.18);
    const CGFloat topButtonHeight = MAX(38.0, actionSize * 0.58);
    _pauseButton.frame = CGRectMake(
        width - margin - topButtonWidth,
        self.safeAreaInsets.top + 8.0,
        topButtonWidth,
        topButtonHeight);
    _skipButton.frame = CGRectMake(
        CGRectGetMinX(_pauseButton.frame) - gap - topButtonWidth,
        self.safeAreaInsets.top + 8.0,
        topButtonWidth,
        topButtonHeight);
}

- (void)releaseMovementKeys {
    SeriousIOS_QueueSDLKey('w', false);
    SeriousIOS_QueueSDLKey('s', false);
    SeriousIOS_QueueSDLKey('a', false);
    SeriousIOS_QueueSDLKey('d', false);
}

- (void)releaseGameplayTouches {
    [self releaseMovementKeys];
    _movementTouch = nil;
    _lookTouch = nil;
}

- (void)updateGameplayControlVisibility {
    const BOOL active = SeriousIOS_ApplicationGameplayControlsActive();
    for (UIButton* button in @[_fireButton, _jumpButton, _useButton, _skipButton, _pauseButton]) {
        button.hidden = !active;
    }
    if (!active && (_movementTouch != nil || _lookTouch != nil)) {
        [self releaseGameplayTouches];
    }
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

- (void)gameplaySkip {
    SeriousIOS_QueueSDLKey(' ', true);
    SeriousIOS_QueueSDLKey('\r', true);
    SeriousIOS_QueueSDLMouseButton(1, true);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=skip pulse=down");
    dispatch_after(
        dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.12 * NSEC_PER_SEC)),
        dispatch_get_main_queue(), ^{
            SeriousIOS_QueueSDLKey(' ', false);
            SeriousIOS_QueueSDLKey('\r', false);
            SeriousIOS_QueueSDLMouseButton(1, false);
            SeriousIOS_DiagnosticsLog("input", "touch_control action=skip pulse=up");
        });
}

- (void)gameplayPause {
    SeriousIOS_QueueSDLKey(27, true);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=pause pulse=down");
    dispatch_after(
        dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.08 * NSEC_PER_SEC)),
        dispatch_get_main_queue(), ^{
            SeriousIOS_QueueSDLKey(27, false);
            SeriousIOS_DiagnosticsLog("input", "touch_control action=pause pulse=up");
        });
}

- (void)routeMenuTouch:(UITouch*)touch activate:(BOOL)activate {
    if (touch == nil || _drawableWidth <= 0 || _drawableHeight <= 0) {
        return;
    }

    const CGRect bounds = self.bounds;
    if (CGRectGetWidth(bounds) <= 0.0 || CGRectGetHeight(bounds) <= 0.0) {
        return;
    }

    const CGPoint point = [touch locationInView:self];
    const CGFloat normalizedX = point.x / CGRectGetWidth(bounds);
    const CGFloat normalizedY = point.y / CGRectGetHeight(bounds);
    const int pixelX = (int)(normalizedX * (CGFloat)(_drawableWidth - 1) + 0.5);
    const int pixelY = (int)(normalizedY * (CGFloat)(_drawableHeight - 1) + 0.5);

    if (activate) {
        SeriousIOS_ApplicationMenuPointerActivate(pixelX, pixelY);
    } else {
        SeriousIOS_ApplicationMenuPointerMove(pixelX, pixelY);
    }
}

- (void)beginGameplayTouches:(NSSet<UITouch*>*)touches {
    const CGFloat movementBoundary = CGRectGetWidth(self.bounds) * 0.46;
    for (UITouch* touch in touches) {
        const CGPoint point = [touch locationInView:self];
        if (_movementTouch == nil && point.x < movementBoundary) {
            _movementTouch = touch;
            _movementOrigin = point;
            [self releaseMovementKeys];
        } else if (_lookTouch == nil) {
            _lookTouch = touch;
            _lookPrevious = point;
        }
    }
}

- (void)moveGameplayTouches:(NSSet<UITouch*>*)touches {
    const CGFloat movementRadius = MAX(55.0, MIN(CGRectGetWidth(self.bounds), CGRectGetHeight(self.bounds)) * 0.13);
    for (UITouch* touch in touches) {
        const CGPoint point = [touch locationInView:self];
        if (touch == _movementTouch) {
            const CGFloat horizontal = MAX(-1.0, MIN(1.0, (point.x - _movementOrigin.x) / movementRadius));
            const CGFloat vertical = MAX(-1.0, MIN(1.0, (_movementOrigin.y - point.y) / movementRadius));
            const CGFloat deadZone = 0.20;
            SeriousIOS_QueueSDLKey('w', vertical > deadZone);
            SeriousIOS_QueueSDLKey('s', vertical < -deadZone);
            SeriousIOS_QueueSDLKey('d', horizontal > deadZone);
            SeriousIOS_QueueSDLKey('a', horizontal < -deadZone);
        } else if (touch == _lookTouch) {
            const CGFloat scale = self.contentScaleFactor > 0.0 ? self.contentScaleFactor : 1.0;
            const CGFloat deltaX = point.x - _lookPrevious.x;
            const CGFloat deltaY = point.y - _lookPrevious.y;
            _lookPrevious = point;
            SeriousIOS_AddSDLRelativeMouseDelta(
                (int)llround(deltaX * scale * 0.72),
                (int)llround(deltaY * scale * 0.72));
        }
    }
}

- (void)endGameplayTouches:(NSSet<UITouch*>*)touches {
    for (UITouch* touch in touches) {
        if (touch == _movementTouch) {
            [self releaseMovementKeys];
            _movementTouch = nil;
        }
        if (touch == _lookTouch) {
            _lookTouch = nil;
        }
    }
}

- (void)touchesBegan:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    if (SeriousIOS_ApplicationGameplayControlsActive()) {
        [self beginGameplayTouches:touches];
        return;
    }
    [self routeMenuTouch:touches.anyObject activate:NO];
}

- (void)touchesMoved:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    if (SeriousIOS_ApplicationGameplayControlsActive()) {
        [self moveGameplayTouches:touches];
        return;
    }
    [self routeMenuTouch:touches.anyObject activate:NO];
}

- (void)touchesEnded:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    if (SeriousIOS_ApplicationGameplayControlsActive()
        || _movementTouch != nil
        || _lookTouch != nil) {
        [self endGameplayTouches:touches];
        return;
    }
    [self routeMenuTouch:touches.anyObject activate:YES];
}

- (void)touchesCancelled:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    [self endGameplayTouches:touches];
}
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def transform(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "SeriousIOS_ApplicationMenuPointerActivate" in text:
        raise RuntimeError("touch routing is already present")

    text = replace_once(
        text,
        '''    CADisplayLink* _displayLink;
    BOOL _startupScheduled;
    BOOL _renderedFirstApplicationFrame;''',
        '''    CADisplayLink* _displayLink;
''' + GAMEPLAY_IVARS + '''    BOOL _startupScheduled;
    BOOL _renderedFirstApplicationFrame;''',
        "gameplay touch ivars",
    )

    text = replace_once(
        text,
        "    [NSLayoutConstraint activateConstraints:@[",
        GAMEPLAY_BUTTONS + "\n    [NSLayoutConstraint activateConstraints:@[",
        "gameplay button construction",
    )

    text = replace_once(
        text,
        '''- (void)layoutSubviews {
    [super layoutSubviews];
    [self createDrawable];
}''',
        '''- (void)layoutSubviews {
    [super layoutSubviews];
    [self createDrawable];
    [self layoutGameplayControls];
}''',
        "gameplay control layout",
    )

    text = replace_once(
        text,
        "    const bool rendered = SeriousIOS_ApplicationFrame();",
        '''    SeriousIOS_ApplicationProcessInputEvents();
    const bool rendered = SeriousIOS_ApplicationFrame();
    [self updateGameplayControlVisibility];''',
        "gameplay input frame processing",
    )

    marker = "- (void)destroyDrawable {"
    if text.count(marker) != 1:
        raise RuntimeError("expected one destroyDrawable insertion point")
    text = text.replace(marker, TOUCH_METHODS + "\n" + marker, 1)

    required = (
        "touch_control action=skip",
        "SeriousIOS_AddSDLRelativeMouseDelta",
        "SeriousIOS_ApplicationProcessInputEvents",
        "SeriousIOS_ApplicationGameplayControlsActive",
        'setTitle:@"FIRE"',
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"generated touch host missing token: {token}")

    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("host_source", type=Path)
    args = parser.parse_args()
    source = args.host_source.resolve()
    if not source.is_file():
        raise SystemExit(f"host source does not exist: {source}")
    transform(source)
    print(f"Injected native menu and gameplay touch controls into {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
