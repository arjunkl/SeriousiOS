#!/usr/bin/env python3
"""Make licensed-data startup manual and use the Serious Engine ES1 bridge."""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def replace_count(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} matches, found {count}")
    return text.replace(old, new)


def transform_opengles1(text: str) -> str:
    text = replace_once(
        text,
        '#import <OpenGLES/ES2/gl.h>\n',
        '#import <OpenGLES/ES1/gl.h>\n#import <OpenGLES/ES1/glext.h>\n',
        "OpenGL ES import",
    )
    text = replace_once(
        text,
        '[[EAGLContext alloc] initWithAPI:kEAGLRenderingAPIOpenGLES2]',
        '[[EAGLContext alloc] initWithAPI:kEAGLRenderingAPIOpenGLES1]',
        "OpenGL ES context API",
    )
    text = replace_once(
        text,
        '@"Unable to create an OpenGL ES 2 context"',
        '@"Unable to create an OpenGL ES 1.1 context"',
        "OpenGL ES assertion",
    )

    replacements = (
        ("glGenFramebuffers(", "glGenFramebuffersOES(", 1),
        ("glBindFramebuffer(", "glBindFramebufferOES(", 1),
        ("glGenRenderbuffers(", "glGenRenderbuffersOES(", 2),
        ("glBindRenderbuffer(", "glBindRenderbufferOES(", 3),
        ("glGetRenderbufferParameteriv(", "glGetRenderbufferParameterivOES(", 2),
        ("glFramebufferRenderbuffer(", "glFramebufferRenderbufferOES(", 2),
        ("glRenderbufferStorage(", "glRenderbufferStorageOES(", 1),
        ("glCheckFramebufferStatus(", "glCheckFramebufferStatusOES(", 1),
        ("glDeleteRenderbuffers(", "glDeleteRenderbuffersOES(", 2),
        ("glDeleteFramebuffers(", "glDeleteFramebuffersOES(", 1),
        ("GL_FRAMEBUFFER_COMPLETE", "GL_FRAMEBUFFER_COMPLETE_OES", 1),
        ("GL_COLOR_ATTACHMENT0", "GL_COLOR_ATTACHMENT0_OES", 1),
        ("GL_DEPTH_ATTACHMENT", "GL_DEPTH_ATTACHMENT_OES", 1),
        ("GL_DEPTH_COMPONENT16", "GL_DEPTH_COMPONENT16_OES", 1),
        ("GL_RENDERBUFFER_WIDTH", "GL_RENDERBUFFER_WIDTH_OES", 1),
        ("GL_RENDERBUFFER_HEIGHT", "GL_RENDERBUFFER_HEIGHT_OES", 1),
        ("GL_FRAMEBUFFER", "GL_FRAMEBUFFER_OES", 4),
        ("GL_RENDERBUFFER", "GL_RENDERBUFFER_OES", 10),
    )
    for old, new, expected in replacements:
        text = replace_count(text, old, new, expected, f"ES1 replacement {old}")

    text = replace_once(
        text,
        '''    NSAssert(
        glCheckFramebufferStatusOES(GL_FRAMEBUFFER_OES) == GL_FRAMEBUFFER_COMPLETE_OES,
        @"SeriousiOS EAGL framebuffer is incomplete");

    glViewport(0, 0, _drawableWidth, _drawableHeight);''',
        '''    NSAssert(
        glCheckFramebufferStatusOES(GL_FRAMEBUFFER_OES) == GL_FRAMEBUFFER_COMPLETE_OES,
        @"SeriousiOS EAGL framebuffer is incomplete");

    if (!SeriousIOS_ValidateOpenGLCompatibility()) {
        _startupScheduled = YES;
        _startupLabel.textColor = UIColor.systemRedColor;
        _startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\\nOpenGL ES 1.1 compatibility validation failed\\n%s",
            kEncounterName,
            SeriousIOS_GetOpenGLCompatibilityError()];
        return;
    }

    glViewport(0, 0, _drawableWidth, _drawableHeight);''',
        "OpenGL ES compatibility validation",
    )
    return text


