#import "SeriousIOSTouchOverlayView.h"

#import <CoreMotion/CoreMotion.h>
#import <QuartzCore/QuartzCore.h>

#include "SeriousIOSApplicationLifecycle.h"
#include "SeriousIOSDiagnostics.h"
#include "SeriousIOSPlatformBridge.h"

#include <algorithm>
#include <cmath>

namespace {

constexpr CGFloat kMovementZoneFraction = 0.46;
constexpr CGFloat kMovementDeadZone = 12.0;
constexpr CGFloat kMovementDiagonalRatio = 0.55;
constexpr float kDigitalMovementMagnitude = 0.95f;
constexpr CGFloat kLookGestureDisplacementSlop = 4.0;
constexpr CGFloat kLookGestureTravelSlop = 6.0;
constexpr int64_t kLookHoldFireDelayMilliseconds = 125;
constexpr int64_t kPulseMilliseconds = 80;
constexpr CGFloat kDefaultTouchAimScale = 0.018;
constexpr CGFloat kDefaultGyroAimScale = 6.0;
constexpr CGFloat kCurrentTouchBackendDefault = 0.72;
constexpr CGFloat kCurrentGyroBackendDefault = 1.0;
constexpr NSInteger kNoControl = -1;
constexpr NSInteger kSkipActionSentinel = -100;
constexpr NSUInteger kMaximumRawLookLogs = 20;

NSString* const kPreferencePrefix = @"SeriousIOS.TouchControls.v2";

NSString* PreferenceKey(NSString* component) {
    return [NSString stringWithFormat:@"%@.%@", kPreferencePrefix, component];
}

NSString* LayoutKey(NSInteger control, NSString* component) {
    return [NSString stringWithFormat:@"%@.control.%ld.%@", kPreferencePrefix,
                                      (long)control, component];
}

CGRect CircleRect(CGPoint center, CGFloat radius) {
    return CGRectMake(center.x - radius, center.y - radius,
                      radius * 2.0, radius * 2.0);
}

typedef NS_ENUM(NSInteger, SeriousIOSControlIndex) {
    SeriousIOSControlUse = 0,
    SeriousIOSControlJump,
    SeriousIOSControlCrouch,
    SeriousIOSControlWeapon,
    SeriousIOSControlPause,
    SeriousIOSControlFire,
    SeriousIOSControlSkip,
    SeriousIOSControlCount,
};

SeriousIOSVirtualAction ActionForControl(NSInteger control) {
    switch (control) {
        case SeriousIOSControlUse: return SERIOUSIOS_ACTION_USE;
        case SeriousIOSControlJump: return SERIOUSIOS_ACTION_JUMP;
        case SeriousIOSControlCrouch: return SERIOUSIOS_ACTION_CROUCH;
        case SeriousIOSControlWeapon: return SERIOUSIOS_ACTION_NEXT_WEAPON;
        case SeriousIOSControlFire: return SERIOUSIOS_ACTION_FIRE;
        default: return SERIOUSIOS_ACTION_COUNT;
    }
}

} // namespace

@interface SeriousIOSTouchOverlayView () {
    UITouch* _moveTouch;
    UITouch* _lookTouch;
    CGPoint _moveOrigin;
    CGPoint _lookOrigin;
    CGPoint _lookPrevious;
    NSMutableDictionary<NSValue*, NSNumber*>* _touchActions;

    BOOL _lookMoved;
    BOOL _lookFiring;
    CGFloat _lookTotalTravel;
    NSUInteger _lookGeneration;
    CGFloat _touchRemainderX;
    CGFloat _touchRemainderY;

    UITouch* _pauseTouch;
    BOOL _pauseHoldActivated;
    UILongPressGestureRecognizer* _pauseLongPressGesture;

    BOOL _gameplayActive;
    BOOL _computerActive;
    BOOL _layoutEditing;
    UITouch* _editTouch;
    NSInteger _editingControl;
    BOOL _editingResize;

    CGSize _controlLayoutSize;
    BOOL _controlLayoutReady;
    CGPoint _controlCenters[SeriousIOSControlCount];
    CGFloat _controlRadii[SeriousIOSControlCount];

    BOOL _fireButtonEnabled;
    BOOL _gyroEnabled;
    CGFloat _touchAimScale;
    CGFloat _gyroAimScale;

    CMMotionManager* _motionManager;
    NSTimeInterval _lastMotionTimestamp;
    CGFloat _gyroRemainderX;
    CGFloat _gyroRemainderY;

    UIView* _editorPanel;
    UIButton* _fireToggleButton;
    UIButton* _gyroToggleButton;
    UIButton* _doneButton;
    UILabel* _touchSensitivityLabel;
    UILabel* _gyroSensitivityLabel;
    UISlider* _touchSensitivitySlider;
    UISlider* _gyroSensitivitySlider;
    UILabel* _statusLabel;

    NSUInteger _rawLookLogCount;
}
@end

