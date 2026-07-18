#!/usr/bin/env python3
"""Inject bounded, low-overhead frame pacing diagnostics into the UIKit host."""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


PERFORMANCE_IVARS = r'''    UIButton* _performanceButton;
    UILabel* _performanceHUD;
    BOOL _performanceHUDVisible;
    CFTimeInterval _performanceSessionStart;
    CFTimeInterval _performancePreviousDisplayTimestamp;
    CFTimeInterval _performanceWindowStart;
    CFTimeInterval _performanceLastLogTimestamp;
    NSUInteger _performanceWindowFrames;
    NSUInteger _performanceWindowMisses;
    double _performanceWindowCPUTotalMs;
    uint64_t _performanceTotalFrames;
    uint64_t _performanceDeadlineMisses;
    uint64_t _performanceOver167Ms;
    uint64_t _performanceOver200Ms;
    uint64_t _performanceOver250Ms;
    uint64_t _performanceOver333Ms;
    uint64_t _performanceOver500Ms;
    NSUInteger _performanceCurrentMissStreak;
    NSUInteger _performanceMaxMissStreak;
    double _performanceTotalIntervalMs;
    double _performanceTotalCPUMs;
    double _performanceMaxIntervalMs;
    double _performanceMaxCPUMs;
    NSInteger _performanceWorstThermalState;
    NSUInteger _performanceSampleCount;
    NSUInteger _performanceWriteIndex;
    double _performanceSampleTimeMs[4096];
    double _performanceIntervalsMs[4096];
    double _performanceCPUMs[4096];
    uint8_t _performanceStates[4096];
    uint8_t _performanceMissed[4096];
    uint64_t _performanceStateFrames[4];
    uint64_t _performanceStateMisses[4];
    double _performanceStateIntervalTotalMs[4];
    double _performanceStateCPUTotalMs[4];
'''


PERFORMANCE_SETUP = r'''    _performanceButton = [UIButton buttonWithType:UIButtonTypeSystem];
    UIButtonConfiguration* performanceConfiguration =
        [UIButtonConfiguration tintedButtonConfiguration];
    performanceConfiguration.title = @"FPS";
    performanceConfiguration.baseForegroundColor = UIColor.whiteColor;
    performanceConfiguration.baseBackgroundColor =
        [UIColor colorWithWhite:0.02 alpha:0.66];
    performanceConfiguration.cornerStyle = UIButtonConfigurationCornerStyleCapsule;
    _performanceButton.configuration = performanceConfiguration;
    _performanceButton.hidden = YES;
    _performanceButton.alpha = 0.82;
    _performanceButton.accessibilityLabel = @"Toggle performance overlay";
    _performanceButton.accessibilityIdentifier = @"performance-overlay-toggle";
    [_performanceButton addTarget:self
                           action:@selector(togglePerformanceHUD)
                 forControlEvents:UIControlEventTouchUpInside];
    [self addSubview:_performanceButton];

    _performanceHUD = [[UILabel alloc] initWithFrame:CGRectZero];
    _performanceHUD.hidden = YES;
    _performanceHUD.userInteractionEnabled = NO;
    _performanceHUD.numberOfLines = 0;
    _performanceHUD.font = [UIFont monospacedDigitSystemFontOfSize:11.0
                                                            weight:UIFontWeightSemibold];
    _performanceHUD.textColor = UIColor.whiteColor;
    _performanceHUD.backgroundColor = [UIColor colorWithWhite:0.01 alpha:0.74];
    _performanceHUD.layer.cornerRadius = 8.0;
    _performanceHUD.layer.masksToBounds = YES;
    _performanceHUD.textAlignment = NSTextAlignmentLeft;
    _performanceHUD.accessibilityIdentifier = @"performance-overlay-hud";
    [self addSubview:_performanceHUD];

    [NSNotificationCenter.defaultCenter
        addObserver:self
           selector:@selector(performanceWillResignActive:)
               name:UIApplicationWillResignActiveNotification
             object:nil];
    [NSNotificationCenter.defaultCenter
        addObserver:self
           selector:@selector(performanceDidBecomeActive:)
               name:UIApplicationDidBecomeActiveNotification
             object:nil];
'''