def transform(path: Path) -> None:
    text = transform_opengles1(path.read_text(encoding="utf-8"))

    text = replace_once(
        text,
        '''    UILabel* _startupLabel;
    UIButton* _importButton;
    CADisplayLink* _displayLink;''',
        '''    UILabel* _startupLabel;
    UIButton* _launchButton;
    UIButton* _importButton;
    CADisplayLink* _displayLink;''',
        "diagnostic launch button ivar",
    )

    text = replace_once(
        text,
        '''    _importButton = [UIButton buttonWithType:UIButtonTypeSystem];''',
        '''    _launchButton = [UIButton buttonWithType:UIButtonTypeSystem];
    _launchButton.translatesAutoresizingMaskIntoConstraints = NO;
    _launchButton.hidden = YES;
    _launchButton.titleLabel.font = [UIFont systemFontOfSize:16.0 weight:UIFontWeightSemibold];
    _launchButton.configuration = [UIButtonConfiguration filledButtonConfiguration];
    [_launchButton setTitle:@"Start diagnostic launch" forState:UIControlStateNormal];
    [_launchButton addTarget:self
                      action:@selector(beginApplicationDiagnosticLaunch)
            forControlEvents:UIControlEventTouchUpInside];
    [self addSubview:_launchButton];

    _importButton = [UIButton buttonWithType:UIButtonTypeSystem];''',
        "diagnostic launch button construction",
    )

    text = replace_once(
        text,
        '''        [_importButton.centerXAnchor constraintEqualToAnchor:self.centerXAnchor],
        [_importButton.topAnchor constraintEqualToAnchor:_startupLabel.bottomAnchor constant:20.0],''',
        '''        [_launchButton.centerXAnchor constraintEqualToAnchor:self.centerXAnchor],
        [_launchButton.topAnchor constraintEqualToAnchor:_startupLabel.bottomAnchor constant:20.0],
        [_importButton.centerXAnchor constraintEqualToAnchor:self.centerXAnchor],
        [_importButton.topAnchor constraintEqualToAnchor:_launchButton.bottomAnchor constant:12.0],''',
        "diagnostic launch button constraints",
    )

    old_schedule = '''- (void)scheduleEngineStartupIfNeeded {
    if (_startupScheduled || _drawableWidth <= 0 || _drawableHeight <= 0) {
        return;
    }
    _startupScheduled = YES;

    const BOOL hasValidatedGameData = [self requiredSentinelExists];
    _startupLabel.text = [NSString stringWithFormat:
        hasValidatedGameData
            ? @"SeriousiOS %@\\nStarting full application with imported data…"
            : @"SeriousiOS %@\\nStarting core engine without game data…",
        kEncounterName];

    dispatch_async(dispatch_get_main_queue(), ^{
        if (hasValidatedGameData) {
            const bool started = SeriousIOS_ApplicationInitialize();
            if (started) {
                self->_startupLabel.textColor = UIColor.systemGreenColor;
                self->_startupLabel.text = [NSString stringWithFormat:
                    @"SeriousiOS %@\\nApplication initialized\\nStarting UIKit-driven frame loop…",
                    kEncounterName];
                self->_importButton.hidden = YES;
                [self startApplicationFrameLoop];
                NSLog(@"SeriousiOS application lifecycle initialized for %@", kEncounterName);
                return;
            }

            NSString* errorText = stringFromCString(
                SeriousIOS_ApplicationGetError(),
                @"Unknown application startup failure");
            self->_startupLabel.textColor = UIColor.systemRedColor;
            self->_startupLabel.text = [NSString stringWithFormat:
                @"SeriousiOS %@\\nApplication startup failed\\n%@",
                kEncounterName,
                errorText];
            self->_importButton.hidden = NO;
            [self->_importButton setTitle:@"Re-import original .gro files"
                                 forState:UIControlStateNormal];
            NSLog(@"SeriousiOS application startup failed for %@: %@", kEncounterName, errorText);
            return;
        }

        const bool started = SeriousIOS_StartCoreEngine();
        const SeriousIOSEngineState state = SeriousIOS_GetEngineState();
        if (started && state == SeriousIOSEngineStateCoreInitialized) {
            self->_startupLabel.textColor = UIColor.systemGreenColor;
            self->_startupLabel.text = [NSString stringWithFormat:
                @"SeriousiOS %@\\nCore engine initialized\\nWaiting for original game data import",
                kEncounterName];
            self->_importButton.hidden = NO;
            [self refreshImportedGameDataStatus];
            NSLog(@"SeriousiOS core engine checkpoint passed for %@", kEncounterName);
            return;
        }

        NSString* errorText = stringFromCString(
            SeriousIOS_GetEngineStartupError(),
            @"Unknown core engine startup failure");
        self->_startupLabel.textColor = UIColor.systemRedColor;
        self->_startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\\nCore engine startup failed\\n%@",
            kEncounterName,
            errorText];
        self->_importButton.hidden = YES;
        NSLog(@"SeriousiOS core engine startup failed for %@: %@", kEncounterName, errorText);
    });
}
'''

    new_schedule = '''- (void)scheduleEngineStartupIfNeeded {
    if (_startupScheduled || _drawableWidth <= 0 || _drawableHeight <= 0) {
        return;
    }
    _startupScheduled = YES;

    const BOOL hasValidatedGameData = [self requiredSentinelExists];
    if (hasValidatedGameData) {
        NSString* previousCheckpoint = [self previousApplicationCheckpointSummary];
        _startupLabel.textColor = UIColor.whiteColor;
        _startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\\nOriginal game data found\\n%@\\n\\nTap Start diagnostic launch",
            kEncounterName,
            previousCheckpoint];
        _launchButton.hidden = NO;
        _importButton.hidden = NO;
        [_importButton setTitle:@"Re-import original .gro files" forState:UIControlStateNormal];
        return;
    }

    _startupLabel.text = [NSString stringWithFormat:
        @"SeriousiOS %@\\nStarting core engine without game data…",
        kEncounterName];

    dispatch_async(dispatch_get_main_queue(), ^{
        const bool started = SeriousIOS_StartCoreEngine();
        const SeriousIOSEngineState state = SeriousIOS_GetEngineState();
        if (started && state == SeriousIOSEngineStateCoreInitialized) {
            self->_startupLabel.textColor = UIColor.systemGreenColor;
            self->_startupLabel.text = [NSString stringWithFormat:
                @"SeriousiOS %@\\nCore engine initialized\\nWaiting for original game data import",
                kEncounterName];
            self->_importButton.hidden = NO;
            [self refreshImportedGameDataStatus];
            NSLog(@"SeriousiOS core engine checkpoint passed for %@", kEncounterName);
            return;
        }

        NSString* errorText = stringFromCString(
            SeriousIOS_GetEngineStartupError(),
            @"Unknown core engine startup failure");
        self->_startupLabel.textColor = UIColor.systemRedColor;
        self->_startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\\nCore engine startup failed\\n%@",
            kEncounterName,
            errorText];
        self->_importButton.hidden = YES;
        NSLog(@"SeriousiOS core engine startup failed for %@: %@", kEncounterName, errorText);
    });
}

- (NSString*)previousApplicationCheckpointSummary {
    const char* userPath = SeriousIOS_GetUserPath();
    if (userPath == nullptr || *userPath == '\\0') {
        return @"No previous startup checkpoint";
    }

    NSString* directory = [NSString stringWithUTF8String:userPath];
    NSString* checkpointPath = [directory
        stringByAppendingPathComponent:@"application-runtime-checkpoint.txt"];
    NSError* error = nil;
    NSString* checkpoint = [NSString stringWithContentsOfFile:checkpointPath
                                                     encoding:NSUTF8StringEncoding
                                                        error:&error];
    if (checkpoint.length == 0) {
        return @"No previous startup checkpoint";
    }
    return [NSString stringWithFormat:@"Previous checkpoint:\\n%@", checkpoint];
}

- (void)beginApplicationDiagnosticLaunch {
    _launchButton.enabled = NO;
    _importButton.enabled = NO;
    _startupLabel.textColor = UIColor.whiteColor;
    _startupLabel.text = [NSString stringWithFormat:
        @"SeriousiOS %@\\nArming staged startup diagnostics…",
        kEncounterName];

    dispatch_after(
        dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.75 * NSEC_PER_SEC)),
        dispatch_get_main_queue(), ^{
            [self runApplicationDiagnosticLaunch];
        });
}

- (void)runApplicationDiagnosticLaunch {
    _startupLabel.text = [NSString stringWithFormat:
        @"SeriousiOS %@\\nStarting full application\\nEvery phase is being persisted…",
        kEncounterName];

    const bool started = SeriousIOS_ApplicationInitialize();
    if (started) {
        _startupLabel.textColor = UIColor.systemGreenColor;
        _startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\\nApplication initialized\\nStarting UIKit-driven frame loop…",
            kEncounterName];
        _launchButton.hidden = YES;
        _importButton.hidden = YES;
        [self startApplicationFrameLoop];
        NSLog(@"SeriousiOS application lifecycle initialized for %@", kEncounterName);
        return;
    }

    NSString* errorText = stringFromCString(
        SeriousIOS_ApplicationGetError(),
        @"Unknown application startup failure");
    _startupLabel.textColor = UIColor.systemRedColor;
    _startupLabel.text = [NSString stringWithFormat:
        @"SeriousiOS %@\\nApplication startup failed\\nStage: %s\\n%@\\n\\nClose and reopen the app before retrying",
        kEncounterName,
        SeriousIOS_ApplicationGetStage(),
        errorText];
    _launchButton.enabled = NO;
    _launchButton.hidden = YES;
    _importButton.enabled = NO;
    _importButton.hidden = YES;
    NSLog(@"SeriousiOS application startup failed for %@ at %s: %@",
        kEncounterName,
        SeriousIOS_ApplicationGetStage(),
        errorText);
}
'''

    text = replace_once(
        text,
        old_schedule,
        new_schedule,
        "manual diagnostic startup method",
    )

    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("host_source", type=Path)
    args = parser.parse_args()
    source = args.host_source.resolve()
    if not source.is_file():
        raise SystemExit(f"host source does not exist: {source}")
    transform(source)
    print(f"Applied OpenGL ES 1.1 and crash-loop-safe diagnostics to {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
