#!/usr/bin/env python3
"""Add icon controls, gyro aiming, sensitivity settings, and layout editing."""

from __future__ import annotations

import argparse
from pathlib import Path


ADVANCED_IVARS = r'''    CMMotionManager* _motionManager;
    NSTimeInterval _lastMotionTimestamp;
    CGFloat _gyroRemainderX;
    CGFloat _gyroRemainderY;
    BOOL _gyroEnabled;
    CGFloat _gyroSensitivity;
    CGFloat _touchAimSensitivity;
    BOOL _controlsEditorVisible;
    BOOL _pauseLongPressRecognized;
    UIView* _controlsEditorOverlay;
    UIView* _controlsEditorPanel;
    UISwitch* _gyroSwitch;
    UISlider* _gyroSensitivitySlider;
    UISlider* _touchSensitivitySlider;
    UILabel* _gyroSensitivityValueLabel;
    UILabel* _touchSensitivityValueLabel;
    NSMutableArray<UIGestureRecognizer*>* _controlEditingGestures;
'''

ADVANCED_METHODS = r'''- (NSArray<UIButton*>*)gameplayControlButtons {
    return @[_fireButton, _jumpButton, _useButton, _skipButton, _pauseButton];
}

- (UIImage*)controlImageNamed:(NSString*)symbol fallback:(NSString*)fallback {
    UIImageSymbolConfiguration* configuration =
        [UIImageSymbolConfiguration configurationWithPointSize:28.0
                                                        weight:UIImageSymbolWeightSemibold];
    UIImage* image = [UIImage systemImageNamed:symbol withConfiguration:configuration];
    if (image == nil && fallback.length > 0) {
        image = [UIImage systemImageNamed:fallback withConfiguration:configuration];
    }
    return image;
}

- (void)styleControlButton:(UIButton*)button
                    symbol:(NSString*)symbol
                  fallback:(NSString*)fallback
                     label:(NSString*)label
                identifier:(NSString*)identifier {
    button.configuration = nil;
    [button setTitle:nil forState:UIControlStateNormal];
    [button setImage:[self controlImageNamed:symbol fallback:fallback]
            forState:UIControlStateNormal];
    button.tintColor = UIColor.whiteColor;
    button.backgroundColor = [UIColor colorWithWhite:0.08 alpha:0.42];
    button.layer.borderColor = [UIColor colorWithWhite:1.0 alpha:0.58].CGColor;
    button.layer.borderWidth = 1.4;
    button.layer.shadowColor = UIColor.blackColor.CGColor;
    button.layer.shadowOpacity = 0.35;
    button.layer.shadowRadius = 3.0;
    button.layer.shadowOffset = CGSizeMake(0.0, 1.0);
    button.imageView.contentMode = UIViewContentModeScaleAspectFit;
    button.contentEdgeInsets = UIEdgeInsetsMake(12.0, 12.0, 12.0, 12.0);
    button.accessibilityLabel = label;
    button.accessibilityIdentifier = identifier;
    button.exclusiveTouch = YES;
}

- (void)updatePauseButtonForComputerActive:(BOOL)computerActive {
    NSString* symbol = computerActive ? @"xmark" : @"pause.fill";
    NSString* label = computerActive ? @"Exit NETRICSA" : @"Pause";
    [_pauseButton setImage:[self controlImageNamed:symbol fallback:@"circle.fill"]
                  forState:UIControlStateNormal];
    _pauseButton.accessibilityLabel = label;
}

- (UILabel*)controlsEditorLabelWithText:(NSString*)text font:(UIFont*)font {
    UILabel* label = [[UILabel alloc] initWithFrame:CGRectZero];
    label.text = text;
    label.font = font;
    label.textColor = UIColor.whiteColor;
    label.numberOfLines = 0;
    [_controlsEditorPanel addSubview:label];
    return label;
}

- (UIView*)descendantViewWithAccessibilityIdentifier:(NSString*)identifier
                                               inView:(UIView*)root {
    if ([root.accessibilityIdentifier isEqualToString:identifier]) {
        return root;
    }
    for (UIView* subview in root.subviews) {
        UIView* match = [self descendantViewWithAccessibilityIdentifier:identifier inView:subview];
        if (match != nil) {
            return match;
        }
    }
    return nil;
}

- (UIButton*)controlsEditorButtonWithTitle:(NSString*)title action:(SEL)action {
    UIButton* button = [UIButton buttonWithType:UIButtonTypeSystem];
    UIButtonConfiguration* configuration = [UIButtonConfiguration tintedButtonConfiguration];
    configuration.baseForegroundColor = UIColor.whiteColor;
    configuration.baseBackgroundColor = [UIColor colorWithWhite:1.0 alpha:0.16];
    configuration.cornerStyle = UIButtonConfigurationCornerStyleMedium;
    button.configuration = configuration;
    [button setTitle:title forState:UIControlStateNormal];
    [button addTarget:self action:action forControlEvents:UIControlEventTouchUpInside];
    [_controlsEditorPanel addSubview:button];
    return button;
}

- (NSString*)controlLayoutKeyForButton:(UIButton*)button {
    NSString* identifier = button.accessibilityIdentifier ?: @"unknown";
    return [@"SeriousIOS.TouchControlLayout." stringByAppendingString:identifier];
}

- (CGRect)clampedControlFrame:(CGRect)frame {
    const CGRect bounds = self.bounds;
    const UIEdgeInsets safe = self.safeAreaInsets;
    const CGFloat padding = 6.0;
    const CGFloat minX = safe.left + padding;
    const CGFloat minY = safe.top + padding;
    const CGFloat maxX = MAX(minX, CGRectGetWidth(bounds) - safe.right - padding - CGRectGetWidth(frame));
    const CGFloat maxY = MAX(minY, CGRectGetHeight(bounds) - safe.bottom - padding - CGRectGetHeight(frame));
    frame.origin.x = MIN(maxX, MAX(minX, frame.origin.x));
    frame.origin.y = MIN(maxY, MAX(minY, frame.origin.y));
    return frame;
}

- (CGRect)storedControlFrameForButton:(UIButton*)button defaultFrame:(CGRect)defaultFrame {
    NSDictionary* stored = [NSUserDefaults.standardUserDefaults
        dictionaryForKey:[self controlLayoutKeyForButton:button]];
    if (stored == nil) {
        return [self clampedControlFrame:defaultFrame];
    }

    const CGFloat width = CGRectGetWidth(self.bounds);
    const CGFloat height = CGRectGetHeight(self.bounds);
    const CGFloat unit = MIN(width, height);
    NSNumber* centerXValue = stored[@"centerX"];
    NSNumber* centerYValue = stored[@"centerY"];
    NSNumber* sizeValue = stored[@"size"];
    if (width <= 0.0 || height <= 0.0 || unit <= 0.0
        || centerXValue == nil || centerYValue == nil || sizeValue == nil) {
        return [self clampedControlFrame:defaultFrame];
    }

    const CGFloat minimumSize = 44.0;
    const CGFloat maximumSize = MAX(minimumSize, unit * 0.28);
    const CGFloat size = MIN(maximumSize, MAX(minimumSize, sizeValue.doubleValue * unit));
    const CGPoint center = CGPointMake(
        centerXValue.doubleValue * width,
        centerYValue.doubleValue * height);
    return [self clampedControlFrame:CGRectMake(
        center.x - size * 0.5,
        center.y - size * 0.5,
        size,
        size)];
}

- (void)persistControlFrameForButton:(UIButton*)button {
    const CGFloat width = CGRectGetWidth(self.bounds);
    const CGFloat height = CGRectGetHeight(self.bounds);
    const CGFloat unit = MIN(width, height);
    if (width <= 0.0 || height <= 0.0 || unit <= 0.0) {
        return;
    }
    const CGRect frame = [self clampedControlFrame:button.frame];
    button.frame = frame;
    NSDictionary* stored = @{
        @"centerX": @(CGRectGetMidX(frame) / width),
        @"centerY": @(CGRectGetMidY(frame) / height),
        @"size": @(MAX(CGRectGetWidth(frame), CGRectGetHeight(frame)) / unit),
    };
    [NSUserDefaults.standardUserDefaults setObject:stored
                                            forKey:[self controlLayoutKeyForButton:button]];
    SeriousIOS_DiagnosticsLog(
        "input",
        "touch_layout_saved control=%s center_x=%.4f center_y=%.4f size=%.4f",
        button.accessibilityIdentifier.UTF8String,
        CGRectGetMidX(frame) / width,
        CGRectGetMidY(frame) / height,
        MAX(CGRectGetWidth(frame), CGRectGetHeight(frame)) / unit);
}

- (void)updateControlButtonCorners {
    for (UIButton* button in [self gameplayControlButtons]) {
        button.layer.cornerRadius = MIN(CGRectGetWidth(button.bounds), CGRectGetHeight(button.bounds)) * 0.5;
    }
}

- (void)controlEditorPan:(UIPanGestureRecognizer*)gesture {
    if (!_controlsEditorVisible || ![gesture.view isKindOfClass:UIButton.class]) {
        return;
    }
    UIButton* button = (UIButton*)gesture.view;
    const CGPoint translation = [gesture translationInView:self];
    button.center = CGPointMake(
        button.center.x + translation.x,
        button.center.y + translation.y);
    [gesture setTranslation:CGPointZero inView:self];
    button.frame = [self clampedControlFrame:button.frame];
    if (gesture.state == UIGestureRecognizerStateEnded
        || gesture.state == UIGestureRecognizerStateCancelled) {
        [self persistControlFrameForButton:button];
    }
}

- (void)controlEditorPinch:(UIPinchGestureRecognizer*)gesture {
    if (!_controlsEditorVisible || ![gesture.view isKindOfClass:UIButton.class]) {
        return;
    }
    UIButton* button = (UIButton*)gesture.view;
    const CGFloat unit = MIN(CGRectGetWidth(self.bounds), CGRectGetHeight(self.bounds));
    const CGFloat minimumSize = 44.0;
    const CGFloat maximumSize = MAX(minimumSize, unit * 0.28);
    const CGFloat currentSize = MAX(CGRectGetWidth(button.bounds), CGRectGetHeight(button.bounds));
    const CGFloat size = MIN(maximumSize, MAX(minimumSize, currentSize * gesture.scale));
    const CGPoint center = button.center;
    button.bounds = CGRectMake(0.0, 0.0, size, size);
    button.center = center;
    button.frame = [self clampedControlFrame:button.frame];
    gesture.scale = 1.0;
    [self updateControlButtonCorners];
    if (gesture.state == UIGestureRecognizerStateEnded
        || gesture.state == UIGestureRecognizerStateCancelled) {
        [self persistControlFrameForButton:button];
    }
}

- (void)updateSensitivityValueLabels {
    _gyroSensitivityValueLabel.text = [NSString stringWithFormat:@"%.2fx", _gyroSensitivity];
    _touchSensitivityValueLabel.text = [NSString stringWithFormat:@"%.2fx", _touchAimSensitivity];
}

- (void)gyroEnabledChanged:(UISwitch*)sender {
    _gyroEnabled = sender.isOn;
    _lastMotionTimestamp = 0.0;
    _gyroRemainderX = 0.0;
    _gyroRemainderY = 0.0;
    [NSUserDefaults.standardUserDefaults setBool:_gyroEnabled
                                          forKey:@"SeriousIOS.GyroEnabled"];
    SeriousIOS_DiagnosticsLog("input", "gyro_setting enabled=%d", _gyroEnabled ? 1 : 0);
}

- (void)gyroSensitivityChanged:(UISlider*)sender {
    _gyroSensitivity = sender.value;
    [NSUserDefaults.standardUserDefaults setDouble:_gyroSensitivity
                                            forKey:@"SeriousIOS.GyroSensitivity"];
    [self updateSensitivityValueLabels];
}

- (void)touchSensitivityChanged:(UISlider*)sender {
    _touchAimSensitivity = sender.value;
    [NSUserDefaults.standardUserDefaults setDouble:_touchAimSensitivity
                                            forKey:@"SeriousIOS.TouchAimSensitivity"];
    [self updateSensitivityValueLabels];
}

- (void)resetTouchControlLayout {
    for (UIButton* button in [self gameplayControlButtons]) {
        [NSUserDefaults.standardUserDefaults removeObjectForKey:[self controlLayoutKeyForButton:button]];
    }
    [self layoutGameplayControls];
    SeriousIOS_DiagnosticsLog("input", "touch_layout_reset");
}

- (void)showControlsEditor {
    if (_controlsEditorVisible || SeriousIOS_ApplicationComputerActive()) {
        return;
    }
    _controlsEditorVisible = YES;
    [self releaseGameplayTouches];
    SeriousIOS_ReleaseVirtualController();
    _displayLink.paused = YES;
    _controlsEditorOverlay.hidden = NO;
    [self bringSubviewToFront:_controlsEditorOverlay];
    for (UIButton* button in [self gameplayControlButtons]) {
        button.hidden = NO;
        [self bringSubviewToFront:button];
    }
    for (UIGestureRecognizer* gesture in _controlEditingGestures) {
        gesture.enabled = YES;
    }
    [self layoutControlsEditor];
    SeriousIOS_DiagnosticsLog(
        "input",
        "controls_editor_opened gyro=%d gyro_sensitivity=%.3f touch_sensitivity=%.3f",
        _gyroEnabled ? 1 : 0,
        _gyroSensitivity,
        _touchAimSensitivity);
}

- (void)hideControlsEditor {
    if (!_controlsEditorVisible) {
        return;
    }
    for (UIButton* button in [self gameplayControlButtons]) {
        [self persistControlFrameForButton:button];
    }
    for (UIGestureRecognizer* gesture in _controlEditingGestures) {
        gesture.enabled = NO;
    }
    _controlsEditorOverlay.hidden = YES;
    _controlsEditorVisible = NO;
    _lastMotionTimestamp = 0.0;
    _gyroRemainderX = 0.0;
    _gyroRemainderY = 0.0;
    _displayLink.paused = NO;
    [self updateGameplayControlVisibility];
    SeriousIOS_DiagnosticsLog("input", "controls_editor_closed");
}

- (void)pauseButtonLongPressed:(UILongPressGestureRecognizer*)gesture {
    if (gesture.state == UIGestureRecognizerStateBegan) {
        if (!SeriousIOS_ApplicationComputerActive()) {
            _pauseLongPressRecognized = YES;
            [self showControlsEditor];
        }
        return;
    }
    if (gesture.state == UIGestureRecognizerStateEnded
        || gesture.state == UIGestureRecognizerStateCancelled
        || gesture.state == UIGestureRecognizerStateFailed) {
        dispatch_after(
            dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.30 * NSEC_PER_SEC)),
            dispatch_get_main_queue(), ^{
                self->_pauseLongPressRecognized = NO;
            });
    }
}

- (void)handleDeviceMotion:(CMDeviceMotion*)motion error:(NSError*)error {
    if (error != nil) {
        static BOOL loggedMotionError = NO;
        if (!loggedMotionError) {
            loggedMotionError = YES;
            SeriousIOS_DiagnosticsLog(
                "input",
                "gyro_update_failed domain=%s code=%ld",
                error.domain.UTF8String,
                (long)error.code);
        }
        return;
    }
    if (motion == nil) {
        return;
    }

    const BOOL active = _gyroEnabled
        && !_controlsEditorVisible
        && UIApplication.sharedApplication.applicationState == UIApplicationStateActive
        && SeriousIOS_ApplicationGameplayControlsActive()
        && !SeriousIOS_ApplicationComputerActive();
    if (!active) {
        _lastMotionTimestamp = motion.timestamp;
        _gyroRemainderX = 0.0;
        _gyroRemainderY = 0.0;
        return;
    }

    NSTimeInterval deltaTime = _lastMotionTimestamp > 0.0
        ? motion.timestamp - _lastMotionTimestamp
        : 0.0;
    _lastMotionTimestamp = motion.timestamp;
    if (deltaTime <= 0.0 || deltaTime > 0.050) {
        return;
    }

    const CMRotationRate rate = motion.rotationRate;
    UIInterfaceOrientation orientation = self.window.windowScene.interfaceOrientation;
    double yawRate = 0.0;
    double pitchRate = 0.0;
    if (orientation == UIInterfaceOrientationLandscapeLeft) {
        yawRate = -rate.x;
        pitchRate = rate.y;
    } else if (orientation == UIInterfaceOrientationLandscapeRight) {
        yawRate = rate.x;
        pitchRate = -rate.y;
    } else {
        yawRate = rate.y;
        pitchRate = rate.x;
    }

    const CGFloat scale = self.contentScaleFactor > 0.0 ? self.contentScaleFactor : 1.0;
    const double pointsPerRadian = 280.0 * _gyroSensitivity * scale;
    const double accumulatedX = yawRate * deltaTime * pointsPerRadian + _gyroRemainderX;
    const double accumulatedY = pitchRate * deltaTime * pointsPerRadian + _gyroRemainderY;
    const int deltaX = (int)llround(accumulatedX);
    const int deltaY = (int)llround(accumulatedY);
    _gyroRemainderX = accumulatedX - deltaX;
    _gyroRemainderY = accumulatedY - deltaY;
    if (deltaX != 0 || deltaY != 0) {
        SeriousIOS_AddSDLRelativeMouseDelta(deltaX, deltaY);
    }
}

- (void)configureAdvancedTouchControls {
    NSUserDefaults* defaults = NSUserDefaults.standardUserDefaults;
    _gyroEnabled = [defaults objectForKey:@"SeriousIOS.GyroEnabled"] != nil
        ? [defaults boolForKey:@"SeriousIOS.GyroEnabled"]
        : NO;
    _gyroSensitivity = [defaults objectForKey:@"SeriousIOS.GyroSensitivity"] != nil
        ? [defaults doubleForKey:@"SeriousIOS.GyroSensitivity"]
        : 1.0;
    _touchAimSensitivity = [defaults objectForKey:@"SeriousIOS.TouchAimSensitivity"] != nil
        ? [defaults doubleForKey:@"SeriousIOS.TouchAimSensitivity"]
        : 0.72;

    [self styleControlButton:_fireButton
                      symbol:@"scope"
                    fallback:@"circle.circle"
                       label:@"Fire"
                  identifier:@"fire"];
    [self styleControlButton:_jumpButton
                      symbol:@"arrow.up"
                    fallback:@"chevron.up"
                       label:@"Jump"
                  identifier:@"jump"];
    [self styleControlButton:_useButton
                      symbol:@"hand.tap.fill"
                    fallback:@"hand.point.up.left.fill"
                       label:@"Use"
                  identifier:@"use"];
    [self styleControlButton:_skipButton
                      symbol:@"forward.fill"
                    fallback:@"chevron.right.2"
                       label:@"Skip sequence"
                  identifier:@"skip"];
    [self styleControlButton:_pauseButton
                      symbol:@"pause.fill"
                    fallback:@"circle.fill"
                       label:@"Pause"
                  identifier:@"pause"];

    _controlEditingGestures = [NSMutableArray array];
    for (UIButton* button in [self gameplayControlButtons]) {
        UIPanGestureRecognizer* pan = [[UIPanGestureRecognizer alloc]
            initWithTarget:self action:@selector(controlEditorPan:)];
        pan.maximumNumberOfTouches = 1;
        pan.enabled = NO;
        [button addGestureRecognizer:pan];
        [_controlEditingGestures addObject:pan];

        UIPinchGestureRecognizer* pinch = [[UIPinchGestureRecognizer alloc]
            initWithTarget:self action:@selector(controlEditorPinch:)];
        pinch.enabled = NO;
        [button addGestureRecognizer:pinch];
        [_controlEditingGestures addObject:pinch];
    }

    UILongPressGestureRecognizer* pauseLongPress = [[UILongPressGestureRecognizer alloc]
        initWithTarget:self action:@selector(pauseButtonLongPressed:)];
    pauseLongPress.minimumPressDuration = 0.55;
    pauseLongPress.cancelsTouchesInView = YES;
    [_pauseButton addGestureRecognizer:pauseLongPress];

    _controlsEditorOverlay = [[UIView alloc] initWithFrame:self.bounds];
    _controlsEditorOverlay.hidden = YES;
    _controlsEditorOverlay.backgroundColor = [UIColor colorWithWhite:0.0 alpha:0.56];
    [self addSubview:_controlsEditorOverlay];

    _controlsEditorPanel = [[UIView alloc] initWithFrame:CGRectZero];
    _controlsEditorPanel.backgroundColor = [UIColor colorWithWhite:0.08 alpha:0.96];
    _controlsEditorPanel.layer.cornerRadius = 18.0;
    _controlsEditorPanel.layer.borderWidth = 1.0;
    _controlsEditorPanel.layer.borderColor = [UIColor colorWithWhite:1.0 alpha:0.20].CGColor;
    [_controlsEditorOverlay addSubview:_controlsEditorPanel];

    UILabel* title = [self controlsEditorLabelWithText:@"Touch controls"
                                                  font:[UIFont systemFontOfSize:19.0 weight:UIFontWeightBold]];
    title.accessibilityIdentifier = @"controls-editor-title";
    UILabel* instructions = [self controlsEditorLabelWithText:
        @"Drag buttons to move them. Pinch a button to resize it."
                                                       font:[UIFont systemFontOfSize:12.0 weight:UIFontWeightRegular]];
    instructions.textColor = [UIColor colorWithWhite:0.86 alpha:1.0];
    instructions.accessibilityIdentifier = @"controls-editor-instructions";

    UILabel* gyroLabel = [self controlsEditorLabelWithText:@"Gyro aiming"
                                                       font:[UIFont systemFontOfSize:14.0 weight:UIFontWeightSemibold]];
    gyroLabel.accessibilityIdentifier = @"gyro-enabled-label";
    _gyroSwitch = [[UISwitch alloc] initWithFrame:CGRectZero];
    _gyroSwitch.on = _gyroEnabled;
    [_gyroSwitch addTarget:self action:@selector(gyroEnabledChanged:)
          forControlEvents:UIControlEventValueChanged];
    [_controlsEditorPanel addSubview:_gyroSwitch];

    UILabel* gyroSensitivityLabel = [self controlsEditorLabelWithText:@"Gyro sensitivity"
                                                                  font:[UIFont systemFontOfSize:13.0 weight:UIFontWeightMedium]];
    gyroSensitivityLabel.accessibilityIdentifier = @"gyro-sensitivity-label";
    _gyroSensitivityValueLabel = [self controlsEditorLabelWithText:@""
                                                                   font:[UIFont monospacedDigitSystemFontOfSize:12.0 weight:UIFontWeightMedium]];
    _gyroSensitivityValueLabel.textAlignment = NSTextAlignmentRight;
    _gyroSensitivitySlider = [[UISlider alloc] initWithFrame:CGRectZero];
    _gyroSensitivitySlider.minimumValue = 0.10f;
    _gyroSensitivitySlider.maximumValue = 3.00f;
    _gyroSensitivitySlider.value = _gyroSensitivity;
    [_gyroSensitivitySlider addTarget:self action:@selector(gyroSensitivityChanged:)
                       forControlEvents:UIControlEventValueChanged];
    [_controlsEditorPanel addSubview:_gyroSensitivitySlider];

    UILabel* touchSensitivityLabel = [self controlsEditorLabelWithText:@"Touch aim sensitivity"
                                                                   font:[UIFont systemFontOfSize:13.0 weight:UIFontWeightMedium]];
    touchSensitivityLabel.accessibilityIdentifier = @"touch-sensitivity-label";
    _touchSensitivityValueLabel = [self controlsEditorLabelWithText:@""
                                                                    font:[UIFont monospacedDigitSystemFontOfSize:12.0 weight:UIFontWeightMedium]];
    _touchSensitivityValueLabel.textAlignment = NSTextAlignmentRight;
    _touchSensitivitySlider = [[UISlider alloc] initWithFrame:CGRectZero];
    _touchSensitivitySlider.minimumValue = 0.20f;
    _touchSensitivitySlider.maximumValue = 2.50f;
    _touchSensitivitySlider.value = _touchAimSensitivity;
    [_touchSensitivitySlider addTarget:self action:@selector(touchSensitivityChanged:)
                        forControlEvents:UIControlEventValueChanged];
    [_controlsEditorPanel addSubview:_touchSensitivitySlider];

    UIButton* reset = [self controlsEditorButtonWithTitle:@"Reset layout"
                                                   action:@selector(resetTouchControlLayout)];
    reset.accessibilityIdentifier = @"controls-editor-reset";
    UIButton* done = [self controlsEditorButtonWithTitle:@"Done"
                                                  action:@selector(hideControlsEditor)];
    done.accessibilityIdentifier = @"controls-editor-done";
    [self updateSensitivityValueLabels];

    _motionManager = [[CMMotionManager alloc] init];
    if (_motionManager.deviceMotionAvailable) {
        _motionManager.deviceMotionUpdateInterval = 1.0 / 100.0;
        __weak SeriousIOSRenderView* weakSelf = self;
        [_motionManager startDeviceMotionUpdatesUsingReferenceFrame:CMAttitudeReferenceFrameXArbitraryZVertical
                                                            toQueue:NSOperationQueue.mainQueue
                                                        withHandler:^(CMDeviceMotion* motion, NSError* error) {
            [weakSelf handleDeviceMotion:motion error:error];
        }];
        SeriousIOS_DiagnosticsLog(
            "input",
            "gyro_configured available=1 enabled=%d update_hz=100 sensitivity=%.3f",
            _gyroEnabled ? 1 : 0,
            _gyroSensitivity);
    } else {
        _gyroEnabled = NO;
        _gyroSwitch.on = NO;
        _gyroSwitch.enabled = NO;
        SeriousIOS_DiagnosticsLog("input", "gyro_configured available=0 enabled=0");
    }
}

- (void)layoutControlsEditor {
    if (_controlsEditorOverlay == nil) {
        return;
    }
    _controlsEditorOverlay.frame = self.bounds;
    const CGFloat width = CGRectGetWidth(self.bounds);
    const CGFloat height = CGRectGetHeight(self.bounds);
    const CGFloat panelWidth = MIN(350.0, MAX(300.0, width * 0.42));
    const CGFloat panelHeight = MIN(300.0, MAX(270.0, height - self.safeAreaInsets.top - self.safeAreaInsets.bottom - 20.0));
    const CGFloat panelX = self.safeAreaInsets.left + 10.0;
    const CGFloat panelY = MAX(self.safeAreaInsets.top + 10.0, (height - panelHeight) * 0.5);
    _controlsEditorPanel.frame = CGRectMake(panelX, panelY, panelWidth, panelHeight);

    UIView* titleView = [self descendantViewWithAccessibilityIdentifier:@"controls-editor-title"
                                                                  inView:_controlsEditorPanel];
    UIView* instructionsView = [self descendantViewWithAccessibilityIdentifier:@"controls-editor-instructions"
                                                                         inView:_controlsEditorPanel];
    UIView* gyroLabelView = [self descendantViewWithAccessibilityIdentifier:@"gyro-enabled-label"
                                                                      inView:_controlsEditorPanel];
    UIView* gyroSensitivityLabelView = [self descendantViewWithAccessibilityIdentifier:@"gyro-sensitivity-label"
                                                                                 inView:_controlsEditorPanel];
    UIView* touchSensitivityLabelView = [self descendantViewWithAccessibilityIdentifier:@"touch-sensitivity-label"
                                                                                  inView:_controlsEditorPanel];
    UIButton* reset = (UIButton*)[self descendantViewWithAccessibilityIdentifier:@"controls-editor-reset"
                                                                             inView:_controlsEditorPanel];
    UIButton* done = (UIButton*)[self descendantViewWithAccessibilityIdentifier:@"controls-editor-done"
                                                                            inView:_controlsEditorPanel];

    const CGFloat left = 18.0;
    const CGFloat right = 18.0;
    const CGFloat contentWidth = panelWidth - left - right;
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
}
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_text(text: str) -> str:
    text = replace_once(
        text,
        '#import <UIKit/UIKit.h>\n',
        '#import <UIKit/UIKit.h>\n#import <CoreMotion/CoreMotion.h>\n',
        'Core Motion import',
    )
    text = replace_once(
        text,
        '''    CGPoint _movementOrigin;\n    CGPoint _lookPrevious;\n    BOOL _startupScheduled;''',
        '''    CGPoint _movementOrigin;\n    CGPoint _lookPrevious;\n''' + ADVANCED_IVARS + '''    BOOL _startupScheduled;''',
        'advanced control ivars',
    )
    text = replace_once(
        text,
        '''    [_pauseButton addTarget:self action:@selector(gameplayPause)\n          forControlEvents:UIControlEventTouchUpInside];\n\n    [NSLayoutConstraint activateConstraints:@[''',
        '''    [_pauseButton addTarget:self action:@selector(gameplayPause)\n          forControlEvents:UIControlEventTouchUpInside];\n\n    [self configureAdvancedTouchControls];\n\n    [NSLayoutConstraint activateConstraints:@[''',
        'advanced control initialization',
    )
    text = replace_once(
        text,
        '''- (void)dealloc {\n    [_displayLink invalidate];''',
        '''- (void)dealloc {\n    [_motionManager stopDeviceMotionUpdates];\n    _motionManager = nil;\n    [_displayLink invalidate];''',
        'motion cleanup',
    )
    text = replace_once(
        text,
        '''- (void)layoutSubviews {\n    [super layoutSubviews];\n    [self createDrawable];\n    [self layoutGameplayControls];\n}''',
        '''- (void)layoutSubviews {\n    [super layoutSubviews];\n    [self createDrawable];\n    [self layoutGameplayControls];\n    [self layoutControlsEditor];\n}''',
        'editor layout hook',
    )

    old_layout = text[text.index('- (void)layoutGameplayControls {'):text.index('- (void)releaseMovementKeys {')]
    new_layout = r'''- (void)layoutGameplayControls {
    const CGRect bounds = self.bounds;
    const CGFloat width = CGRectGetWidth(bounds);
    const CGFloat height = CGRectGetHeight(bounds);
    if (width <= 0.0 || height <= 0.0) {
        return;
    }

    const CGFloat unit = MIN(width, height);
    const CGFloat actionSize = MAX(54.0, MIN(78.0, unit * 0.145));
    const CGFloat fireSize = actionSize * 1.14;
    const CGFloat pauseSize = MAX(50.0, actionSize * 0.88);
    const CGFloat margin = MAX(12.0, unit * 0.025);
    const CGFloat gap = MAX(8.0, unit * 0.015);

    const CGRect fireDefault = CGRectMake(
        width - self.safeAreaInsets.right - margin - fireSize,
        height - self.safeAreaInsets.bottom - margin - fireSize,
        fireSize,
        fireSize);
    const CGRect jumpDefault = CGRectMake(
        width - self.safeAreaInsets.right - margin - actionSize,
        CGRectGetMinY(fireDefault) - gap - actionSize,
        actionSize,
        actionSize);
    const CGRect useDefault = CGRectMake(
        CGRectGetMinX(fireDefault) - gap - actionSize,
        CGRectGetMinY(fireDefault) - actionSize * 0.30,
        actionSize,
        actionSize);
    const CGRect pauseDefault = CGRectMake(
        width - self.safeAreaInsets.right - margin - pauseSize,
        self.safeAreaInsets.top + margin,
        pauseSize,
        pauseSize);
    const CGRect skipDefault = CGRectMake(
        CGRectGetMinX(pauseDefault) - gap - pauseSize,
        self.safeAreaInsets.top + margin,
        pauseSize,
        pauseSize);

    _fireButton.frame = [self storedControlFrameForButton:_fireButton defaultFrame:fireDefault];
    _jumpButton.frame = [self storedControlFrameForButton:_jumpButton defaultFrame:jumpDefault];
    _useButton.frame = [self storedControlFrameForButton:_useButton defaultFrame:useDefault];
    _skipButton.frame = [self storedControlFrameForButton:_skipButton defaultFrame:skipDefault];
    _pauseButton.frame = [self storedControlFrameForButton:_pauseButton defaultFrame:pauseDefault];
    [self updateControlButtonCorners];
}

'''
    text = text.replace(old_layout, new_layout, 1)

    text = text.replace('- (void)releaseMovementKeys {', ADVANCED_METHODS + '\n- (void)releaseMovementKeys {', 1)

    old_visibility_start = text.index('- (void)updateGameplayControlVisibility {')
    old_visibility_end = text.index('- (void)gameplayFireDown {', old_visibility_start)
    new_visibility = r'''- (void)updateGameplayControlVisibility {
    const BOOL active = SeriousIOS_ApplicationGameplayControlsActive();
    const BOOL computerActive = active && SeriousIOS_ApplicationComputerActive();

    if (_controlsEditorVisible) {
        for (UIButton* button in [self gameplayControlButtons]) {
            button.hidden = NO;
        }
        [self updatePauseButtonForComputerActive:NO];
        return;
    }

    _fireButton.hidden = !active || computerActive;
    _jumpButton.hidden = !active || computerActive;
    _useButton.hidden = !active || computerActive;
    _skipButton.hidden = !active || computerActive;
    _pauseButton.hidden = !active;
    [self updatePauseButtonForComputerActive:computerActive];

    if ((!active || computerActive)
        && (_movementTouch != nil || _lookTouch != nil)) {
        [self releaseGameplayTouches];
    }
}

'''
    text = text[:old_visibility_start] + new_visibility + text[old_visibility_end:]

    for selector in ('gameplayFireDown', 'gameplayFireUp', 'gameplayJumpDown', 'gameplayJumpUp', 'gameplayUseDown', 'gameplayUseUp', 'gameplaySkip'):
        marker = f'- (void){selector} {{\n'
        text = replace_once(
            text,
            marker,
            marker + '    if (_controlsEditorVisible) {\n        return;\n    }\n',
            f'{selector} editor guard',
        )

    text = replace_once(
        text,
        '''- (void)gameplayPause {\n    SeriousIOS_QueueSDLKey(27, true);''',
        '''- (void)gameplayPause {\n    if (_controlsEditorVisible) {\n        return;\n    }\n    if (_pauseLongPressRecognized) {\n        _pauseLongPressRecognized = NO;\n        return;\n    }\n    SeriousIOS_QueueSDLKey(27, true);''',
        'pause long-press guard',
    )
    text = replace_once(
        text,
        '''            SeriousIOS_AddSDLRelativeMouseDelta(\n                (int)llround(deltaX * scale * 0.72),\n                (int)llround(deltaY * scale * 0.72));''',
        '''            const CGFloat sensitivity = MIN(2.50, MAX(0.20, _touchAimSensitivity));\n            SeriousIOS_AddSDLRelativeMouseDelta(\n                (int)llround(deltaX * scale * sensitivity),\n                (int)llround(deltaY * scale * sensitivity));''',
        'touch sensitivity',
    )

    for method in ('touchesBegan', 'touchesMoved', 'touchesEnded', 'touchesCancelled'):
        marker = f'- (void){method}:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {{\n    (void)event;\n'
        text = replace_once(
            text,
            marker,
            marker + '    if (_controlsEditorVisible) {\n        return;\n    }\n',
            f'{method} editor guard',
        )

    required = (
        '#import <CoreMotion/CoreMotion.h>',
        'pauseButtonLongPressed:',
        'controls_editor_opened',
        'SeriousIOS.GyroSensitivity',
        'SeriousIOS.TouchAimSensitivity',
        'controlEditorPinch:',
        'symbol:@"scope"',
        'MIN(2.50, MAX(0.20, _touchAimSensitivity))',
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f'missing advanced control token: {token}')
    if 'setTitle:(computerActive ? @"EXIT" : @"PAUSE")' in text:
        raise RuntimeError('text pause/exit placeholder remains')
    return text


def self_test() -> None:
    fixture_path = Path(__file__).with_name('_touch_customization_fixture.mm')
    if fixture_path.exists():
        source = fixture_path.read_text(encoding='utf-8')
    else:
        source = '''#import <UIKit/UIKit.h>\n    CGPoint _movementOrigin;\n    CGPoint _lookPrevious;\n    BOOL _startupScheduled;\n    [_pauseButton addTarget:self action:@selector(gameplayPause)\n          forControlEvents:UIControlEventTouchUpInside];\n\n    [NSLayoutConstraint activateConstraints:@[\n- (void)dealloc {\n    [_displayLink invalidate];\n- (void)layoutSubviews {\n    [super layoutSubviews];\n    [self createDrawable];\n    [self layoutGameplayControls];\n}\n- (void)layoutGameplayControls {\n}\n\n- (void)releaseMovementKeys {\n}\n- (void)updateGameplayControlVisibility {\n}\n\n- (void)gameplayFireDown {\n}\n- (void)gameplayFireUp {\n}\n- (void)gameplayJumpDown {\n}\n- (void)gameplayJumpUp {\n}\n- (void)gameplayUseDown {\n}\n- (void)gameplayUseUp {\n}\n- (void)gameplaySkip {\n}\n- (void)gameplayPause {\n    SeriousIOS_QueueSDLKey(27, true);\n}\n            SeriousIOS_AddSDLRelativeMouseDelta(\n                (int)llround(deltaX * scale * 0.72),\n                (int)llround(deltaY * scale * 0.72));\n- (void)touchesBegan:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {\n    (void)event;\n}\n- (void)touchesMoved:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {\n    (void)event;\n}\n- (void)touchesEnded:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {\n    (void)event;\n}\n- (void)touchesCancelled:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {\n    (void)event;\n}\n'''
    transformed = transform_text(source)
    assert 'CMMotionManager* _motionManager;' in transformed
    assert 'symbol:@"scope"' in transformed
    assert 'controls_editor_opened' in transformed
    assert '* 0.72' not in transformed
    print('SeriousiOS touch customization transform self-test passed')


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
    print(f'Injected gyro, touch settings, icon controls, and layout editor into {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