PERFORMANCE_METHODS = r'''- (void)layoutPerformanceProfiler {
    const UIEdgeInsets safe = self.safeAreaInsets;
    const CGFloat x = safe.left + 8.0;
    const CGFloat buttonY = safe.top + 46.0;
    _performanceButton.frame = CGRectMake(x, buttonY, 56.0, 30.0);
    _performanceHUD.frame = CGRectMake(x, buttonY + 36.0, 208.0, 72.0);
}

- (NSString*)performanceThermalName:(NSProcessInfoThermalState)state {
    switch (state) {
        case NSProcessInfoThermalStateNominal: return @"nominal";
        case NSProcessInfoThermalStateFair: return @"fair";
        case NSProcessInfoThermalStateSerious: return @"serious";
        case NSProcessInfoThermalStateCritical: return @"critical";
    }
    return @"unknown";
}

- (NSString*)performanceStateName:(uint8_t)state {
    switch (state) {
        case 1: return @"gameplay";
        case 2: return @"pause";
        case 3: return @"computer";
        default: return @"menu-or-other";
    }
}

- (uint8_t)currentPerformanceState {
    if (SeriousIOS_ApplicationComputerActive()) {
        return 3;
    }
    if (SeriousIOS_ApplicationPauseMenuActive()) {
        return 2;
    }
    if (SeriousIOS_ApplicationGameplayControlsActive()) {
        return 1;
    }
    return 0;
}

- (double)performancePercentileForValues:(const double*)values
                                   count:(NSUInteger)count
                              percentile:(double)percentile {
    if (values == nullptr || count == 0) {
        return 0.0;
    }
    double* sorted = static_cast<double*>(malloc(sizeof(double) * count));
    if (sorted == nullptr) {
        return 0.0;
    }
    for (NSUInteger index = 0; index < count; ++index) {
        sorted[index] = values[index];
    }
    qsort(sorted, count, sizeof(double), SeriousIOSComparePerformanceDouble);
    const double clamped = MIN(1.0, MAX(0.0, percentile));
    const double position = clamped * (double)(count - 1);
    const NSUInteger lower = (NSUInteger)floor(position);
    const NSUInteger upper = (NSUInteger)ceil(position);
    const double fraction = position - (double)lower;
    const double result = sorted[lower] + (sorted[upper] - sorted[lower]) * fraction;
    free(sorted);
    return result;
}

- (double)recentPerformanceIntervalPercentile:(double)percentile {
    const NSUInteger available = MIN((NSUInteger)180, _performanceSampleCount);
    if (available == 0) {
        return 0.0;
    }
    double recent[180];
    const NSUInteger start =
        (_performanceWriteIndex + 4096 - available) % 4096;
    for (NSUInteger index = 0; index < available; ++index) {
        recent[index] = _performanceIntervalsMs[(start + index) % 4096];
    }
    return [self performancePercentileForValues:recent
                                          count:available
                                     percentile:percentile];
}

- (void)resetPerformanceProfiler {
    _performanceHUDVisible = NO;
    _performanceHUD.hidden = YES;
    _performanceHUD.text = @"Collecting frame data…";
    _performanceSessionStart = CACurrentMediaTime();
    _performancePreviousDisplayTimestamp = 0.0;
    _performanceWindowStart = 0.0;
    _performanceLastLogTimestamp = 0.0;
    _performanceWindowFrames = 0;
    _performanceWindowMisses = 0;
    _performanceWindowCPUTotalMs = 0.0;
    _performanceTotalFrames = 0;
    _performanceDeadlineMisses = 0;
    _performanceOver167Ms = 0;
    _performanceOver200Ms = 0;
    _performanceOver250Ms = 0;
    _performanceOver333Ms = 0;
    _performanceOver500Ms = 0;
    _performanceCurrentMissStreak = 0;
    _performanceMaxMissStreak = 0;
    _performanceTotalIntervalMs = 0.0;
    _performanceTotalCPUMs = 0.0;
    _performanceMaxIntervalMs = 0.0;
    _performanceMaxCPUMs = 0.0;
    _performanceWorstThermalState = NSProcessInfo.processInfo.thermalState;
    _performanceSampleCount = 0;
    _performanceWriteIndex = 0;
    for (NSUInteger state = 0; state < 4; ++state) {
        _performanceStateFrames[state] = 0;
        _performanceStateMisses[state] = 0;
        _performanceStateIntervalTotalMs[state] = 0.0;
        _performanceStateCPUTotalMs[state] = 0.0;
    }
    SeriousIOS_DiagnosticsLog(
        "performance",
        "profile_started requested_fps=%ld maximum_fps=%ld drawable=%dx%d",
        (long)_displayLink.preferredFramesPerSecond,
        (long)UIScreen.mainScreen.maximumFramesPerSecond,
        _drawableWidth,
        _drawableHeight);
}

- (void)togglePerformanceHUD {
    _performanceHUDVisible = !_performanceHUDVisible;
    _performanceHUD.hidden = !_performanceHUDVisible;
    if (_performanceHUDVisible) {
        [self bringSubviewToFront:_performanceHUD];
    }
    [self bringSubviewToFront:_performanceButton];
    SeriousIOS_DiagnosticsLog(
        "performance",
        "hud_toggled visible=%d",
        _performanceHUDVisible ? 1 : 0);
}

- (void)performanceWillResignActive:(NSNotification*)notification {
    (void)notification;
    _performancePreviousDisplayTimestamp = 0.0;
    _performanceWindowStart = 0.0;
    _performanceWindowFrames = 0;
    _performanceWindowMisses = 0;
    _performanceWindowCPUTotalMs = 0.0;
}

- (void)performanceDidBecomeActive:(NSNotification*)notification {
    (void)notification;
    _performancePreviousDisplayTimestamp = 0.0;
    _performanceWindowStart = 0.0;
    _performanceWindowFrames = 0;
    _performanceWindowMisses = 0;
    _performanceWindowCPUTotalMs = 0.0;
}

- (void)updatePerformanceHUDAtTimestamp:(CFTimeInterval)timestamp {
    if (_performanceWindowStart <= 0.0) {
        _performanceWindowStart = timestamp;
        return;
    }
    const double elapsed = timestamp - _performanceWindowStart;
    if (elapsed < 1.0) {
        return;
    }

    const double fps = elapsed > 0.0
        ? (double)_performanceWindowFrames / elapsed
        : 0.0;
    const double averageCPU = _performanceWindowFrames > 0
        ? _performanceWindowCPUTotalMs / (double)_performanceWindowFrames
        : 0.0;
    const double missedPercent = _performanceWindowFrames > 0
        ? 100.0 * (double)_performanceWindowMisses / (double)_performanceWindowFrames
        : 0.0;
    const double p95Interval = [self recentPerformanceIntervalPercentile:0.95];
    const NSProcessInfoThermalState thermalState = NSProcessInfo.processInfo.thermalState;
    _performanceWorstThermalState = MAX(_performanceWorstThermalState, (NSInteger)thermalState);
    const uint8_t state = [self currentPerformanceState];

    _performanceHUD.text = [NSString stringWithFormat:
        @"  FPS %5.1f   P95 %5.1f ms\n  CPU %5.1f ms   Miss %4.1f%%\n  %@   thermal %@",
        fps,
        p95Interval,
        averageCPU,
        missedPercent,
        [self performanceStateName:state],
        [self performanceThermalName:thermalState]];

    if (timestamp - _performanceLastLogTimestamp >= 5.0) {
        _performanceLastLogTimestamp = timestamp;
        SeriousIOS_DiagnosticsLog(
            "performance",
            "window fps=%.2f p95_interval_ms=%.3f avg_cpu_ms=%.3f missed_pct=%.2f state=%s thermal=%s total_frames=%llu",
            fps,
            p95Interval,
            averageCPU,
            missedPercent,
            [self performanceStateName:state].UTF8String,
            [self performanceThermalName:thermalState].UTF8String,
            (unsigned long long)_performanceTotalFrames);
    }

    _performanceWindowStart = timestamp;
    _performanceWindowFrames = 0;
    _performanceWindowMisses = 0;
    _performanceWindowCPUTotalMs = 0.0;
    [self bringSubviewToFront:_performanceButton];
    if (_performanceHUDVisible) {
        [self bringSubviewToFront:_performanceHUD];
    }
}

- (void)recordPerformanceFrame:(CADisplayLink*)displayLink
                     startTime:(CFTimeInterval)startTime
                       endTime:(CFTimeInterval)endTime
                      rendered:(BOOL)rendered {
    const CFTimeInterval timestamp = displayLink.timestamp;
    const double cpuMs = MAX(0.0, (endTime - startTime) * 1000.0);
    if (_performancePreviousDisplayTimestamp <= 0.0) {
        _performancePreviousDisplayTimestamp = timestamp;
        _performanceWindowStart = timestamp;
        return;
    }

    const double intervalSeconds = timestamp - _performancePreviousDisplayTimestamp;
    _performancePreviousDisplayTimestamp = timestamp;
    if (intervalSeconds <= 0.0) {
        return;
    }
    const double intervalMs = intervalSeconds * 1000.0;
    double scheduledBudget = displayLink.targetTimestamp - timestamp;
    if (scheduledBudget <= 0.0) {
        scheduledBudget = 1.0 / 60.0;
    }
    const BOOL missed =
        (displayLink.targetTimestamp > 0.0 && endTime > displayLink.targetTimestamp + 0.0005)
        || intervalSeconds > scheduledBudget * 1.25;
    const uint8_t state = [self currentPerformanceState];

    const NSUInteger slot = _performanceWriteIndex;
    _performanceSampleTimeMs[slot] = MAX(0.0, (endTime - _performanceSessionStart) * 1000.0);
    _performanceIntervalsMs[slot] = intervalMs;
    _performanceCPUMs[slot] = cpuMs;
    _performanceStates[slot] = state;
    _performanceMissed[slot] = missed ? 1 : 0;
    _performanceWriteIndex = (slot + 1) % 4096;
    _performanceSampleCount = MIN((NSUInteger)4096, _performanceSampleCount + 1);

    _performanceTotalFrames += 1;
    _performanceTotalIntervalMs += intervalMs;
    _performanceTotalCPUMs += cpuMs;
    _performanceMaxIntervalMs = MAX(_performanceMaxIntervalMs, intervalMs);
    _performanceMaxCPUMs = MAX(_performanceMaxCPUMs, cpuMs);
    _performanceStateFrames[state] += 1;
    _performanceStateIntervalTotalMs[state] += intervalMs;
    _performanceStateCPUTotalMs[state] += cpuMs;

    if (intervalMs > 16.7) _performanceOver167Ms += 1;
    if (intervalMs > 20.0) _performanceOver200Ms += 1;
    if (intervalMs > 25.0) _performanceOver250Ms += 1;
    if (intervalMs > 33.3) _performanceOver333Ms += 1;
    if (intervalMs > 50.0) _performanceOver500Ms += 1;

    if (missed) {
        _performanceDeadlineMisses += 1;
        _performanceStateMisses[state] += 1;
        _performanceCurrentMissStreak += 1;
        _performanceMaxMissStreak = MAX(
            _performanceMaxMissStreak,
            _performanceCurrentMissStreak);
    } else {
        _performanceCurrentMissStreak = 0;
    }

    _performanceWindowFrames += 1;
    _performanceWindowCPUTotalMs += cpuMs;
    if (missed) {
        _performanceWindowMisses += 1;
    }
    if (!rendered) {
        SeriousIOS_DiagnosticsLog(
            "performance",
            "frame_loop_render_failed interval_ms=%.3f cpu_ms=%.3f",
            intervalMs,
            cpuMs);
    }
    [self updatePerformanceHUDAtTimestamp:timestamp];
}

- (NSString*)performanceReportPath {
    const char* userPath = SeriousIOS_GetUserPath();
    NSString* root = userPath != nullptr && *userPath != '\0'
        ? [NSString stringWithUTF8String:userPath]
        : NSTemporaryDirectory();
    if (root.length == 0) {
        root = NSTemporaryDirectory();
    }
    return [root stringByAppendingPathComponent:@"SeriousIOS-performance-report.txt"];
}

- (void)writePerformanceReport {
    const NSUInteger count = _performanceSampleCount;
    const double p50Interval = [self performancePercentileForValues:_performanceIntervalsMs
                                                              count:count
                                                         percentile:0.50];
    const double p95Interval = [self performancePercentileForValues:_performanceIntervalsMs
                                                              count:count
                                                         percentile:0.95];
    const double p99Interval = [self performancePercentileForValues:_performanceIntervalsMs
                                                              count:count
                                                         percentile:0.99];
    const double p50CPU = [self performancePercentileForValues:_performanceCPUMs
                                                         count:count
                                                    percentile:0.50];
    const double p95CPU = [self performancePercentileForValues:_performanceCPUMs
                                                         count:count
                                                    percentile:0.95];
    const double p99CPU = [self performancePercentileForValues:_performanceCPUMs
                                                         count:count
                                                    percentile:0.99];
    const double effectiveFPS = _performanceTotalIntervalMs > 0.0
        ? 1000.0 * (double)_performanceTotalFrames / _performanceTotalIntervalMs
        : 0.0;
    const double averageCPU = _performanceTotalFrames > 0
        ? _performanceTotalCPUMs / (double)_performanceTotalFrames
        : 0.0;
    const double missedPercent = _performanceTotalFrames > 0
        ? 100.0 * (double)_performanceDeadlineMisses / (double)_performanceTotalFrames
        : 0.0;
    const NSProcessInfoThermalState currentThermal = NSProcessInfo.processInfo.thermalState;
    _performanceWorstThermalState = MAX(_performanceWorstThermalState, (NSInteger)currentThermal);

    NSMutableString* report = [NSMutableString string];
    NSString* generatedAt = [[NSISO8601DateFormatter new] stringFromDate:[NSDate date]];
    [report appendFormat:@"SeriousiOS performance profile\n"];
    [report appendFormat:@"generated_at=%@\n", generatedAt];
    [report appendFormat:@"encounter=%@\n", kEncounterName];
    [report appendFormat:@"drawable=%dx%d\n", _drawableWidth, _drawableHeight];
    [report appendFormat:@"native_scale=%.3f\n", self.contentScaleFactor];
    [report appendFormat:@"requested_fps=%ld\n", (long)_displayLink.preferredFramesPerSecond];
    [report appendFormat:@"screen_maximum_fps=%ld\n", (long)UIScreen.mainScreen.maximumFramesPerSecond];
    [report appendFormat:@"display_link_duration_ms=%.3f\n", _displayLink.duration * 1000.0];
    [report appendFormat:@"session_seconds=%.3f\n", MAX(0.0, CACurrentMediaTime() - _performanceSessionStart)];
    [report appendFormat:@"total_profiled_frames=%llu\n", (unsigned long long)_performanceTotalFrames];
    [report appendFormat:@"percentile_ring_samples=%lu\n", (unsigned long)count];
    [report appendFormat:@"effective_fps=%.3f\n", effectiveFPS];
    [report appendFormat:@"interval_avg_ms=%.3f\n", _performanceTotalFrames > 0 ? _performanceTotalIntervalMs / (double)_performanceTotalFrames : 0.0];
    [report appendFormat:@"interval_p50_ms=%.3f\n", p50Interval];
    [report appendFormat:@"interval_p95_ms=%.3f\n", p95Interval];
    [report appendFormat:@"interval_p99_ms=%.3f\n", p99Interval];
    [report appendFormat:@"interval_max_ms=%.3f\n", _performanceMaxIntervalMs];
    [report appendFormat:@"cpu_avg_ms=%.3f\n", averageCPU];
    [report appendFormat:@"cpu_p50_ms=%.3f\n", p50CPU];
    [report appendFormat:@"cpu_p95_ms=%.3f\n", p95CPU];
    [report appendFormat:@"cpu_p99_ms=%.3f\n", p99CPU];
    [report appendFormat:@"cpu_max_ms=%.3f\n", _performanceMaxCPUMs];
    [report appendFormat:@"deadline_misses=%llu\n", (unsigned long long)_performanceDeadlineMisses];
    [report appendFormat:@"deadline_miss_percent=%.3f\n", missedPercent];
    [report appendFormat:@"maximum_miss_streak=%lu\n", (unsigned long)_performanceMaxMissStreak];
    [report appendFormat:@"interval_over_16_7_ms=%llu\n", (unsigned long long)_performanceOver167Ms];
    [report appendFormat:@"interval_over_20_ms=%llu\n", (unsigned long long)_performanceOver200Ms];
    [report appendFormat:@"interval_over_25_ms=%llu\n", (unsigned long long)_performanceOver250Ms];
    [report appendFormat:@"interval_over_33_3_ms=%llu\n", (unsigned long long)_performanceOver333Ms];
    [report appendFormat:@"interval_over_50_ms=%llu\n", (unsigned long long)_performanceOver500Ms];
    [report appendFormat:@"thermal_current=%@\n", [self performanceThermalName:currentThermal]];
    [report appendFormat:@"thermal_worst=%@\n", [self performanceThermalName:(NSProcessInfoThermalState)_performanceWorstThermalState]];

    [report appendString:@"\n[state_summaries]\n"];
    for (uint8_t state = 0; state < 4; ++state) {
        const uint64_t frames = _performanceStateFrames[state];
        const double stateFPS = _performanceStateIntervalTotalMs[state] > 0.0
            ? 1000.0 * (double)frames / _performanceStateIntervalTotalMs[state]
            : 0.0;
        const double stateCPU = frames > 0
            ? _performanceStateCPUTotalMs[state] / (double)frames
            : 0.0;
        const double stateMiss = frames > 0
            ? 100.0 * (double)_performanceStateMisses[state] / (double)frames
            : 0.0;
        [report appendFormat:
            @"state=%@ frames=%llu effective_fps=%.3f avg_cpu_ms=%.3f misses=%llu miss_percent=%.3f\n",
            [self performanceStateName:state],
            (unsigned long long)frames,
            stateFPS,
            stateCPU,
            (unsigned long long)_performanceStateMisses[state],
            stateMiss];
    }

    [report appendString:@"\n[recent_frame_samples]\n"];
    [report appendString:@"session_ms,interval_ms,cpu_ms,missed,state\n"];
    const NSUInteger start = count == 4096 ? _performanceWriteIndex : 0;
    for (NSUInteger item = 0; item < count; ++item) {
        const NSUInteger index = (start + item) % 4096;
        [report appendFormat:@"%.3f,%.3f,%.3f,%u,%@\n",
            _performanceSampleTimeMs[index],
            _performanceIntervalsMs[index],
            _performanceCPUMs[index],
            (unsigned)_performanceMissed[index],
            [self performanceStateName:_performanceStates[index]]];
    }

    NSError* error = nil;
    const NSString* path = [self performanceReportPath];
    if (![report writeToFile:path
                  atomically:YES
                    encoding:NSUTF8StringEncoding
                       error:&error]) {
        SeriousIOS_DiagnosticsLog(
            "performance",
            "report_write_failed domain=%s code=%ld",
            error.domain.UTF8String,
            (long)error.code);
        return;
    }
    SeriousIOS_DiagnosticsLog(
        "performance",
        "report_written frames=%llu effective_fps=%.3f p95_interval_ms=%.3f p99_interval_ms=%.3f p95_cpu_ms=%.3f missed_pct=%.3f bytes=%lu",
        (unsigned long long)_performanceTotalFrames,
        effectiveFPS,
        p95Interval,
        p99Interval,
        p95CPU,
        missedPercent,
        (unsigned long)[report lengthOfBytesUsingEncoding:NSUTF8StringEncoding]);
}
'''


