#!/usr/bin/env python3
"""Install the compiled eDuke-style touch overlay into the generated UIKit host."""

from __future__ import annotations

import argparse
from pathlib import Path


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
        '#import <UIKit/UIKit.h>\n',
        '#import <UIKit/UIKit.h>\n#import "SeriousIOSTouchOverlayView.h"\n',
        "overlay import",
    )
    text = replace_once(
        text,
        '    CADisplayLink* _displayLink;\n',
        '    CADisplayLink* _displayLink;\n    SeriousIOSTouchOverlayView* _touchOverlay;\n',
        "overlay ivar",
    )
    text = replace_once(
        text,
        '    [self configureAdvancedTouchControls];\n',
        '''    [self configureAdvancedTouchControls];
    [_motionManager stopDeviceMotionUpdates];
    _gyroEnabled = NO;
    for (UIButton* legacyButton in @[_fireButton, _jumpButton, _useButton, _skipButton, _pauseButton]) {
        legacyButton.hidden = YES;
        legacyButton.userInteractionEnabled = NO;
    }
    _controlsEditorOverlay.hidden = YES;
    _controlsEditorOverlay.userInteractionEnabled = NO;

    _touchOverlay = [[SeriousIOSTouchOverlayView alloc] initWithFrame:self.bounds];
    // Preserve the exact relative-look resolution of the previously validated
    // render-view path. A child UIView otherwise may operate at a lower content
    // scale, causing touch and gyro deltas to be rounded into coarse steps.
    _touchOverlay.contentScaleFactor = self.contentScaleFactor;
    _touchOverlay.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    [self addSubview:_touchOverlay];
''',
        "overlay initialization",
    )
    text = replace_once(
        text,
        '- (void)dealloc {\n',
        '''- (void)dealloc {
    [_touchOverlay cancelAllInputWithReason:@"host-dealloc"];
''',
        "overlay cleanup",
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
    _touchOverlay.frame = self.bounds;
    _touchOverlay.contentScaleFactor = self.contentScaleFactor;
    [self bringSubviewToFront:_touchOverlay];
}''',
        "overlay layout",
    )

    visibility = r'''- (void)updateGameplayControlVisibility {
    for (UIButton* legacyButton in @[_fireButton, _jumpButton, _useButton, _skipButton, _pauseButton]) {
        legacyButton.hidden = YES;
        legacyButton.userInteractionEnabled = NO;
    }
    _controlsEditorOverlay.hidden = YES;
    _controlsEditorOverlay.userInteractionEnabled = NO;

    const BOOL gameplayActive = SeriousIOS_ApplicationGameplayControlsActive();
    const BOOL computerActive = SeriousIOS_ApplicationComputerActive();
    [_touchOverlay updateGameplayActive:gameplayActive computerActive:computerActive];
    [self bringSubviewToFront:_touchOverlay];
}'''
    text = replace_method(
        text,
        '- (void)updateGameplayControlVisibility {',
        '- (void)gameplayFireDown {',
        visibility,
    )

    required = (
        'SeriousIOSTouchOverlayView* _touchOverlay;',
        'initWithFrame:self.bounds',
        '_touchOverlay.contentScaleFactor = self.contentScaleFactor;',
        'updateGameplayActive:gameplayActive computerActive:computerActive',
        'legacyButton.userInteractionEnabled = NO;',
        '[_motionManager stopDeviceMotionUpdates];',
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"eDuke overlay integration missing token: {token}")
    if text.count('_touchOverlay.contentScaleFactor = self.contentScaleFactor;') != 2:
        raise RuntimeError("overlay content scale must be copied at initialization and layout")
    return text


def self_test() -> None:
    fixture = '''#import <UIKit/UIKit.h>
    CADisplayLink* _displayLink;
    [self configureAdvancedTouchControls];
- (void)dealloc {
- (void)layoutSubviews {
    [super layoutSubviews];
    [self createDrawable];
    [self layoutGameplayControls];
    [self layoutControlsEditor];
}
- (void)updateGameplayControlVisibility {
    old;
}

- (void)gameplayFireDown {
}
'''
    transformed = transform_text(fixture)
    assert 'SeriousIOSTouchOverlayView* _touchOverlay;' in transformed
    assert 'legacyButton.userInteractionEnabled = NO;' in transformed
    assert 'updateGameplayActive:gameplayActive computerActive:computerActive' in transformed
    assert transformed.count('_touchOverlay.contentScaleFactor = self.contentScaleFactor;') == 2
    print('SeriousiOS eDuke overlay integration self-test passed')


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
    print(f'Integrated compiled eDuke-style overlay into {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