@implementation SeriousIOSTouchOverlayView

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self == nil) {
        return nil;
    }

    self.backgroundColor = UIColor.clearColor;
    self.opaque = NO;
    self.multipleTouchEnabled = YES;
    self.userInteractionEnabled = NO;
    self.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    _touchActions = [NSMutableDictionary dictionary];
    _editingControl = kNoControl;

    [self loadPreferences];
    [self createEditor];

    _pauseLongPressGesture = [[UILongPressGestureRecognizer alloc]
        initWithTarget:self action:@selector(pauseLongPress:)];
    _pauseLongPressGesture.minimumPressDuration = 2.0;
    _pauseLongPressGesture.allowableMovement = 32.0;
    _pauseLongPressGesture.cancelsTouchesInView = NO;
    _pauseLongPressGesture.delegate = self;
    [self addGestureRecognizer:_pauseLongPressGesture];

    _motionManager = [[CMMotionManager alloc] init];
    if (_motionManager.deviceMotionAvailable) {
        _motionManager.deviceMotionUpdateInterval = 1.0 / 100.0;
        __weak SeriousIOSTouchOverlayView* weakSelf = self;
        [_motionManager
            startDeviceMotionUpdatesUsingReferenceFrame:CMAttitudeReferenceFrameXArbitraryZVertical
            toQueue:NSOperationQueue.mainQueue
            withHandler:^(CMDeviceMotion* motion, NSError* error) {
                [weakSelf handleDeviceMotion:motion error:error];
            }];
    } else {
        _gyroEnabled = NO;
        _gyroToggleButton.enabled = NO;
    }

    [[NSNotificationCenter defaultCenter]
        addObserver:self selector:@selector(applicationWillResignActive:)
        name:UIApplicationWillResignActiveNotification object:nil];
    [[NSNotificationCenter defaultCenter]
        addObserver:self selector:@selector(applicationDidEnterBackground:)
        name:UIApplicationDidEnterBackgroundNotification object:nil];
    [[NSNotificationCenter defaultCenter]
        addObserver:self selector:@selector(applicationDidBecomeActive:)
        name:UIApplicationDidBecomeActiveNotification object:nil];

    SeriousIOS_DiagnosticsLog(
        "input",
        "SERIOUSSAM_IOS_CONTROLS: overlay_installed gyro_available=%d gyro_enabled=%d fire_button=%d",
        _motionManager.deviceMotionAvailable ? 1 : 0,
        _gyroEnabled ? 1 : 0,
        _fireButtonEnabled ? 1 : 0);
    return self;
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
    [self cancelAllInputWithReason:@"overlay-dealloc"];
    [_motionManager stopDeviceMotionUpdates];
}

- (void)loadPreferences {
    NSUserDefaults* defaults = NSUserDefaults.standardUserDefaults;

    NSString* gyroEnabledKey = PreferenceKey(@"gyro.enabled");
    if ([defaults objectForKey:gyroEnabledKey] != nil) {
        _gyroEnabled = [defaults boolForKey:gyroEnabledKey];
    } else if ([defaults objectForKey:@"SeriousIOS.GyroEnabled"] != nil) {
        _gyroEnabled = [defaults boolForKey:@"SeriousIOS.GyroEnabled"];
    } else {
        _gyroEnabled = YES;
    }

    NSString* fireEnabledKey = PreferenceKey(@"fireButton.enabled");
    _fireButtonEnabled = [defaults objectForKey:fireEnabledKey] != nil
        ? [defaults boolForKey:fireEnabledKey]
        : YES;

    NSString* touchKey = PreferenceKey(@"aim.touch");
    if ([defaults objectForKey:touchKey] != nil) {
        _touchAimScale = [defaults doubleForKey:touchKey];
    } else if ([defaults objectForKey:@"SeriousIOS.TouchAimSensitivity"] != nil) {
        _touchAimScale = [defaults doubleForKey:@"SeriousIOS.TouchAimSensitivity"] / 40.0;
    } else {
        _touchAimScale = kDefaultTouchAimScale;
    }
    _touchAimScale = std::max<CGFloat>(0.006, std::min<CGFloat>(0.060, _touchAimScale));

    NSString* gyroKey = PreferenceKey(@"aim.gyro");
    if ([defaults objectForKey:gyroKey] != nil) {
        _gyroAimScale = [defaults doubleForKey:gyroKey];
    } else if ([defaults objectForKey:@"SeriousIOS.GyroSensitivity"] != nil) {
        _gyroAimScale = [defaults doubleForKey:@"SeriousIOS.GyroSensitivity"] * 6.0;
    } else {
        _gyroAimScale = kDefaultGyroAimScale;
    }
    _gyroAimScale = std::max<CGFloat>(1.0, std::min<CGFloat>(12.0, _gyroAimScale));
}

- (void)createEditor {
    _statusLabel = [[UILabel alloc] initWithFrame:CGRectZero];
    _statusLabel.backgroundColor = [UIColor colorWithWhite:0.05 alpha:0.72];
    _statusLabel.textColor = UIColor.whiteColor;
    _statusLabel.font = [UIFont boldSystemFontOfSize:15.0];
    _statusLabel.textAlignment = NSTextAlignmentCenter;
    _statusLabel.layer.cornerRadius = 12.0;
    _statusLabel.clipsToBounds = YES;
    _statusLabel.alpha = 0.0;
    [self addSubview:_statusLabel];

    _editorPanel = [[UIView alloc] initWithFrame:CGRectZero];
    _editorPanel.backgroundColor = [UIColor colorWithWhite:0.03 alpha:0.90];
    _editorPanel.layer.cornerRadius = 16.0;
    _editorPanel.layer.borderWidth = 1.0;
    _editorPanel.layer.borderColor = [UIColor colorWithWhite:1.0 alpha:0.20].CGColor;
    _editorPanel.hidden = YES;
    [self addSubview:_editorPanel];

    UILabel* title = [[UILabel alloc] initWithFrame:CGRectZero];
    title.tag = 7001;
    title.text = @"CONTROL EDITOR";
    title.textColor = UIColor.whiteColor;
    title.font = [UIFont boldSystemFontOfSize:14.0];
    [_editorPanel addSubview:title];

    _fireToggleButton = [self editorButtonWithAction:@selector(toggleFireButton:)];
    _gyroToggleButton = [self editorButtonWithAction:@selector(toggleGyro:)];
    _doneButton = [self editorButtonWithAction:@selector(finishEditor:)];
    [_doneButton setTitle:@"DONE" forState:UIControlStateNormal];

    _touchSensitivityLabel = [self editorLabel];
    _gyroSensitivityLabel = [self editorLabel];

    _touchSensitivitySlider = [[UISlider alloc] initWithFrame:CGRectZero];
    _touchSensitivitySlider.minimumValue = 0.006f;
    _touchSensitivitySlider.maximumValue = 0.060f;
    _touchSensitivitySlider.value = _touchAimScale;
    _touchSensitivitySlider.minimumTrackTintColor =
        [UIColor colorWithRed:0.05 green:0.78 blue:0.90 alpha:1.0];
    [_touchSensitivitySlider addTarget:self action:@selector(sensitivityChanged:)
                      forControlEvents:UIControlEventValueChanged];
    [_editorPanel addSubview:_touchSensitivitySlider];

    _gyroSensitivitySlider = [[UISlider alloc] initWithFrame:CGRectZero];
    _gyroSensitivitySlider.minimumValue = 1.0f;
    _gyroSensitivitySlider.maximumValue = 12.0f;
    _gyroSensitivitySlider.value = _gyroAimScale;
    _gyroSensitivitySlider.minimumTrackTintColor =
        [UIColor colorWithRed:1.0 green:0.47 blue:0.08 alpha:1.0];
    [_gyroSensitivitySlider addTarget:self action:@selector(sensitivityChanged:)
                     forControlEvents:UIControlEventValueChanged];
    [_editorPanel addSubview:_gyroSensitivitySlider];

    [self updateEditorControls];
}

