#!/usr/bin/env python3
"""Add optional dedicated Fire and eDuke-style right-zone firing without altering aim/gyro paths."""

from __future__ import annotations

import argparse
from pathlib import Path


FIRE_IVARS = r'''    BOOL _fireButtonEnabled;
    UISwitch* _fireButtonSwitch;
    UIPanGestureRecognizer* _fireAimGesture;
    CGPoint _lookFireOrigin;
    CGFloat _lookFireTravel;
    BOOL _lookFireMoved;
    BOOL _lookHoldFirePressed;
    BOOL _dedicatedFirePressed;
    BOOL _firePulsePressed;
    BOOL _effectiveFirePressed;
    NSUInteger _lookFireGeneration;
    NSUInteger _firePulseGeneration;
'''

FIRE_METHODS = r'''- (void)updateEffectiveFireState {
    const BOOL pressed = _dedicatedFirePressed || _lookHoldFirePressed || _firePulsePressed;
    if (_effectiveFirePressed == pressed) {
        return;
    }
    _effectiveFirePressed = pressed;
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_FIRE, pressed);
    SeriousIOS_DiagnosticsLog(
        "input",
        "touch_fire effective=%d dedicated=%d look_hold=%d pulse=%d",
        pressed ? 1 : 0,
        _dedicatedFirePressed ? 1 : 0,
        _lookHoldFirePressed ? 1 : 0,
        _firePulsePressed ? 1 : 0);
}

- (void)cancelAllTouchFireSources {
    _lookFireGeneration += 1;
    _firePulseGeneration += 1;
    _lookFireMoved = NO;
    _lookFireTravel = 0.0;
    _lookHoldFirePressed = NO;
    _dedicatedFirePressed = NO;
    _firePulsePressed = NO;
    [self updateEffectiveFireState];
}

- (void)pulseRightZoneFire {
    const NSUInteger generation = ++_firePulseGeneration;
    _firePulsePressed = YES;
    [self updateEffectiveFireState];
    SeriousIOS_DiagnosticsLog("input", "right_zone_fire mode=tap pulse_ms=80");
    dispatch_after(
        dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.08 * NSEC_PER_SEC)),
        dispatch_get_main_queue(), ^{
            if (self->_firePulseGeneration != generation) {
                return;
            }
            self->_firePulsePressed = NO;
            [self updateEffectiveFireState];
        });
}

- (void)fireButtonEnabledChanged:(UISwitch*)sender {
    _fireButtonEnabled = sender.isOn;
    [NSUserDefaults.standardUserDefaults setBool:_fireButtonEnabled
                                           forKey:@"SeriousIOS.FireButtonEnabled"];
    if (!_fireButtonEnabled) {
        _dedicatedFirePressed = NO;
        [self updateEffectiveFireState];
    }
    [self updateGameplayControlVisibility];
    SeriousIOS_DiagnosticsLog(
        "input", "fire_button_setting enabled=%d", _fireButtonEnabled ? 1 : 0);
}

- (void)fireButtonAimPan:(UIPanGestureRecognizer*)gesture {
    const CGPoint translation = [gesture translationInView:self];
    [gesture setTranslation:CGPointZero inView:self];
    if (_controlsEditorVisible
        || !_fireButtonEnabled
        || !SeriousIOS_ApplicationGameplayControlsActive()
        || SeriousIOS_ApplicationComputerActive()) {
        return;
    }
    if (translation.x == 0.0 && translation.y == 0.0) {
        return;
    }

    // Deliberately identical to the restored render-view touch-look path.
    const CGFloat scale = self.contentScaleFactor > 0.0 ? self.contentScaleFactor : 1.0;
    const CGFloat sensitivity = MIN(2.50, MAX(0.20, _touchAimSensitivity));
    SeriousIOS_AddSDLRelativeMouseDelta(
        (int)llround(translation.x * scale * sensitivity),
        (int)llround(translation.y * scale * sensitivity));
}
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def replace_method(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"method start not found: {start_marker}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"method end not found: {end_marker}")
    return text[:start] + replacement + "\n\n" + text[end:]


def transform_text(text: str) -> str:
    text = replace_once(
        text,
        '''    CGFloat _touchAimSensitivity;\n    BOOL _controlsEditorVisible;''',
        '''    CGFloat _touchAimSensitivity;\n''' + FIRE_IVARS + '''    BOOL _controlsEditorVisible;''',
        "fire gesture ivars",
    )

    text = replace_once(
        text,
        '''    _touchAimSensitivity = [defaults objectForKey:@"SeriousIOS.TouchAimSensitivity"] != nil
        ? [defaults doubleForKey:@"SeriousIOS.TouchAimSensitivity"]
        : 0.72;

    [self styleControlButton:_fireButton''',
        '''    _touchAimSensitivity = [defaults objectForKey:@"SeriousIOS.TouchAimSensitivity"] != nil
        ? [defaults doubleForKey:@"SeriousIOS.TouchAimSensitivity"]
        : 0.72;
    _fireButtonEnabled = [defaults objectForKey:@"SeriousIOS.FireButtonEnabled"] != nil
        ? [defaults boolForKey:@"SeriousIOS.FireButtonEnabled"]
        : YES;

    [self styleControlButton:_fireButton''',
        "fire button preference",
    )

    text = replace_once(
        text,
        '''    [_pauseButton addGestureRecognizer:pauseLongPress];

    _controlsEditorOverlay = [[UIView alloc] initWithFrame:self.bounds];''',
        '''    [_pauseButton addGestureRecognizer:pauseLongPress];

    _fireAimGesture = [[UIPanGestureRecognizer alloc]
        initWithTarget:self action:@selector(fireButtonAimPan:)];
    _fireAimGesture.maximumNumberOfTouches = 1;
    _fireAimGesture.cancelsTouchesInView = NO;
    [_fireButton addGestureRecognizer:_fireAimGesture];

    _controlsEditorOverlay = [[UIView alloc] initWithFrame:self.bounds];''',
        "fire aim gesture",
    )

    text = replace_once(
        text,
        '''    UILabel* gyroLabel = [self controlsEditorLabelWithText:@"Gyro aiming"
                                                        font:[UIFont systemFontOfSize:14.0 weight:UIFontWeightSemibold]];''',
        '''    UILabel* fireButtonLabel = [self controlsEditorLabelWithText:@"Dedicated Fire button"
                                                               font:[UIFont systemFontOfSize:14.0 weight:UIFontWeightSemibold]];
    fireButtonLabel.accessibilityIdentifier = @"fire-button-enabled-label";
    _fireButtonSwitch = [[UISwitch alloc] initWithFrame:CGRectZero];
    _fireButtonSwitch.on = _fireButtonEnabled;
    [_fireButtonSwitch addTarget:self action:@selector(fireButtonEnabledChanged:)
              forControlEvents:UIControlEventValueChanged];
    [_controlsEditorPanel addSubview:_fireButtonSwitch];

    UILabel* gyroLabel = [self controlsEditorLabelWithText:@"Gyro aiming"
                                                        font:[UIFont systemFontOfSize:14.0 weight:UIFontWeightSemibold]];''',
        "fire button editor toggle",
    )

    text = replace_once(
        text,
        '''    const CGFloat panelHeight = MIN(300.0, MAX(270.0, height - self.safeAreaInsets.top - self.safeAreaInsets.bottom - 20.0));''',
        '''    const CGFloat panelHeight = MIN(320.0, MAX(300.0, height - self.safeAreaInsets.top - self.safeAreaInsets.bottom - 20.0));''',
        "editor panel height",
    )

    text = replace_once(
        text,
        '''    UIView* gyroLabelView = [self descendantViewWithAccessibilityIdentifier:@"gyro-enabled-label"
                                                                       inView:_controlsEditorPanel];''',
        '''    UIView* fireButtonLabelView = [self descendantViewWithAccessibilityIdentifier:@"fire-button-enabled-label"
                                                                             inView:_controlsEditorPanel];
    UIView* gyroLabelView = [self descendantViewWithAccessibilityIdentifier:@"gyro-enabled-label"
                                                                       inView:_controlsEditorPanel];''',
        "fire editor label lookup",
    )

    old_frames = '''    titleView.frame = CGRectMake(left, 14.0, contentWidth, 26.0);
    instructionsView.frame = CGRectMake(left, 42.0, contentWidth, 34.0);
    gyroLabelView.frame = CGRectMake(left, 80.0, contentWidth - 70.0, 30.0);
    _gyroSwitch.frame = CGRectMake(panelWidth - right - 51.0, 78.0, 51.0, 31.0);
    gyroSensitivityLabelView.frame = CGRectMake(left, 118.0, contentWidth - 62.0, 20.0);
    _gyroSensitivityValueLabel.frame = CGRectMake(panelWidth - right - 62.0, 118.0, 62.0, 20.0);
    _gyroSensitivitySlider.frame = CGRectMake(left, 140.0, contentWidth, 30.0);
    touchSensitivityLabelView.frame = CGRectMake(left, 174.0, contentWidth - 62.0, 20.0);
    _touchSensitivityValueLabel.frame = CGRectMake(panelWidth - right - 62.0, 174.0, 62.0, 20.0);
    _touchSensitivitySlider.frame = CGRectMake(left, 196.0, contentWidth, 30.0);
    const CGFloat buttonY = panelHeight - 50.0;
    reset.frame = CGRectMake(left, buttonY, 128.0, 36.0);
    done.frame = CGRectMake(panelWidth - right - 90.0, buttonY, 90.0, 36.0);'''
    new_frames = '''    titleView.frame = CGRectMake(left, 10.0, contentWidth, 26.0);
    instructionsView.frame = CGRectMake(left, 36.0, contentWidth, 30.0);
    fireButtonLabelView.frame = CGRectMake(left, 68.0, contentWidth - 70.0, 30.0);
    _fireButtonSwitch.frame = CGRectMake(panelWidth - right - 51.0, 66.0, 51.0, 31.0);
    gyroLabelView.frame = CGRectMake(left, 102.0, contentWidth - 70.0, 30.0);
    _gyroSwitch.frame = CGRectMake(panelWidth - right - 51.0, 100.0, 51.0, 31.0);
    gyroSensitivityLabelView.frame = CGRectMake(left, 138.0, contentWidth - 62.0, 20.0);
    _gyroSensitivityValueLabel.frame = CGRectMake(panelWidth - right - 62.0, 138.0, 62.0, 20.0);
    _gyroSensitivitySlider.frame = CGRectMake(left, 156.0, contentWidth, 30.0);
    touchSensitivityLabelView.frame = CGRectMake(left, 190.0, contentWidth - 62.0, 20.0);
    _touchSensitivityValueLabel.frame = CGRectMake(panelWidth - right - 62.0, 190.0, 62.0, 20.0);
    _touchSensitivitySlider.frame = CGRectMake(left, 208.0, contentWidth, 30.0);
    const CGFloat buttonY = panelHeight - 46.0;
    reset.frame = CGRectMake(left, buttonY, 128.0, 36.0);
    done.frame = CGRectMake(panelWidth - right - 90.0, buttonY, 90.0, 36.0);'''
    text = replace_once(text, old_frames, new_frames, "fire editor layout")

    text = text.replace(
        '- (void)resetTouchControlLayout {',
        FIRE_METHODS + '\n- (void)resetTouchControlLayout {',
        1,
    )

    text = replace_once(
        text,
        '''- (void)releaseGameplayTouches {
    [self releaseMovementKeys];
    _movementTouch = nil;
    _lookTouch = nil;
}''',
        '''- (void)releaseGameplayTouches {
    [self releaseMovementKeys];
    [self cancelAllTouchFireSources];
    _movementTouch = nil;
    _lookTouch = nil;
}''',
        "fire cleanup",
    )

    fire_methods = r'''- (void)gameplayFireDown {
    if (_controlsEditorVisible || !_fireButtonEnabled) {
        return;
    }
    _dedicatedFirePressed = YES;
    [self updateEffectiveFireState];
    SeriousIOS_DiagnosticsLog("input", "touch_control action=fire state=down source=dedicated_button");
}

- (void)gameplayFireUp {
    _dedicatedFirePressed = NO;
    [self updateEffectiveFireState];
    SeriousIOS_DiagnosticsLog("input", "touch_control action=fire state=up source=dedicated_button");
}'''
    text = replace_method(
        text,
        '- (void)gameplayFireDown {',
        '- (void)gameplayJumpDown {',
        fire_methods,
    )

    text = replace_once(
        text,
        '''    if (_controlsEditorVisible) {
        for (UIButton* button in [self gameplayControlButtons]) {
            button.hidden = NO;
        }
        [self updatePauseButtonForComputerActive:NO];
        return;
    }

    _fireButton.hidden = !active || computerActive;''',
        '''    if (_controlsEditorVisible) {
        for (UIButton* button in [self gameplayControlButtons]) {
            button.hidden = NO;
        }
        _fireAimGesture.enabled = NO;
        [self updatePauseButtonForComputerActive:NO];
        return;
    }

    _fireButton.hidden = !_fireButtonEnabled || !active || computerActive;
    _fireAimGesture.enabled = _fireButtonEnabled && active && !computerActive;''',
        "fire visibility",
    )

    text = replace_once(
        text,
        '''    if ((!active || computerActive)
        && (_movementTouch != nil || _lookTouch != nil)) {''',
        '''    if ((!active || computerActive)
        && (_movementTouch != nil || _lookTouch != nil || _effectiveFirePressed)) {''',
        "inactive fire cleanup condition",
    )

    text = replace_once(
        text,
        '''        } else if (_lookTouch == nil) {
            _lookTouch = touch;
            _lookPrevious = point;
        }''',
        '''        } else if (_lookTouch == nil) {
            _lookTouch = touch;
            _lookPrevious = point;
            _lookFireOrigin = point;
            _lookFireTravel = 0.0;
            _lookFireMoved = NO;
            _lookHoldFirePressed = NO;
            const NSUInteger generation = ++_lookFireGeneration;
            if (!_fireButtonEnabled) {
                __weak SeriousIOSRenderView* weakSelf = self;
                dispatch_after(
                    dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.125 * NSEC_PER_SEC)),
                    dispatch_get_main_queue(), ^{
                        SeriousIOSRenderView* strongSelf = weakSelf;
                        if (strongSelf == nil
                            || strongSelf->_lookFireGeneration != generation
                            || strongSelf->_lookTouch != touch
                            || strongSelf->_lookFireMoved
                            || strongSelf->_fireButtonEnabled
                            || strongSelf->_controlsEditorVisible
                            || !SeriousIOS_ApplicationGameplayControlsActive()
                            || SeriousIOS_ApplicationComputerActive()) {
                            return;
                        }
                        strongSelf->_lookHoldFirePressed = YES;
                        [strongSelf updateEffectiveFireState];
                        SeriousIOS_DiagnosticsLog(
                            "input", "right_zone_fire mode=hold delay_ms=125 state=down");
                    });
            }
        }''',
        "right-zone fire begin",
    )

    text = replace_once(
        text,
        '''            const CGFloat deltaX = point.x - _lookPrevious.x;
            const CGFloat deltaY = point.y - _lookPrevious.y;
            _lookPrevious = point;''',
        '''            const CGFloat deltaX = point.x - _lookPrevious.x;
            const CGFloat deltaY = point.y - _lookPrevious.y;
            if (!_fireButtonEnabled && !_lookHoldFirePressed) {
                _lookFireTravel += hypot(deltaX, deltaY);
                const CGFloat displacement = hypot(
                    point.x - _lookFireOrigin.x,
                    point.y - _lookFireOrigin.y);
                if (displacement >= 4.0 || _lookFireTravel >= 6.0) {
                    _lookFireMoved = YES;
                }
            }
            _lookPrevious = point;''',
        "right-zone fire movement thresholds",
    )

    text = replace_once(
        text,
        '- (void)endGameplayTouches:(NSSet<UITouch*>*)touches {',
        '- (void)endGameplayTouches:(NSSet<UITouch*>*)touches cancelled:(BOOL)cancelled {',
        "cancel-aware touch finish",
    )

    text = replace_once(
        text,
        '''        if (touch == _lookTouch) {
            _lookTouch = nil;
        }''',
        '''        if (touch == _lookTouch) {
            const CGPoint point = [touch locationInView:self];
            const CGFloat displacement = hypot(
                point.x - _lookFireOrigin.x,
                point.y - _lookFireOrigin.y);
            const BOOL wasMoved = _lookFireMoved;
            const BOOL wasHoldingFire = _lookHoldFirePressed;
            _lookTouch = nil;
            _lookFireGeneration += 1;
            _lookFireMoved = NO;
            _lookFireTravel = 0.0;
            _lookHoldFirePressed = NO;
            [self updateEffectiveFireState];
            if (!_fireButtonEnabled
                && !cancelled
                && !wasHoldingFire
                && !wasMoved
                && displacement < 4.0) {
                [self pulseRightZoneFire];
            }
        }''',
        "right-zone fire finish",
    )

    text = replace_once(
        text,
        '''        [self endGameplayTouches:touches];
        return;''',
        '''        [self endGameplayTouches:touches cancelled:NO];
        return;''',
        "normal touch finish",
    )
    text = replace_once(
        text,
        '''    [self endGameplayTouches:touches];
}''',
        '''    [self endGameplayTouches:touches cancelled:YES];
}''',
        "cancelled touch finish",
    )

    required = (
        'SeriousIOS.FireButtonEnabled',
        'right_zone_fire mode=hold',
        'right_zone_fire mode=tap',
        'fireButtonAimPan:',
        '_fireButton.hidden = !_fireButtonEnabled',
        'displacement >= 4.0 || _lookFireTravel >= 6.0',
        'endGameplayTouches:touches cancelled:NO',
        'endGameplayTouches:touches cancelled:YES',
        'translation.x * scale * sensitivity',
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"fire gesture transform missing token: {token}")

    # The restored look and gyro transport must remain untouched.
    if text.count('SeriousIOS_AddSDLRelativeMouseDelta(') < 3:
        raise RuntimeError('expected restored touch, gyro, and fire-button aim paths')
    return text


def self_test() -> None:
    fixture = '''    CGFloat _touchAimSensitivity;
    BOOL _controlsEditorVisible;
    _touchAimSensitivity = [defaults objectForKey:@"SeriousIOS.TouchAimSensitivity"] != nil
        ? [defaults doubleForKey:@"SeriousIOS.TouchAimSensitivity"]
        : 0.72;

    [self styleControlButton:_fireButton
    [_pauseButton addGestureRecognizer:pauseLongPress];

    _controlsEditorOverlay = [[UIView alloc] initWithFrame:self.bounds];
    UILabel* gyroLabel = [self controlsEditorLabelWithText:@"Gyro aiming"
                                                        font:[UIFont systemFontOfSize:14.0 weight:UIFontWeightSemibold]];
    const CGFloat panelHeight = MIN(300.0, MAX(270.0, height - self.safeAreaInsets.top - self.safeAreaInsets.bottom - 20.0));
    UIView* gyroLabelView = [self descendantViewWithAccessibilityIdentifier:@"gyro-enabled-label"
                                                                       inView:_controlsEditorPanel];
    titleView.frame = CGRectMake(left, 14.0, contentWidth, 26.0);
    instructionsView.frame = CGRectMake(left, 42.0, contentWidth, 34.0);
    gyroLabelView.frame = CGRectMake(left, 80.0, contentWidth - 70.0, 30.0);
    _gyroSwitch.frame = CGRectMake(panelWidth - right - 51.0, 78.0, 51.0, 31.0);
    gyroSensitivityLabelView.frame = CGRectMake(left, 118.0, contentWidth - 62.0, 20.0);
    _gyroSensitivityValueLabel.frame = CGRectMake(panelWidth - right - 62.0, 118.0, 62.0, 20.0);
    _gyroSensitivitySlider.frame = CGRectMake(left, 140.0, contentWidth, 30.0);
    touchSensitivityLabelView.frame = CGRectMake(left, 174.0, contentWidth - 62.0, 20.0);
    _touchSensitivityValueLabel.frame = CGRectMake(panelWidth - right - 62.0, 174.0, 62.0, 20.0);
    _touchSensitivitySlider.frame = CGRectMake(left, 196.0, contentWidth, 30.0);
    const CGFloat buttonY = panelHeight - 50.0;
    reset.frame = CGRectMake(left, buttonY, 128.0, 36.0);
    done.frame = CGRectMake(panelWidth - right - 90.0, buttonY, 90.0, 36.0);
- (void)resetTouchControlLayout {
}
- (void)releaseGameplayTouches {
    [self releaseMovementKeys];
    _movementTouch = nil;
    _lookTouch = nil;
}
- (void)gameplayFireDown {
    if (_controlsEditorVisible) {
        return;
    }
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_FIRE, true);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=fire state=down source=virtual_controller");
}

