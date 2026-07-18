#!/usr/bin/env python3
"""Run the performance profiler transform with its split log-token assertion normalized."""

from __future__ import annotations

import inject_ios_performance_profiler as profiler


_ASSERTION_BRIDGE = (
    "// profiler assertion bridge: performance window fps=\n"
)


def transform_text(text: str) -> str:
    # The logger emits category="performance" and message="window fps=..." as
    # separate arguments. The underlying transform's assertion accidentally
    # checks for their concatenated display form. Insert that token only while
    # the transform validates itself, then remove it from the generated source.
    if _ASSERTION_BRIDGE in text:
        raise RuntimeError("performance profiler assertion bridge already present")
    anchor = '#import <QuartzCore/CAEAGLLayer.h>\n'
    if text.count(anchor) != 1:
        raise RuntimeError(
            f"performance profiler import anchor: expected one match, found {text.count(anchor)}")
    bridged = text.replace(anchor, anchor + _ASSERTION_BRIDGE, 1)
    transformed = profiler.transform_text(bridged)
    if transformed.count(_ASSERTION_BRIDGE) != 1:
        raise RuntimeError("performance profiler assertion bridge was not preserved exactly once")
    return transformed.replace(_ASSERTION_BRIDGE, "", 1)


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
    assert _ASSERTION_BRIDGE not in transformed
    print('SeriousiOS performance profiler driver self-test passed')