- (UIButton*)editorButtonWithAction:(SEL)action {
    UIButton* button = [UIButton buttonWithType:UIButtonTypeSystem];
    button.titleLabel.font = [UIFont boldSystemFontOfSize:13.0];
    button.layer.cornerRadius = 10.0;
    button.backgroundColor = [UIColor colorWithWhite:1.0 alpha:0.16];
    [button setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    [button addTarget:self action:action forControlEvents:UIControlEventTouchUpInside];
    [_editorPanel addSubview:button];
    return button;
}

- (UILabel*)editorLabel {
    UILabel* label = [[UILabel alloc] initWithFrame:CGRectZero];
    label.textColor = [UIColor colorWithWhite:0.92 alpha:1.0];
    label.font = [UIFont systemFontOfSize:12.0 weight:UIFontWeightSemibold];
    [_editorPanel addSubview:label];
    return label;
}

- (void)layoutSubviews {
    [super layoutSubviews];
    [self ensureControlLayout];

    _statusLabel.frame = CGRectMake(0.0, 0.0, 330.0, 42.0);
    _statusLabel.center = CGPointMake(CGRectGetMidX(self.bounds), 42.0);

    CGFloat panelWidth = MIN(CGRectGetWidth(self.bounds) - 32.0, 520.0);
    _editorPanel.frame = CGRectMake(
        (CGRectGetWidth(self.bounds) - panelWidth) * 0.5,
        MAX(12.0, self.safeAreaInsets.top + 4.0),
        panelWidth,
        124.0);
    UILabel* title = (UILabel*)[_editorPanel viewWithTag:7001];
    title.frame = CGRectMake(16.0, 10.0, 176.0, 30.0);
    _fireToggleButton.frame = CGRectMake(panelWidth - 324.0, 9.0, 114.0, 32.0);
    _gyroToggleButton.frame = CGRectMake(panelWidth - 202.0, 9.0, 102.0, 32.0);
    _doneButton.frame = CGRectMake(panelWidth - 92.0, 9.0, 76.0, 32.0);
    _touchSensitivityLabel.frame = CGRectMake(16.0, 47.0, 118.0, 27.0);
    _touchSensitivitySlider.frame = CGRectMake(134.0, 45.0, panelWidth - 150.0, 31.0);
    _gyroSensitivityLabel.frame = CGRectMake(16.0, 84.0, 118.0, 27.0);
    _gyroSensitivitySlider.frame = CGRectMake(134.0, 82.0, panelWidth - 150.0, 31.0);
}

- (CGPoint)defaultCenterForControl:(NSInteger)control {
    CGFloat width = CGRectGetWidth(self.bounds);
    CGFloat height = CGRectGetHeight(self.bounds);
    switch (control) {
        case SeriousIOSControlUse: return CGPointMake(width - 150.0, height - 105.0);
        case SeriousIOSControlJump: return CGPointMake(width - 72.0, height - 166.0);
        case SeriousIOSControlCrouch: return CGPointMake(width - 153.0, height - 42.0);
        case SeriousIOSControlWeapon: return CGPointMake(width - 226.0, height - 46.0);
        case SeriousIOSControlPause: return CGPointMake(width - 35.0, 35.0);
        case SeriousIOSControlFire: return CGPointMake(width - 72.0, height - 88.0);
        case SeriousIOSControlSkip: return CGPointMake(width - 100.0, 35.0);
        default: return CGPointMake(width * 0.5, height * 0.5);
    }
}

- (CGFloat)defaultRadiusForControl:(NSInteger)control {
    switch (control) {
        case SeriousIOSControlUse:
        case SeriousIOSControlJump: return 31.0;
        case SeriousIOSControlCrouch: return 28.0;
        case SeriousIOSControlWeapon: return 27.0;
        case SeriousIOSControlPause:
        case SeriousIOSControlSkip: return 25.0;
        case SeriousIOSControlFire: return 38.0;
        default: return 28.0;
    }
}

- (void)ensureControlLayout {
    CGSize size = self.bounds.size;
    if (size.width <= 0.0 || size.height <= 0.0) {
        return;
    }

    if (_controlLayoutReady) {
        if (!CGSizeEqualToSize(size, _controlLayoutSize)) {
            CGFloat sx = size.width / _controlLayoutSize.width;
            CGFloat sy = size.height / _controlLayoutSize.height;
            CGFloat sr = MIN(sx, sy);
            for (NSInteger control = 0; control < SeriousIOSControlCount; ++control) {
                _controlCenters[control].x *= sx;
                _controlCenters[control].y *= sy;
                _controlRadii[control] *= sr;
            }
            _controlLayoutSize = size;
        }
        return;
    }

    NSUserDefaults* defaults = NSUserDefaults.standardUserDefaults;
    CGFloat scale = MIN(size.width, size.height);
    for (NSInteger control = 0; control < SeriousIOSControlCount; ++control) {
        NSNumber* x = [defaults objectForKey:LayoutKey(control, @"x")];
        NSNumber* y = [defaults objectForKey:LayoutKey(control, @"y")];
        NSNumber* radius = [defaults objectForKey:LayoutKey(control, @"r")];
        if (x != nil && y != nil && radius != nil) {
            _controlCenters[control] = CGPointMake(x.doubleValue * size.width,
                                                   y.doubleValue * size.height);
            _controlRadii[control] = radius.doubleValue * scale;
        } else {
            _controlCenters[control] = [self defaultCenterForControl:control];
            _controlRadii[control] = [self defaultRadiusForControl:control];
        }
        _controlRadii[control] = MAX(20.0, MIN(64.0, _controlRadii[control]));
    }
    _controlLayoutSize = size;
    _controlLayoutReady = YES;
    SeriousIOS_DiagnosticsLog(
        "input", "SERIOUSSAM_IOS_CONTROLS: editor_layout_loaded version=2");
}

- (void)saveControlLayout {
    [self ensureControlLayout];
    CGFloat width = CGRectGetWidth(self.bounds);
    CGFloat height = CGRectGetHeight(self.bounds);
    CGFloat scale = MIN(width, height);
    if (width <= 0.0 || height <= 0.0 || scale <= 0.0) {
        return;
    }

    NSUserDefaults* defaults = NSUserDefaults.standardUserDefaults;
    for (NSInteger control = 0; control < SeriousIOSControlCount; ++control) {
        [defaults setDouble:_controlCenters[control].x / width
                     forKey:LayoutKey(control, @"x")];
        [defaults setDouble:_controlCenters[control].y / height
                     forKey:LayoutKey(control, @"y")];
        [defaults setDouble:_controlRadii[control] / scale
                     forKey:LayoutKey(control, @"r")];
    }
    SeriousIOS_DiagnosticsLog(
        "input", "SERIOUSSAM_IOS_CONTROLS: editor_layout_saved version=2");
}

- (CGPoint)centerForControl:(NSInteger)control {
    [self ensureControlLayout];
    return _controlCenters[control];
}

- (CGFloat)radiusForControl:(NSInteger)control {
    [self ensureControlLayout];
    return _controlRadii[control];
}

- (BOOL)gestureRecognizer:(UIGestureRecognizer*)gestureRecognizer
       shouldReceiveTouch:(UITouch*)touch {
    if (gestureRecognizer != _pauseLongPressGesture) {
        return YES;
    }
    CGPoint point = [touch locationInView:self];
    return CGRectContainsPoint(
        CircleRect([self centerForControl:SeriousIOSControlPause],
                   [self radiusForControl:SeriousIOSControlPause] + 10.0),
        point);
}

- (void)pauseLongPress:(UILongPressGestureRecognizer*)recognizer {
    if (recognizer.state != UIGestureRecognizerStateBegan || _pauseHoldActivated) {
        return;
    }
    _pauseHoldActivated = YES;
    [self toggleControlEditor];
}

- (void)updateGameplayActive:(BOOL)gameplayActive
              computerActive:(BOOL)computerActive {
    BOOL stateChanged = _gameplayActive != gameplayActive || _computerActive != computerActive;
    _gameplayActive = gameplayActive;
    _computerActive = computerActive;

    if (stateChanged && (!gameplayActive || computerActive)) {
        [self cancelAllInputWithReason:computerActive ? @"computer-active" : @"gameplay-inactive"];
    }

    self.hidden = !(_layoutEditing || gameplayActive || computerActive);
    self.userInteractionEnabled = _layoutEditing || gameplayActive || computerActive;
    [self setNeedsDisplay];
}

- (void)applicationWillResignActive:(NSNotification*)notification {
    (void)notification;
    [self cancelAllInputWithReason:@"will-resign-active"];
}

- (void)applicationDidEnterBackground:(NSNotification*)notification {
    (void)notification;
    [self cancelAllInputWithReason:@"did-enter-background"];
}

- (void)applicationDidBecomeActive:(NSNotification*)notification {
    (void)notification;
    _lastMotionTimestamp = 0.0;
    _gyroRemainderX = 0.0;
    _gyroRemainderY = 0.0;
    SeriousIOS_DiagnosticsLog(
        "input", "SERIOUSSAM_IOS_LIFECYCLE: overlay_became_active stale_input=0");
    [self setNeedsDisplay];
}

- (void)cancelAllInputWithReason:(NSString*)reason {
    SeriousIOS_SetVirtualMovement(0.0f, 0.0f);
    if (_lookFiring) {
        SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_FIRE, false);
    }
    for (NSNumber* actionNumber in _touchActions.allValues) {
        NSInteger raw = actionNumber.integerValue;
        if (raw >= 0 && raw < SERIOUSIOS_ACTION_COUNT) {
            SeriousIOS_SetVirtualAction((SeriousIOSVirtualAction)raw, false);
        }
    }
    [_touchActions removeAllObjects];
    SeriousIOS_ReleaseVirtualController();
    SeriousIOS_ReleaseSDLInput();

    _moveTouch = nil;
    _lookTouch = nil;
    _lookMoved = NO;
    _lookFiring = NO;
    _lookTotalTravel = 0.0;
    _lookGeneration += 1;
    _touchRemainderX = 0.0;
    _touchRemainderY = 0.0;
    _pauseTouch = nil;
    _pauseHoldActivated = NO;
    _editTouch = nil;
    _editingControl = kNoControl;
    _editingResize = NO;
    _lastMotionTimestamp = 0.0;
    _gyroRemainderX = 0.0;
    _gyroRemainderY = 0.0;

    SeriousIOS_DiagnosticsLog(
        "input", "SERIOUSSAM_IOS_LIFECYCLE: input_cancelled reason=%s",
        reason.UTF8String ?: "unknown");
    [self setNeedsDisplay];
}