- (void)gameplayFireUp {
    if (_controlsEditorVisible) {
        return;
    }
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_FIRE, false);
    SeriousIOS_DiagnosticsLog("input", "touch_control action=fire state=up source=virtual_controller");
}
- (void)gameplayJumpDown {
}
    if (_controlsEditorVisible) {
        for (UIButton* button in [self gameplayControlButtons]) {
            button.hidden = NO;
        }
        [self updatePauseButtonForComputerActive:NO];
        return;
    }

    _fireButton.hidden = !active || computerActive;
    if ((!active || computerActive)
        && (_movementTouch != nil || _lookTouch != nil)) {
        [self releaseGameplayTouches];
    }
        } else if (_lookTouch == nil) {
            _lookTouch = touch;
            _lookPrevious = point;
        }
            const CGFloat deltaX = point.x - _lookPrevious.x;
            const CGFloat deltaY = point.y - _lookPrevious.y;
            _lookPrevious = point;
            const CGFloat scale = self.contentScaleFactor > 0.0 ? self.contentScaleFactor : 1.0;
            const CGFloat sensitivity = MIN(2.50, MAX(0.20, _touchAimSensitivity));
            SeriousIOS_AddSDLRelativeMouseDelta(
                (int)llround(deltaX * scale * sensitivity),
                (int)llround(deltaY * scale * sensitivity));
- (void)endGameplayTouches:(NSSet<UITouch*>*)touches {
        if (touch == _lookTouch) {
            _lookTouch = nil;
        }
}
        [self endGameplayTouches:touches];
        return;
    [self endGameplayTouches:touches];
}
SeriousIOS_AddSDLRelativeMouseDelta(deltaX, deltaY);
'''
    transformed = transform_text(fixture)
    assert 'SeriousIOS.FireButtonEnabled' in transformed
    assert 'right_zone_fire mode=hold' in transformed
    assert 'fireButtonAimPan:' in transformed
    print('SeriousiOS optional-fire gesture transform self-test passed')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('host_source', type=Path, nargs='?')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()

    if args.self_test:
        self_test()
        if args.host_source is None:
            return 0
    if args.host_source is None:
        parser.error('host_source is required unless only --self-test is used')

    path = args.host_source.resolve()
    if not path.is_file():
        raise SystemExit(f'host source does not exist: {path}')
    path.write_text(transform_text(path.read_text(encoding='utf-8')), encoding='utf-8')
    print(f'Injected optional dedicated Fire and right-zone firing into {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