def transform_text(text: str) -> str:
    text = replace_once(
        text,
        '#import <QuartzCore/CAEAGLLayer.h>\n',
        '#import <QuartzCore/CAEAGLLayer.h>\n#include <math.h>\n#include <stdlib.h>\n',
        "profiler C library imports",
    )
    text = replace_once(
        text,
        'static int SeriousIOSMakeCurrent(void* context);\n',
        '''static int SeriousIOSMakeCurrent(void* context);
static int SeriousIOSComparePerformanceDouble(const void* lhs, const void* rhs) {
    const double left = *static_cast<const double*>(lhs);
    const double right = *static_cast<const double*>(rhs);
    return (left > right) - (left < right);
}
''',
        "performance comparator",
    )
    text = replace_once(
        text,
        '    UIButton* _diagnosticsButton;\n',
        '    UIButton* _diagnosticsButton;\n' + PERFORMANCE_IVARS,
        "performance ivars",
    )
    text = replace_once(
        text,
        '    [self addSubview:_diagnosticsButton];\n',
        '    [self addSubview:_diagnosticsButton];\n\n' + PERFORMANCE_SETUP,
        "performance UI setup",
    )
    text = replace_once(
        text,
        '    [self layoutReturnToGameButton];\n',
        '    [self layoutReturnToGameButton];\n    [self layoutPerformanceProfiler];\n',
        "performance UI layout",
    )
    text = replace_once(
        text,
        '- (void)dealloc {\n',
        '''- (void)dealloc {
    [NSNotificationCenter.defaultCenter removeObserver:self];
''',
        "performance observer cleanup",
    )
    text = replace_once(
        text,
        '- (void)layoutReturnToGameButton {',
        PERFORMANCE_METHODS + '\n- (void)layoutReturnToGameButton {',
        "performance methods",
    )
    text = replace_once(
        text,
        '''    _renderedFirstApplicationFrame = NO;
    _displayLink = [CADisplayLink displayLinkWithTarget:self''',
        '''    _renderedFirstApplicationFrame = NO;
    _displayLink = [CADisplayLink displayLinkWithTarget:self''',
        "display link creation anchor",
    )
    text = replace_once(
        text,
        '''    _displayLink.preferredFramesPerSecond = 60;
    [_displayLink addToRunLoop:NSRunLoop.mainRunLoop forMode:NSRunLoopCommonModes];''',
        '''    _displayLink.preferredFramesPerSecond = 60;
    [self resetPerformanceProfiler];
    _performanceButton.hidden = NO;
    [self layoutPerformanceProfiler];
    [self bringSubviewToFront:_performanceButton];
    [_displayLink addToRunLoop:NSRunLoop.mainRunLoop forMode:NSRunLoopCommonModes];''',
        "performance profiler startup",
    )
    text = replace_once(
        text,
        '''    SeriousIOS_ApplicationProcessInputEvents();
    const bool rendered = SeriousIOS_ApplicationFrame();
    [self updateGameplayControlVisibility];''',
        '''    const CFTimeInterval performanceFrameStart = CACurrentMediaTime();
    SeriousIOS_ApplicationProcessInputEvents();
    const bool rendered = SeriousIOS_ApplicationFrame();
    [self updateGameplayControlVisibility];
    const CFTimeInterval performanceFrameEnd = CACurrentMediaTime();
    [self recordPerformanceFrame:displayLink
                       startTime:performanceFrameStart
                         endTime:performanceFrameEnd
                        rendered:rendered ? YES : NO];''',
        "frame timing",
    )
    text = replace_once(
        text,
        '''    SeriousIOS_DiagnosticsWriteSummary("manual-export");
    SeriousIOS_DiagnosticsFlush();''',
        '''    [self writePerformanceReport];
    SeriousIOS_DiagnosticsWriteSummary("manual-export");
    SeriousIOS_DiagnosticsFlush();''',
        "performance report generation",
    )
    text = replace_once(
        text,
        '''    appendSection(@"APPLICATION CHECKPOINT", userRoot == nil
        ? nil
        : [userRoot stringByAppendingPathComponent:@"application-runtime-checkpoint.txt"]);''',
        '''    appendSection(@"APPLICATION CHECKPOINT", userRoot == nil
        ? nil
        : [userRoot stringByAppendingPathComponent:@"application-runtime-checkpoint.txt"]);
    appendSection(@"PERFORMANCE PROFILE", userRoot == nil
        ? nil
        : [userRoot stringByAppendingPathComponent:@"SeriousIOS-performance-report.txt"]);''',
        "performance report export section",
    )

    required = (
        'performance-overlay-toggle',
        'SeriousIOS-performance-report.txt',
        'PERFORMANCE PROFILE',
        'recordPerformanceFrame:displayLink',
        'displayLink.targetTimestamp',
        'interval_p95_ms',
        'cpu_p95_ms',
        'thermal_worst',
        'recent_frame_samples',
        'performance window fps=',
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"performance profiler transform missing token: {token}")
    if text.count('[self writePerformanceReport];') != 1:
        raise RuntimeError("performance report must be generated exactly once per export")
    return text