- (void)toggleControlEditor {
    [self cancelAllInputWithReason:@"editor-toggle"];
    _layoutEditing = !_layoutEditing;
    _editorPanel.hidden = !_layoutEditing;
    if (!_layoutEditing) {
        [self saveControlLayout];
    }
    [self updateEditorControls];
    _statusLabel.text = @"CONTROL LAYOUT SAVED";
    _statusLabel.alpha = _layoutEditing ? 0.0 : 1.0;

    UINotificationFeedbackGenerator* feedback = [[UINotificationFeedbackGenerator alloc] init];
    [feedback notificationOccurred:_layoutEditing
        ? UINotificationFeedbackTypeSuccess
        : UINotificationFeedbackTypeWarning];
    if (!_layoutEditing) {
        [UIView animateWithDuration:0.25 delay:0.8
            options:UIViewAnimationOptionBeginFromCurrentState
            animations:^{ self->_statusLabel.alpha = 0.0; }
            completion:nil];
    }
    SeriousIOS_DiagnosticsLog(
        "input", "SERIOUSSAM_IOS_CONTROLS: editor_%s",
        _layoutEditing ? "opened" : "closed");
    [self setNeedsDisplay];
}

- (void)finishEditor:(UIButton*)sender {
    (void)sender;
    if (_layoutEditing) {
        [self toggleControlEditor];
    }
}

