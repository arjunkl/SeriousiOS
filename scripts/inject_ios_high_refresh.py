#!/usr/bin/env python3
"""Turn the diagnostic host into a low-overhead adaptive high-refresh build.

The existing performance sampler remains available through LOG export, but its
live HUD and periodic main-thread percentile/log work are disabled. The display
link requests an adaptive 60-120 Hz range, with the device maximum preferred.
"""

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
        '''    _displayLink.preferredFramesPerSecond = 60;
    [self resetPerformanceProfiler];
    _performanceButton.hidden = NO;
    [self layoutPerformanceProfiler];
    [self bringSubviewToFront:_performanceButton];
    [_displayLink addToRunLoop:NSRunLoop.mainRunLoop forMode:NSRunLoopCommonModes];''',
        '''    const NSInteger screenMaximumRefreshRate =
        UIScreen.mainScreen.maximumFramesPerSecond;
    const NSInteger requestedMaximumRefreshRate = MIN(
        (NSInteger)120,
        MAX((NSInteger)60, screenMaximumRefreshRate));
    _displayLink.preferredFrameRateRange = CAFrameRateRangeMake(
        60.0f,
        (float)requestedMaximumRefreshRate,
        (float)requestedMaximumRefreshRate);
    [self resetPerformanceProfiler];
    // Keep sampling for manual LOG export, but remove the live profiler UI and
    // its periodic UIKit/percentile work from the gameplay main thread.
    _performanceButton.hidden = YES;
    _performanceButton.userInteractionEnabled = NO;
    _performanceHUD.hidden = YES;
    [_displayLink addToRunLoop:NSRunLoop.mainRunLoop forMode:NSRunLoopCommonModes];''',
        "adaptive high-refresh display link",
    )

    text = replace_once(
        text,
        '    [self updatePerformanceHUDAtTimestamp:timestamp];\n',
        '',
        "remove live profiler update",
    )

    text = replace_once(
        text,
        '''    const BOOL missed =
        (displayLink.targetTimestamp > 0.0 && endTime > displayLink.targetTimestamp + 0.0005)
        || intervalSeconds > scheduledBudget * 1.25;''',
        '''    // A miss is an observed callback cadence overrun, not merely CPU
    // completion occurring close to targetTimestamp. The old definition marked
    // many perfectly paced frames as missed.
    const BOOL missed = intervalSeconds > scheduledBudget * 1.25;''',
        "cadence-based miss classification",
    )

    text = replace_once(
        text,
        '    uint64_t _performanceOver167Ms;\n',
        '''    uint64_t _performanceOver084Ms;
    uint64_t _performanceOver100Ms;
    uint64_t _performanceOver125Ms;
    uint64_t _performanceOver167Ms;
    uint64_t _performanceDiscontinuities;
''',
        "high-refresh counters",
    )
    text = replace_once(
        text,
        '    _performanceOver167Ms = 0;\n',
        '''    _performanceOver084Ms = 0;
    _performanceOver100Ms = 0;
    _performanceOver125Ms = 0;
    _performanceOver167Ms = 0;
    _performanceDiscontinuities = 0;
''',
        "high-refresh counter reset",
    )

    text = replace_once(
        text,
        '''    const double intervalMs = intervalSeconds * 1000.0;
    double scheduledBudget = displayLink.targetTimestamp - timestamp;''',
        '''    const double intervalMs = intervalSeconds * 1000.0;
    // Share sheets, Control Center, app switching, and similar interruptions
    // are not rendered frames. Keep them out of FPS/percentile statistics while
    // reporting their count separately.
    if (intervalSeconds > 0.250) {
        _performanceDiscontinuities += 1;
        _performanceCurrentMissStreak = 0;
        return;
    }
    double scheduledBudget = displayLink.targetTimestamp - timestamp;''',
        "lifecycle discontinuity filter",
    )

    text = replace_once(
        text,
        '    if (intervalMs > 16.7) _performanceOver167Ms += 1;\n',
        '''    if (intervalMs > 8.4) _performanceOver084Ms += 1;
    if (intervalMs > 10.0) _performanceOver100Ms += 1;
    if (intervalMs > 12.5) _performanceOver125Ms += 1;
    if (intervalMs > 16.7) _performanceOver167Ms += 1;
''',
        "high-refresh interval thresholds",
    )

    text = replace_once(
        text,
        '''        "profile_started requested_fps=%ld maximum_fps=%ld drawable=%dx%d",
        (long)_displayLink.preferredFramesPerSecond,
        (long)UIScreen.mainScreen.maximumFramesPerSecond,''',
        '''        "profile_started requested_range=%.1f-%.1f preferred=%.1f maximum_fps=%ld drawable=%dx%d",
        _displayLink.preferredFrameRateRange.minimum,
        _displayLink.preferredFrameRateRange.maximum,
        _displayLink.preferredFrameRateRange.preferred,
        (long)UIScreen.mainScreen.maximumFramesPerSecond,''',
        "high-refresh profile-start log",
    )

    text = replace_once(
        text,
        '''    [report appendFormat:@"requested_fps=%ld\\n", (long)_displayLink.preferredFramesPerSecond];
    [report appendFormat:@"screen_maximum_fps=%ld\\n", (long)UIScreen.mainScreen.maximumFramesPerSecond];
    [report appendFormat:@"display_link_duration_ms=%.3f\\n", _displayLink.duration * 1000.0];''',
        '''    const CAFrameRateRange requestedRange = _displayLink.preferredFrameRateRange;
    [report appendFormat:@"requested_fps_min=%.3f\\n", requestedRange.minimum];
    [report appendFormat:@"requested_fps_max=%.3f\\n", requestedRange.maximum];
    [report appendFormat:@"requested_fps_preferred=%.3f\\n", requestedRange.preferred];
    [report appendFormat:@"screen_maximum_fps=%ld\\n", (long)UIScreen.mainScreen.maximumFramesPerSecond];
    [report appendFormat:@"display_link_duration_ms=%.3f\\n", _displayLink.duration * 1000.0];''',
        "high-refresh report range",
    )

    text = replace_once(
        text,
        '    [report appendFormat:@"interval_over_16_7_ms=%llu\\n", (unsigned long long)_performanceOver167Ms];\n',
        '''    [report appendFormat:@"interval_over_8_4_ms=%llu\\n", (unsigned long long)_performanceOver084Ms];
    [report appendFormat:@"interval_over_10_0_ms=%llu\\n", (unsigned long long)_performanceOver100Ms];
    [report appendFormat:@"interval_over_12_5_ms=%llu\\n", (unsigned long long)_performanceOver125Ms];
    [report appendFormat:@"interval_over_16_7_ms=%llu\\n", (unsigned long long)_performanceOver167Ms];
    [report appendFormat:@"lifecycle_discontinuities=%llu\\n", (unsigned long long)_performanceDiscontinuities];
''',
        "high-refresh report thresholds",
    )

    text = replace_once(
        text,
        '        SeriousIOS_DiagnosticsLog("host", "application_frame_loop_scheduled fps=60");',
        '''        SeriousIOS_DiagnosticsLog(
            "host",
            "application_frame_loop_scheduled range=60-%ld preferred=%ld maximum_supported=%ld",
            (long)MIN((NSInteger)120, MAX((NSInteger)60, UIScreen.mainScreen.maximumFramesPerSecond)),
            (long)MIN((NSInteger)120, MAX((NSInteger)60, UIScreen.mainScreen.maximumFramesPerSecond)),
            (long)UIScreen.mainScreen.maximumFramesPerSecond);''',
        "high-refresh scheduling log",
    )

    required = (
        'CAFrameRateRangeMake(',
        'requested_fps_preferred=',
        'interval_over_8_4_ms=',
        'lifecycle_discontinuities=',
        '_performanceButton.userInteractionEnabled = NO;',
        'const BOOL missed = intervalSeconds > scheduledBudget * 1.25;',
        'application_frame_loop_scheduled range=60-',
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"high-refresh transform missing token: {token}")

    forbidden = (
        '_displayLink.preferredFramesPerSecond = 60;',
        '[self updatePerformanceHUDAtTimestamp:timestamp];',
        'endTime > displayLink.targetTimestamp + 0.0005',
        'application_frame_loop_scheduled fps=60',
    )
    for token in forbidden:
        if token in text:
            raise RuntimeError(f"obsolete high-refresh behavior remains: {token}")
    return text


def self_test() -> None:
    import inject_ios_performance_profiler_driver

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
        SeriousIOS_DiagnosticsLog("host", "application_frame_loop_scheduled fps=60");
'''
    profiled = inject_ios_performance_profiler_driver.transform_text(fixture)
    transformed = transform_text(profiled)
    assert 'CAFrameRateRangeMake(' in transformed
    assert 'requested_fps_preferred=' in transformed
    assert 'interval_over_8_4_ms=' in transformed
    assert '[self updatePerformanceHUDAtTimestamp:timestamp];' not in transformed
    assert '_displayLink.preferredFramesPerSecond = 60;' not in transformed
    print('SeriousiOS adaptive high-refresh self-test passed')


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
    print(f'Enabled low-overhead adaptive high refresh in {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
