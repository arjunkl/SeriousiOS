#!/usr/bin/env python3
"""Add a large native Return-to-Game button only on Serious Sam's pause menu.

This also retires the redundant Skip control from the visible/editable gameplay
layout without changing its underlying engine bindings.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


RETURN_METHODS = r'''- (void)layoutReturnToGameButton {
    const UIEdgeInsets safe = self.safeAreaInsets;
    const CGFloat width = 170.0;
    const CGFloat height = 50.0;
    const CGFloat x = MAX(
        safe.left + 12.0,
        CGRectGetWidth(self.bounds) - safe.right - width - 14.0);
    const CGFloat y = safe.top + 12.0;
    _returnToGameButton.frame = CGRectMake(x, y, width, height);
}

- (void)returnToGameFromPauseMenu {
    if (!SeriousIOS_ApplicationPauseMenuActive()) {
        return;
    }

    SeriousIOS_QueueSDLKey(27, true);
    SeriousIOS_DiagnosticsLog("input", "pause_return action=resume pulse=down");
    dispatch_after(
        dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.08 * NSEC_PER_SEC)),
        dispatch_get_main_queue(), ^{
            SeriousIOS_QueueSDLKey(27, false);
            SeriousIOS_DiagnosticsLog("input", "pause_return action=resume pulse=up");
        });
}
'''


def transform_text(text: str) -> str:
    text = replace_once(
        text,
        '    UIButton* _pauseButton;\n',
        '    UIButton* _pauseButton;\n    UIButton* _returnToGameButton;\n',
        "return button ivar",
    )

    setup = r'''    [self configureAdvancedTouchControls];

    // FIRE already performs the same sequence-skip action in this port, so the
    // separate Skip control is intentionally retired from the mobile layout.
    _skipButton.hidden = YES;
    _skipButton.userInteractionEnabled = NO;

    _returnToGameButton = [UIButton buttonWithType:UIButtonTypeSystem];
    UIButtonConfiguration* returnConfiguration =
        [UIButtonConfiguration tintedButtonConfiguration];
    returnConfiguration.title = @"Return to Game";
    returnConfiguration.baseForegroundColor = UIColor.whiteColor;
    returnConfiguration.baseBackgroundColor =
        [UIColor colorWithWhite:0.04 alpha:0.72];
    returnConfiguration.cornerStyle = UIButtonConfigurationCornerStyleCapsule;
    returnConfiguration.imagePadding = 8.0;
    UIImageSymbolConfiguration* returnSymbolConfiguration =
        [UIImageSymbolConfiguration configurationWithPointSize:18.0
                                                        weight:UIImageSymbolWeightSemibold];
    returnConfiguration.image = [UIImage systemImageNamed:@"arrow.uturn.backward"
                                         withConfiguration:returnSymbolConfiguration];
    _returnToGameButton.configuration = returnConfiguration;
    _returnToGameButton.hidden = YES;
    _returnToGameButton.alpha = 0.92;
    _returnToGameButton.accessibilityLabel = @"Return to Game";
    _returnToGameButton.accessibilityIdentifier = @"pause-return-to-game";
    [_returnToGameButton addTarget:self
                            action:@selector(returnToGameFromPauseMenu)
                  forControlEvents:UIControlEventTouchUpInside];
    [self addSubview:_returnToGameButton];
'''
    text = replace_once(
        text,
        '    [self configureAdvancedTouchControls];\n',
        setup,
        "return button setup",
    )

    text = replace_once(
        text,
        '''    [self createDrawable];
    [self layoutGameplayControls];
    [self layoutControlsEditor];
}''',
        '''    [self createDrawable];
    [self layoutGameplayControls];
    [self layoutControlsEditor];
    [self layoutReturnToGameButton];
}''',
        "return button layout",
    )

    text = replace_once(
        text,
        '    return @[_fireButton, _jumpButton, _useButton, _skipButton, _pauseButton];',
        '    return @[_fireButton, _jumpButton, _useButton, _pauseButton];',
        "remove skip from editable controls",
    )

    text = replace_once(
        text,
        '- (void)releaseMovementKeys {',
        RETURN_METHODS + '\n- (void)releaseMovementKeys {',
        "return button methods",
    )

    text = replace_once(
        text,
        '''    const BOOL active = SeriousIOS_ApplicationGameplayControlsActive();
    const BOOL computerActive = active && SeriousIOS_ApplicationComputerActive();

    if (_controlsEditorVisible) {''',
        '''    const BOOL active = SeriousIOS_ApplicationGameplayControlsActive();
    const BOOL computerActive = active && SeriousIOS_ApplicationComputerActive();
    const BOOL pauseMenuActive = SeriousIOS_ApplicationPauseMenuActive();

    _returnToGameButton.hidden = !pauseMenuActive || _controlsEditorVisible;
    _returnToGameButton.userInteractionEnabled = pauseMenuActive && !_controlsEditorVisible;
    if (!_returnToGameButton.hidden) {
        [self bringSubviewToFront:_returnToGameButton];
    }

    if (_controlsEditorVisible) {''',
        "pause menu visibility",
    )

    text = replace_once(
        text,
        '    _skipButton.hidden = !active || computerActive;\n',
        '''    _skipButton.hidden = YES;
    _skipButton.userInteractionEnabled = NO;
''',
        "retire skip visibility",
    )

    required = (
        'UIButton* _returnToGameButton;',
        'SeriousIOS_ApplicationPauseMenuActive()',
        'pause-return-to-game',
        'Return to Game',
        'pause_return action=resume',
        '[self layoutReturnToGameButton];',
        'return @[_fireButton, _jumpButton, _useButton, _pauseButton];',
        '_skipButton.userInteractionEnabled = NO;',
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"pause-return transform missing token: {token}")

    forbidden = (
        'return @[_fireButton, _jumpButton, _useButton, _skipButton, _pauseButton];',
        '_skipButton.hidden = !active || computerActive;',
    )
    for token in forbidden:
        if token in text:
            raise RuntimeError(f"obsolete pause/skip behavior remains: {token}")

    return text


def self_test() -> None:
    fixture = '''    UIButton* _pauseButton;
    [self configureAdvancedTouchControls];
- (void)layoutSubviews {
    [super layoutSubviews];
    [self createDrawable];
    [self layoutGameplayControls];
    [self layoutControlsEditor];
}
- (NSArray<UIButton*>*)gameplayControlButtons {
    return @[_fireButton, _jumpButton, _useButton, _skipButton, _pauseButton];
}
- (void)releaseMovementKeys {
}
- (void)updateGameplayControlVisibility {
    const BOOL active = SeriousIOS_ApplicationGameplayControlsActive();
    const BOOL computerActive = active && SeriousIOS_ApplicationComputerActive();

    if (_controlsEditorVisible) {
    }
    _skipButton.hidden = !active || computerActive;
}
'''
    transformed = transform_text(fixture)
    assert 'SeriousIOS_ApplicationPauseMenuActive()' in transformed
    assert 'pause-return-to-game' in transformed
    assert 'Return to Game' in transformed
    assert '_skipButton.userInteractionEnabled = NO;' in transformed
    assert '_skipButton.hidden = !active || computerActive;' not in transformed
    print('SeriousiOS pause-return and skip-retirement self-test passed')


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
    print(f'Added pause-menu Return control and retired Skip in {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