- (void)toggleFireButton:(UIButton*)sender {
    (void)sender;
    _fireButtonEnabled = !_fireButtonEnabled;
    [NSUserDefaults.standardUserDefaults setBool:_fireButtonEnabled
        forKey:PreferenceKey(@"fireButton.enabled")];
    [self updateEditorControls];
    [self setNeedsDisplay];
    UISelectionFeedbackGenerator* feedback = [[UISelectionFeedbackGenerator alloc] init];
    [feedback selectionChanged];
}

- (void)toggleGyro:(UIButton*)sender {
    (void)sender;
    _gyroEnabled = !_gyroEnabled && _motionManager.deviceMotionAvailable;
    [NSUserDefaults.standardUserDefaults setBool:_gyroEnabled
        forKey:PreferenceKey(@"gyro.enabled")];
    [self updateEditorControls];
    UISelectionFeedbackGenerator* feedback = [[UISelectionFeedbackGenerator alloc] init];
    [feedback selectionChanged];
    SeriousIOS_DiagnosticsLog(
        "input", "SERIOUSSAM_IOS_GYRO: enabled=%d", _gyroEnabled ? 1 : 0);
}

- (void)sensitivityChanged:(UISlider*)sender {
    (void)sender;
    _touchAimScale = _touchSensitivitySlider.value;
    _gyroAimScale = _gyroSensitivitySlider.value;
    NSUserDefaults* defaults = NSUserDefaults.standardUserDefaults;
    [defaults setDouble:_touchAimScale forKey:PreferenceKey(@"aim.touch")];
    [defaults setDouble:_gyroAimScale forKey:PreferenceKey(@"aim.gyro")];
    [self updateEditorControls];
}

- (void)updateEditorControls {
    [_fireToggleButton setTitle:_fireButtonEnabled ? @"FIRE ON" : @"FIRE OFF"
                       forState:UIControlStateNormal];
    _fireToggleButton.backgroundColor = _fireButtonEnabled
        ? [UIColor colorWithRed:0.88 green:0.24 blue:0.12 alpha:0.88]
        : [UIColor colorWithRed:0.48 green:0.16 blue:0.16 alpha:0.85];

    [_gyroToggleButton setTitle:_gyroEnabled ? @"GYRO ON" : @"GYRO OFF"
                       forState:UIControlStateNormal];
    _gyroToggleButton.backgroundColor = _gyroEnabled
        ? [UIColor colorWithRed:0.10 green:0.68 blue:0.35 alpha:0.85]
        : [UIColor colorWithRed:0.48 green:0.16 blue:0.16 alpha:0.85];

    _touchSensitivityLabel.text = [NSString stringWithFormat:
        @"TOUCH AIM %.1fx", _touchAimScale / kDefaultTouchAimScale];
    _gyroSensitivityLabel.text = [NSString stringWithFormat:
        @"GYRO AIM %.1fx", _gyroAimScale / kDefaultGyroAimScale];
}

- (NSInteger)controlAtPoint:(CGPoint)point {
    if (!_gameplayActive || _computerActive) {
        return kNoControl;
    }
    for (NSInteger control = 0; control < SeriousIOSControlCount; ++control) {
        if (control == SeriousIOSControlPause || control == SeriousIOSControlSkip) {
            continue;
        }
        if (control == SeriousIOSControlFire && !_fireButtonEnabled) {
            continue;
        }
        if (CGRectContainsPoint(
                CircleRect([self centerForControl:control],
                           [self radiusForControl:control]), point)) {
            return control;
        }
    }
    return kNoControl;
}

- (void)pulseEscape {
    SeriousIOS_QueueSDLKey(27, true);
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, kPulseMilliseconds * NSEC_PER_MSEC),
                   dispatch_get_main_queue(), ^{
        SeriousIOS_QueueSDLKey(27, false);
    });
}

- (void)pulseSkip {
    SeriousIOS_QueueSDLKey(' ', true);
    SeriousIOS_QueueSDLKey('\r', true);
    SeriousIOS_QueueSDLMouseButton(1, true);
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, kPulseMilliseconds * NSEC_PER_MSEC),
                   dispatch_get_main_queue(), ^{
        SeriousIOS_QueueSDLKey(' ', false);
        SeriousIOS_QueueSDLKey('\r', false);
        SeriousIOS_QueueSDLMouseButton(1, false);
    });
    SeriousIOS_DiagnosticsLog(
        "input", "SERIOUSSAM_IOS_TOUCH: skip_pulse milliseconds=%lld",
        (long long)kPulseMilliseconds);
}

- (void)pulseFire {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_FIRE, true);
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, kPulseMilliseconds * NSEC_PER_MSEC),
                   dispatch_get_main_queue(), ^{
        SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_FIRE, false);
    });
}