def self_test() -> None:
    fixture = '''#import <QuartzCore/CAEAGLLayer.h>
static int SeriousIOSMakeCurrent(void* context);
    UIButton* _diagnosticsButton;
    [self addSubview:_diagnosticsButton];
- (void)dealloc {
- (void)layoutSubviews {
    [self layoutReturnToGameButton];
}
- (void)layoutReturnToGameButton {
}
- (void)startApplicationFrameLoop {
    _renderedFirstApplicationFrame = NO;
    _displayLink = [CADisplayLink displayLinkWithTarget:self
                                               selector:@selector(applicationFrame:)];
    _displayLink.preferredFramesPerSecond = 60;
    [_displayLink addToRunLoop:NSRunLoop.mainRunLoop forMode:NSRunLoopCommonModes];
}
- (void)applicationFrame:(CADisplayLink*)displayLink {
    SeriousIOS_ApplicationProcessInputEvents();
    const bool rendered = SeriousIOS_ApplicationFrame();
    [self updateGameplayControlVisibility];
}
- (void)exportDiagnostics {
    SeriousIOS_DiagnosticsWriteSummary("manual-export");
    SeriousIOS_DiagnosticsFlush();
    NSString* userRoot = nil;
    appendSection(@"APPLICATION CHECKPOINT", userRoot == nil
        ? nil
        : [userRoot stringByAppendingPathComponent:@"application-runtime-checkpoint.txt"]);
}
'''
    transformed = transform_text(fixture)
    assert 'performance-overlay-toggle' in transformed
    assert 'SeriousIOS-performance-report.txt' in transformed
    assert 'PERFORMANCE PROFILE' in transformed
    assert 'recordPerformanceFrame:displayLink' in transformed
    assert transformed.count('[self writePerformanceReport];') == 1
    print('SeriousiOS performance profiler self-test passed')


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
    print(f'Injected bounded performance profiler into {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