- (void)touchesBegan:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    for (UITouch* touch in touches) {
        CGPoint point = [touch locationInView:self];

        if (CGRectContainsPoint(
                CircleRect([self centerForControl:SeriousIOSControlPause],
                           [self radiusForControl:SeriousIOSControlPause] + 10.0), point)) {
            _pauseTouch = touch;
            _pauseHoldActivated = NO;
            continue;
        }

        if (_layoutEditing) {
            if (_editTouch == nil) {
                NSInteger nearest = kNoControl;
                CGFloat nearestDistance = CGFLOAT_MAX;
                for (NSInteger control = 0; control < SeriousIOSControlCount; ++control) {
                    if (control == SeriousIOSControlFire && !_fireButtonEnabled) {
                        continue;
                    }
                    CGFloat distance = hypot(point.x - _controlCenters[control].x,
                                             point.y - _controlCenters[control].y);
                    if (distance <= _controlRadii[control] + 18.0
                        && distance < nearestDistance) {
                        nearest = control;
                        nearestDistance = distance;
                    }
                }
                if (nearest != kNoControl) {
                    _editTouch = touch;
                    _editingControl = nearest;
                    _editingResize = nearestDistance >= _controlRadii[nearest] * 0.62;
                    UISelectionFeedbackGenerator* feedback =
                        [[UISelectionFeedbackGenerator alloc] init];
                    [feedback selectionChanged];
                }
            }
            continue;
        }

        if (_computerActive) {
            continue;
        }

        if (CGRectContainsPoint(
                CircleRect([self centerForControl:SeriousIOSControlSkip],
                           [self radiusForControl:SeriousIOSControlSkip]), point)) {
            [self pulseSkip];
            [_touchActions setObject:@(kSkipActionSentinel)
                forKey:[NSValue valueWithNonretainedObject:touch]];
            continue;
        }

        NSInteger control = [self controlAtPoint:point];
        if (control != kNoControl) {
            SeriousIOSVirtualAction action = ActionForControl(control);
            if (action != SERIOUSIOS_ACTION_COUNT) {
                SeriousIOS_SetVirtualAction(action, true);
                [_touchActions setObject:@((NSInteger)action)
                    forKey:[NSValue valueWithNonretainedObject:touch]];
            }
            continue;
        }

        if (_moveTouch == nil && point.x < CGRectGetWidth(self.bounds) * kMovementZoneFraction) {
            _moveTouch = touch;
            _moveOrigin = point;
            SeriousIOS_SetVirtualMovement(0.0f, 0.0f);
            continue;
        }

        if (_lookTouch == nil) {
            _lookTouch = touch;
            _lookOrigin = point;
            _lookPrevious = point;
            _lookMoved = NO;
            _lookFiring = NO;
            _lookTotalTravel = 0.0;
            _lookGeneration += 1;
            NSUInteger generation = _lookGeneration;
            __weak SeriousIOSTouchOverlayView* weakSelf = self;
            dispatch_after(
                dispatch_time(DISPATCH_TIME_NOW,
                              kLookHoldFireDelayMilliseconds * NSEC_PER_MSEC),
                dispatch_get_main_queue(), ^{
                    SeriousIOSTouchOverlayView* strongSelf = weakSelf;
                    if (strongSelf == nil) {
                        return;
                    }
                    if (strongSelf->_lookGeneration == generation
                        && strongSelf->_lookTouch == touch
                        && !strongSelf->_lookMoved
                        && !strongSelf->_lookFiring
                        && strongSelf->_gameplayActive
                        && !strongSelf->_computerActive
                        && !strongSelf->_layoutEditing) {
                        SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_FIRE, true);
                        strongSelf->_lookFiring = YES;
                        [strongSelf setNeedsDisplay];
                    }
                });
        }
    }

    if (_rawLookLogCount < kMaximumRawLookLogs) {
        SeriousIOS_DiagnosticsLog(
            "input", "SERIOUSSAM_IOS_TOUCH: began count=%lu move=%d look=%d actions=%lu",
            (unsigned long)touches.count,
            _moveTouch != nil ? 1 : 0,
            _lookTouch != nil ? 1 : 0,
            (unsigned long)_touchActions.count);
    }
    [self setNeedsDisplay];
}

- (void)touchesMoved:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    for (UITouch* touch in touches) {
        CGPoint point = [touch locationInView:self];

        if (_layoutEditing) {
            if (touch == _editTouch && _editingControl != kNoControl) {
                if (_editingResize) {
                    CGFloat distance = hypot(point.x - _controlCenters[_editingControl].x,
                                             point.y - _controlCenters[_editingControl].y);
                    _controlRadii[_editingControl] = MAX(20.0, MIN(64.0, distance));
                } else {
                    CGFloat radius = _controlRadii[_editingControl];
                    _controlCenters[_editingControl] = CGPointMake(
                        MAX(radius + 4.0,
                            MIN(CGRectGetWidth(self.bounds) - radius - 4.0, point.x)),
                        MAX(radius + 4.0,
                            MIN(CGRectGetHeight(self.bounds) - radius - 4.0, point.y)));
                }
                [self setNeedsDisplay];
            }
            continue;
        }

        if (!_gameplayActive || _computerActive) {
            continue;
        }

        if (touch == _moveTouch) {
            CGFloat dx = point.x - _moveOrigin.x;
            CGFloat dy = point.y - _moveOrigin.y;
            CGFloat adx = fabs(dx);
            CGFloat ady = fabs(dy);
            float right = 0.0f;
            float forward = 0.0f;
            if (MAX(adx, ady) >= kMovementDeadZone) {
                if (adx >= ady * kMovementDiagonalRatio) {
                    right = dx < 0.0 ? -kDigitalMovementMagnitude : kDigitalMovementMagnitude;
                }
                if (ady >= adx * kMovementDiagonalRatio) {
                    forward = dy < 0.0 ? kDigitalMovementMagnitude : -kDigitalMovementMagnitude;
                }
            }
            SeriousIOS_SetVirtualMovement(forward, right);
        } else if (touch == _lookTouch) {
            CGFloat dx = point.x - _lookPrevious.x;
            CGFloat dy = point.y - _lookPrevious.y;
            _lookTotalTravel += hypot(dx, dy);
            CGFloat displacement = hypot(point.x - _lookOrigin.x,
                                          point.y - _lookOrigin.y);
            if (!_lookFiring
                && (displacement >= kLookGestureDisplacementSlop
                    || _lookTotalTravel >= kLookGestureTravelSlop)) {
                _lookMoved = YES;
            }

            CGFloat nativeScale = self.contentScaleFactor > 0.0
                ? self.contentScaleFactor : 1.0;
            CGFloat backendScale = kCurrentTouchBackendDefault
                * (_touchAimScale / kDefaultTouchAimScale);
            CGFloat accumulatedX = dx * nativeScale * backendScale + _touchRemainderX;
            CGFloat accumulatedY = dy * nativeScale * backendScale + _touchRemainderY;
            int relativeX = (int)llround(accumulatedX);
            int relativeY = (int)llround(accumulatedY);
            _touchRemainderX = accumulatedX - relativeX;
            _touchRemainderY = accumulatedY - relativeY;
            if (relativeX != 0 || relativeY != 0) {
                SeriousIOS_AddSDLRelativeMouseDelta(relativeX, relativeY);
            }
            _lookPrevious = point;

            if (_rawLookLogCount < kMaximumRawLookLogs) {
                SeriousIOS_DiagnosticsLog(
                    "input",
                    "SERIOUSSAM_IOS_TOUCH: look_sample dx=%.2f dy=%.2f output_x=%d output_y=%d firing=%d",
                    dx, dy, relativeX, relativeY, _lookFiring ? 1 : 0);
                _rawLookLogCount += 1;
            }
        }
    }
    [self setNeedsDisplay];
}

- (void)finishTouches:(NSSet<UITouch*>*)touches cancelled:(BOOL)cancelled {
    for (UITouch* touch in touches) {
        if (touch == _pauseTouch) {
            BOOL openedEditor = _pauseHoldActivated;
            _pauseTouch = nil;
            _pauseHoldActivated = NO;
            if (!cancelled && !openedEditor) {
                [self pulseEscape];
            }
            continue;
        }

        if (_layoutEditing && touch == _editTouch) {
            _editTouch = nil;
            _editingControl = kNoControl;
            _editingResize = NO;
            [self saveControlLayout];
            continue;
        }

        NSValue* key = [NSValue valueWithNonretainedObject:touch];
        NSNumber* actionNumber = [_touchActions objectForKey:key];
        if (actionNumber != nil) {
            NSInteger raw = actionNumber.integerValue;
            if (raw >= 0 && raw < SERIOUSIOS_ACTION_COUNT) {
                SeriousIOS_SetVirtualAction((SeriousIOSVirtualAction)raw, false);
            }
            [_touchActions removeObjectForKey:key];
        }

        CGPoint point = [touch locationInView:self];
        if (touch == _moveTouch) {
            _moveTouch = nil;
            SeriousIOS_SetVirtualMovement(0.0f, 0.0f);
        } else if (touch == _lookTouch) {
            CGFloat distance = hypot(point.x - _lookOrigin.x,
                                     point.y - _lookOrigin.y);
            BOOL wasFiring = _lookFiring;
            BOOL wasMoved = _lookMoved;
            _lookTouch = nil;
            _lookMoved = NO;
            _lookFiring = NO;
            _lookTotalTravel = 0.0;
            _lookGeneration += 1;
            _touchRemainderX = 0.0;
            _touchRemainderY = 0.0;

            if (wasFiring) {
                SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_FIRE, false);
            } else if (!cancelled && !wasMoved
                       && distance < kLookGestureDisplacementSlop) {
                [self pulseFire];
            }
        }
    }
    [self setNeedsDisplay];
}

- (void)touchesEnded:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    [self finishTouches:touches cancelled:NO];
}

- (void)touchesCancelled:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    [self finishTouches:touches cancelled:YES];
}

- (void)handleDeviceMotion:(CMDeviceMotion*)motion error:(NSError*)error {
    if (error != nil) {
        static BOOL loggedError = NO;
        if (!loggedError) {
            loggedError = YES;
            SeriousIOS_DiagnosticsLog(
                "input", "SERIOUSSAM_IOS_GYRO: update_failed domain=%s code=%ld",
                error.domain.UTF8String, (long)error.code);
        }
        return;
    }
    if (motion == nil) {
        return;
    }

    BOOL active = _gyroEnabled
        && !_layoutEditing
        && _gameplayActive
        && !_computerActive
        && UIApplication.sharedApplication.applicationState == UIApplicationStateActive;
    if (!active) {
        _lastMotionTimestamp = motion.timestamp;
        _gyroRemainderX = 0.0;
        _gyroRemainderY = 0.0;
        return;
    }

    NSTimeInterval deltaTime = _lastMotionTimestamp > 0.0
        ? motion.timestamp - _lastMotionTimestamp : 0.0;
    _lastMotionTimestamp = motion.timestamp;
    if (deltaTime <= 0.0 || deltaTime > 0.050) {
        return;
    }

    CMRotationRate rate = motion.rotationRate;
    UIInterfaceOrientation orientation = self.window.windowScene.interfaceOrientation;
    double yawRate = 0.0;
    double pitchRate = 0.0;
    if (orientation == UIInterfaceOrientationLandscapeLeft) {
        yawRate = rate.x;
        pitchRate = -rate.y;
    } else if (orientation == UIInterfaceOrientationLandscapeRight) {
        yawRate = -rate.x;
        pitchRate = rate.y;
    } else {
        yawRate = -rate.y;
        pitchRate = -rate.x;
    }

    CGFloat nativeScale = self.contentScaleFactor > 0.0
        ? self.contentScaleFactor : 1.0;
    CGFloat backendScale = kCurrentGyroBackendDefault
        * (_gyroAimScale / kDefaultGyroAimScale);
    double pointsPerRadian = 280.0 * backendScale * nativeScale;
    double accumulatedX = yawRate * deltaTime * pointsPerRadian + _gyroRemainderX;
    double accumulatedY = pitchRate * deltaTime * pointsPerRadian + _gyroRemainderY;
    int relativeX = (int)llround(accumulatedX);
    int relativeY = (int)llround(accumulatedY);
    _gyroRemainderX = accumulatedX - relativeX;
    _gyroRemainderY = accumulatedY - relativeY;
    if (relativeX != 0 || relativeY != 0) {
        SeriousIOS_AddSDLRelativeMouseDelta(relativeX, relativeY);
    }
}

- (NSString*)symbolForControl:(NSInteger)control {
    switch (control) {
        case SeriousIOSControlUse: return @"hand.tap.fill";
        case SeriousIOSControlJump: return @"arrow.up";
        case SeriousIOSControlCrouch: return @"arrow.down.to.line";
        case SeriousIOSControlWeapon: return @"arrow.triangle.2.circlepath";
        case SeriousIOSControlPause: return _computerActive ? @"xmark" : @"pause.fill";
        case SeriousIOSControlFire: return @"scope";
        case SeriousIOSControlSkip: return @"forward.fill";
        default: return @"circle.fill";
    }
}

- (BOOL)isActionActive:(SeriousIOSVirtualAction)action {
    return [_touchActions.allValues containsObject:@((NSInteger)action)];
}

- (void)drawControl:(NSInteger)control active:(BOOL)active {
    CGPoint center = [self centerForControl:control];
    CGFloat radius = [self radiusForControl:control];
    CGContextRef context = UIGraphicsGetCurrentContext();
    CGRect circle = CircleRect(center, radius);

    CGContextSetFillColorWithColor(
        context, [UIColor colorWithWhite:1.0 alpha:active ? 0.22 : 0.075].CGColor);
    CGContextSetStrokeColorWithColor(
        context, [UIColor colorWithWhite:1.0 alpha:active ? 0.68 : 0.38].CGColor);
    CGContextSetLineWidth(context, active ? 2.4 : 1.4);
    CGContextAddEllipseInRect(context, circle);
    CGContextDrawPath(context, kCGPathFillStroke);

    CGRect inset = CGRectInset(circle, radius * 0.16, radius * 0.16);
    CGContextSetStrokeColorWithColor(
        context, [UIColor colorWithWhite:1.0 alpha:0.16].CGColor);
    CGContextSetLineWidth(context, 1.0);
    CGContextStrokeEllipseInRect(context, inset);

    UIImageSymbolConfiguration* configuration =
        [UIImageSymbolConfiguration configurationWithPointSize:radius * 0.78
                                                        weight:UIImageSymbolWeightBold];
    UIImage* symbol = [[UIImage systemImageNamed:[self symbolForControl:control]]
        imageByApplyingSymbolConfiguration:configuration];
    symbol = [symbol imageWithTintColor:
        [UIColor colorWithWhite:1.0 alpha:active ? 0.92 : 0.70]
        renderingMode:UIImageRenderingModeAlwaysOriginal];
    CGSize symbolSize = symbol.size;
    [symbol drawAtPoint:CGPointMake(center.x - symbolSize.width * 0.5,
                                    center.y - symbolSize.height * 0.5)];

    if (_layoutEditing) {
        CGFloat dash[] = {5.0, 4.0};
        CGContextSaveGState(context);
        CGContextSetLineDash(context, 0.0, dash, 2);
        CGContextSetStrokeColorWithColor(context, UIColor.whiteColor.CGColor);
        CGContextSetLineWidth(context, 2.0);
        CGContextStrokeEllipseInRect(context, CGRectInset(circle, -5.0, -5.0));
        CGContextRestoreGState(context);

        CGPoint handle = CGPointMake(center.x + radius * 0.72,
                                     center.y + radius * 0.72);
        CGContextSetFillColorWithColor(context, UIColor.whiteColor.CGColor);
        CGContextFillEllipseInRect(context, CircleRect(handle, 5.5));
        CGContextSetStrokeColorWithColor(context, UIColor.systemBlueColor.CGColor);
        CGContextSetLineWidth(context, 2.0);
        CGContextStrokeEllipseInRect(context, CircleRect(handle, 5.5));
    }
}

- (void)drawRect:(CGRect)rect {
    (void)rect;
    if (_layoutEditing) {
        [[UIColor colorWithWhite:0.0 alpha:0.34] setFill];
        UIRectFill(self.bounds);
    }

    if ((_gameplayActive && !_computerActive) || _layoutEditing) {
        [self drawControl:SeriousIOSControlUse
                   active:[self isActionActive:SERIOUSIOS_ACTION_USE]];
        [self drawControl:SeriousIOSControlJump
                   active:[self isActionActive:SERIOUSIOS_ACTION_JUMP]];
        [self drawControl:SeriousIOSControlCrouch
                   active:[self isActionActive:SERIOUSIOS_ACTION_CROUCH]];
        [self drawControl:SeriousIOSControlWeapon
                   active:[self isActionActive:SERIOUSIOS_ACTION_NEXT_WEAPON]];
        if (_fireButtonEnabled || _layoutEditing) {
            [self drawControl:SeriousIOSControlFire
                       active:[self isActionActive:SERIOUSIOS_ACTION_FIRE]
                              || _lookFiring];
        }
        [self drawControl:SeriousIOSControlSkip
                   active:[_touchActions.allValues containsObject:@(kSkipActionSentinel)]];
    }
    if (_gameplayActive || _computerActive || _layoutEditing) {
        [self drawControl:SeriousIOSControlPause active:_pauseTouch != nil];
    }
}

@end
