#!/usr/bin/env python3
"""Build a crash-loop-safe UIKit host on an OpenGL ES 1.1 surface."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def replace_exact(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} matches, found {count}")
    return text.replace(old, new)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    return replace_exact(text, old, new, 1, label)


def replace_token(text: str, old: str, new: str, expected: int) -> str:
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])"
    )
    count = len(pattern.findall(text))
    if count != expected:
        raise RuntimeError(
            f"ES1 token {old}: expected {expected} standalone matches, found {count}"
        )
    return pattern.sub(new, text)


def replace_method(
    text: str,
    signature: str,
    following_signature: str,
    replacement: str,
) -> str:
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"method signature not found: {signature}")
    following = text.find(following_signature, start + len(signature))
    if following < 0:
        raise RuntimeError(
            f"following method signature not found after {signature}: {following_signature}"
        )
    return text[:start] + replacement.rstrip() + "\n\n" + text[following:]


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

    function_replacements = (
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
    )
    for old, new, expected in function_replacements:
        text = replace_exact(text, old, new, expected, f"ES1 function {old}")

    token_replacements = (
        ("GL_FRAMEBUFFER_COMPLETE", "GL_FRAMEBUFFER_COMPLETE_OES", 1),
        ("GL_COLOR_ATTACHMENT0", "GL_COLOR_ATTACHMENT0_OES", 1),
        ("GL_DEPTH_ATTACHMENT", "GL_DEPTH_ATTACHMENT_OES", 1),
        ("GL_DEPTH_COMPONENT16", "GL_DEPTH_COMPONENT16_OES", 1),
        ("GL_RENDERBUFFER_WIDTH", "GL_RENDERBUFFER_WIDTH_OES", 1),
        ("GL_RENDERBUFFER_HEIGHT", "GL_RENDERBUFFER_HEIGHT_OES", 1),
        ("GL_FRAMEBUFFER", "GL_FRAMEBUFFER_OES", 4),
        ("GL_RENDERBUFFER", "GL_RENDERBUFFER_OES", 10),
    )
    for old, new, expected in token_replacements:
        text = replace_token(text, old, new, expected)

    validation = '''    if (!SeriousIOS_ValidateOpenGLCompatibility()) {
        _startupScheduled = YES;
        _startupLabel.textColor = UIColor.systemRedColor;
        _startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\\nOpenGL ES 1.1 compatibility validation failed\\n%s",
            kEncounterName,
            SeriousIOS_GetOpenGLCompatibilityError()];
        SeriousIOS_DiagnosticsLog(
            "graphics",
            "compatibility_validation_failed error=%s",
            SeriousIOS_GetOpenGLCompatibilityError());
        return;
    }

    const GLubyte* glVersion = glGetString(GL_VERSION);
    const GLubyte* glRenderer = glGetString(GL_RENDERER);
    const GLubyte* glVendor = glGetString(GL_VENDOR);
    SeriousIOS_DiagnosticsLog(
        "graphics",
        "context version=%s renderer=%s vendor=%s drawable=%dx%d scale=%.3f",
        glVersion == nullptr ? "unknown" : reinterpret_cast<const char*>(glVersion),
        glRenderer == nullptr ? "unknown" : reinterpret_cast<const char*>(glRenderer),
        glVendor == nullptr ? "unknown" : reinterpret_cast<const char*>(glVendor),
        _drawableWidth,
        _drawableHeight,
        self.contentScaleFactor);

    glViewport(0, 0, _drawableWidth, _drawableHeight);'''
    text = replace_once(
        text,
        "    glViewport(0, 0, _drawableWidth, _drawableHeight);",
        validation,
        "OpenGL compatibility validation",
    )
    return text


def diagnostic_startup_methods() -> str:
    return r'''- (void)scheduleEngineStartupIfNeeded {
    if (_startupScheduled || _drawableWidth <= 0 || _drawableHeight <= 0) {
        return;
    }
    _startupScheduled = YES;

    const BOOL hasValidatedGameData = [self requiredSentinelExists];
    if (hasValidatedGameData) {
        NSString* previousCheckpoint = [self previousApplicationCheckpointSummary];
        _startupLabel.textColor = UIColor.whiteColor;
        _startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\nOriginal game data found\n%@\n\nTap Start diagnostic launch",
            kEncounterName,
            previousCheckpoint];
        _launchButton.hidden = NO;
        _importButton.hidden = NO;
        [_importButton setTitle:@"Re-import original .gro files" forState:UIControlStateNormal];
        SeriousIOS_DiagnosticsLog("host", "original_game_data_found sentinel=%s", kRequiredGameDataSentinel.UTF8String);
        return;
    }

    _startupLabel.text = [NSString stringWithFormat:
        @"SeriousiOS %@\nStarting core engine without game data…",
        kEncounterName];

    dispatch_async(dispatch_get_main_queue(), ^{
        const bool started = SeriousIOS_StartCoreEngine();
        const SeriousIOSEngineState state = SeriousIOS_GetEngineState();
        if (started && state == SeriousIOSEngineStateCoreInitialized) {
            self->_startupLabel.textColor = UIColor.systemGreenColor;
            self->_startupLabel.text = [NSString stringWithFormat:
                @"SeriousiOS %@\nCore engine initialized\nWaiting for original game data import",
                kEncounterName];
            self->_importButton.hidden = NO;
            [self refreshImportedGameDataStatus];
            SeriousIOS_DiagnosticsLog("engine", "core_checkpoint_passed encounter=%s", kEncounterName.UTF8String);
            NSLog(@"SeriousiOS core engine checkpoint passed for %@", kEncounterName);
            return;
        }

        NSString* errorText = stringFromCString(
            SeriousIOS_GetEngineStartupError(),
            @"Unknown core engine startup failure");
        self->_startupLabel.textColor = UIColor.systemRedColor;
        self->_startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\nCore engine startup failed\n%@",
            kEncounterName,
            errorText];
        self->_importButton.hidden = YES;
        SeriousIOS_DiagnosticsLog("engine", "core_checkpoint_failed error=%s", errorText.UTF8String);
        NSLog(@"SeriousiOS core engine startup failed for %@: %@", kEncounterName, errorText);
    });
}

- (NSString*)previousApplicationCheckpointSummary {
    const char* userPath = SeriousIOS_GetUserPath();
    if (userPath == nullptr || *userPath == '\0') {
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
    return [NSString stringWithFormat:@"Previous checkpoint:\n%@", checkpoint];
}

- (void)beginApplicationDiagnosticLaunch {
    _launchButton.enabled = NO;
    _importButton.enabled = NO;
    _startupLabel.textColor = UIColor.whiteColor;
    _startupLabel.text = [NSString stringWithFormat:
        @"SeriousiOS %@\nArming staged startup diagnostics…",
        kEncounterName];
    SeriousIOS_DiagnosticsLog("host", "diagnostic_launch_requested");

    dispatch_after(
        dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.75 * NSEC_PER_SEC)),
        dispatch_get_main_queue(), ^{
            [self runApplicationDiagnosticLaunch];
        });
}

- (void)runApplicationDiagnosticLaunch {
    _startupLabel.text = [NSString stringWithFormat:
        @"SeriousiOS %@\nStarting full application\nEvery phase is being persisted…",
        kEncounterName];

    const bool started = SeriousIOS_ApplicationInitialize();
    if (started) {
        _startupLabel.textColor = UIColor.systemGreenColor;
        _startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\nApplication initialized\nStarting UIKit-driven frame loop…",
            kEncounterName];
        _launchButton.hidden = YES;
        _importButton.hidden = YES;
        [self startApplicationFrameLoop];
        SeriousIOS_DiagnosticsLog("host", "application_frame_loop_scheduled fps=60");
        NSLog(@"SeriousiOS application lifecycle initialized for %@", kEncounterName);
        return;
    }

    NSString* errorText = stringFromCString(
        SeriousIOS_ApplicationGetError(),
        @"Unknown application startup failure");
    _startupLabel.textColor = UIColor.systemRedColor;
    _startupLabel.text = [NSString stringWithFormat:
        @"SeriousiOS %@\nApplication startup failed\nStage: %s\n%@\n\nClose and reopen the app before retrying",
        kEncounterName,
        SeriousIOS_ApplicationGetStage(),
        errorText];
    _launchButton.enabled = NO;
    _launchButton.hidden = YES;
    _importButton.enabled = NO;
    _importButton.hidden = YES;
    SeriousIOS_DiagnosticsLog(
        "host",
        "application_startup_failed stage=%s error=%s",
        SeriousIOS_ApplicationGetStage(),
        errorText.UTF8String);
    NSLog(@"SeriousiOS application startup failed for %@ at %s: %@",
        kEncounterName,
        SeriousIOS_ApplicationGetStage(),
        errorText);
}'''


def export_method() -> str:
    return r'''- (void)exportDiagnostics {
    SeriousIOS_DiagnosticsWriteSummary("manual-export");
    SeriousIOS_DiagnosticsFlush();

    NSMutableArray<NSURL*>* files = [NSMutableArray array];
    NSFileManager* fileManager = NSFileManager.defaultManager;
    void (^appendFile)(NSString*) = ^(NSString* path) {
        if (path.length > 0 && [fileManager fileExistsAtPath:path]) {
            [files addObject:[NSURL fileURLWithPath:path]];
        }
    };

    const char* logPath = SeriousIOS_DiagnosticsGetLogPath();
    if (logPath != nullptr && *logPath != '\0') {
        NSString* currentLog = [NSString stringWithUTF8String:logPath];
        appendFile(currentLog);
        appendFile([currentLog stringByAppendingString:@".1"]);
        appendFile([currentLog stringByAppendingString:@".2"]);
    }

    const char* userPath = SeriousIOS_GetUserPath();
    if (userPath != nullptr && *userPath != '\0') {
        NSString* root = [NSString stringWithUTF8String:userPath];
        for (NSString* name in @[
            @"SeriousIOS-build-info.txt",
            @"application-runtime-checkpoint.txt",
            @"SeriousSam.log"
        ]) {
            appendFile([root stringByAppendingPathComponent:name]);
        }
    }

    const char* temporaryPath = SeriousIOS_GetTemporaryPath();
    if (temporaryPath != nullptr && *temporaryPath != '\0') {
        NSString* root = [NSString stringWithUTF8String:temporaryPath];
        for (NSString* name in @[
            @"core-startup-checkpoint.txt",
            @"game-runtime-checkpoint.txt"
        ]) {
            appendFile([root stringByAppendingPathComponent:name]);
        }
    }

    UIViewController* presenter = [self presentingViewController];
    if (presenter == nil) {
        return;
    }
    if (files.count == 0) {
        UIAlertController* alert = [UIAlertController
            alertControllerWithTitle:@"No diagnostics yet"
                             message:@"Run the application once, then try exporting again."
                      preferredStyle:UIAlertControllerStyleAlert];
        [alert addAction:[UIAlertAction actionWithTitle:@"OK"
                                                  style:UIAlertActionStyleDefault
                                                handler:nil]];
        [presenter presentViewController:alert animated:YES completion:nil];
        return;
    }

    UIActivityViewController* share = [[UIActivityViewController alloc]
        initWithActivityItems:files
        applicationActivities:nil];
    share.popoverPresentationController.sourceView = _diagnosticsButton;
    share.popoverPresentationController.sourceRect = _diagnosticsButton.bounds;
    SeriousIOS_DiagnosticsLog("host", "diagnostics_export_presented file_count=%lu", (unsigned long)files.count);
    [presenter presentViewController:share animated:YES completion:nil];
}'''


def transform(path: Path, build_identifier: str) -> None:
    text = transform_opengles1(path.read_text(encoding="utf-8"))

    text = replace_once(
        text,
        '#include "SeriousIOSApplicationLifecycle.h"\n',
        '#include "SeriousIOSApplicationLifecycle.h"\n#include "SeriousIOSDiagnostics.h"\n',
        "diagnostics include",
    )

    text = replace_once(
        text,
        '''    UILabel* _startupLabel;
    UIButton* _importButton;
    CADisplayLink* _displayLink;''',
        '''    UILabel* _startupLabel;
    UIButton* _launchButton;
    UIButton* _diagnosticsButton;
    UIButton* _importButton;
    CADisplayLink* _displayLink;''',
        "diagnostic button ivars",
    )

    button_construction = '''    _launchButton = [UIButton buttonWithType:UIButtonTypeSystem];
    _launchButton.translatesAutoresizingMaskIntoConstraints = NO;
    _launchButton.hidden = YES;
    _launchButton.titleLabel.font = [UIFont systemFontOfSize:16.0 weight:UIFontWeightSemibold];
    _launchButton.configuration = [UIButtonConfiguration filledButtonConfiguration];
    [_launchButton setTitle:@"Start diagnostic launch" forState:UIControlStateNormal];
    [_launchButton addTarget:self
                      action:@selector(beginApplicationDiagnosticLaunch)
            forControlEvents:UIControlEventTouchUpInside];
    [self addSubview:_launchButton];

    _diagnosticsButton = [UIButton buttonWithType:UIButtonTypeSystem];
    _diagnosticsButton.translatesAutoresizingMaskIntoConstraints = NO;
    _diagnosticsButton.titleLabel.font = [UIFont monospacedSystemFontOfSize:12.0 weight:UIFontWeightBold];
    _diagnosticsButton.configuration = [UIButtonConfiguration tintedButtonConfiguration];
    _diagnosticsButton.alpha = 0.72;
    [_diagnosticsButton setTitle:@"LOG" forState:UIControlStateNormal];
    [_diagnosticsButton addTarget:self
                           action:@selector(exportDiagnostics)
                 forControlEvents:UIControlEventTouchUpInside];
    [self addSubview:_diagnosticsButton];

    _importButton = [UIButton buttonWithType:UIButtonTypeSystem];'''
    text = replace_once(
        text,
        "    _importButton = [UIButton buttonWithType:UIButtonTypeSystem];",
        button_construction,
        "diagnostic button construction",
    )

    text = replace_once(
        text,
        '''        [_importButton.centerXAnchor constraintEqualToAnchor:self.centerXAnchor],
        [_importButton.topAnchor constraintEqualToAnchor:_startupLabel.bottomAnchor constant:20.0],''',
        '''        [_launchButton.centerXAnchor constraintEqualToAnchor:self.centerXAnchor],
        [_launchButton.topAnchor constraintEqualToAnchor:_startupLabel.bottomAnchor constant:20.0],
        [_importButton.centerXAnchor constraintEqualToAnchor:self.centerXAnchor],
        [_importButton.topAnchor constraintEqualToAnchor:_launchButton.bottomAnchor constant:12.0],
        [_diagnosticsButton.leadingAnchor constraintEqualToAnchor:self.safeAreaLayoutGuide.leadingAnchor constant:8.0],
        [_diagnosticsButton.topAnchor constraintEqualToAnchor:self.safeAreaLayoutGuide.topAnchor constant:8.0],''',
        "diagnostic button constraints",
    )

    text = replace_method(
        text,
        "- (void)scheduleEngineStartupIfNeeded {",
        "- (void)startApplicationFrameLoop {",
        diagnostic_startup_methods(),
    )

    text = replace_once(
        text,
        "- (NSURL*)gameDataDirectoryURL {",
        export_method() + "\n\n- (NSURL*)gameDataDirectoryURL {",
        "diagnostics export method",
    )

    build_literal = json.dumps(build_identifier)
    launch_initialization = f'''    if (!configurePlatformPaths()) {{
        return NO;
    }}
    if (!SeriousIOS_DiagnosticsInitialize(
            kEncounterName.UTF8String,
            {build_literal})) {{
        NSLog(@"SeriousiOS diagnostics initialization failed for %@", kEncounterName);
    }}
    SeriousIOS_DiagnosticsLog(
        "host",
        "launch encounter=%s os=%s device=%s native_bounds=%.0fx%.0f native_scale=%.3f",
        kEncounterName.UTF8String,
        UIDevice.currentDevice.systemVersion.UTF8String,
        UIDevice.currentDevice.model.UTF8String,
        UIScreen.mainScreen.nativeBounds.size.width,
        UIScreen.mainScreen.nativeBounds.size.height,
        UIScreen.mainScreen.nativeScale);
    if (!registerRuntimeSymbols()) {{'''
    text = replace_once(
        text,
        '''    if (!configurePlatformPaths()) {
        return NO;
    }
    if (!registerRuntimeSymbols()) {''',
        launch_initialization,
        "diagnostics host initialization",
    )

    text = replace_once(
        text,
        '''    if (!registerRuntimeSymbols()) {
        NSLog(@"SeriousiOS static runtime registration failed for %@", kEncounterName);
        return NO;
    }''',
        '''    if (!registerRuntimeSymbols()) {
        SeriousIOS_DiagnosticsLog("host", "static_runtime_registration_failed");
        SeriousIOS_DiagnosticsShutdown();
        NSLog(@"SeriousiOS static runtime registration failed for %@", kEncounterName);
        return NO;
    }
    SeriousIOS_DiagnosticsLog("host", "static_runtime_registration_passed");''',
        "runtime registration diagnostics",
    )

    text = replace_once(
        text,
        '''- (void)applicationDidEnterBackground:(UIApplication*)application {
    (void)application;
    SeriousIOS_ApplicationSuspend();
}''',
        '''- (void)applicationDidEnterBackground:(UIApplication*)application {
    (void)application;
    SeriousIOS_DiagnosticsLog("lifecycle", "application_did_enter_background");
    SeriousIOS_ApplicationSuspend();
    SeriousIOS_DiagnosticsFlush();
}''',
        "background diagnostics",
    )

    text = replace_once(
        text,
        '''- (void)applicationWillEnterForeground:(UIApplication*)application {
    (void)application;
    SeriousIOS_ApplicationResume();
}''',
        '''- (void)applicationWillEnterForeground:(UIApplication*)application {
    (void)application;
    SeriousIOS_DiagnosticsLog("lifecycle", "application_will_enter_foreground");
    SeriousIOS_ApplicationResume();
}''',
        "foreground diagnostics",
    )

    text = replace_once(
        text,
        '''    if (SeriousIOS_ApplicationIsInitialized()) {
        SeriousIOS_ApplicationShutdown();
    } else {
        SeriousIOS_StopEngine();
    }
}''',
        '''    if (SeriousIOS_ApplicationIsInitialized()) {
        SeriousIOS_ApplicationShutdown();
    } else {
        SeriousIOS_StopEngine();
    }
    SeriousIOS_DiagnosticsShutdown();
}''',
        "termination diagnostics",
    )

    text = replace_once(
        text,
        "- (void)applicationWillTerminate:(UIApplication*)application {",
        '''- (void)applicationDidReceiveMemoryWarning:(UIApplication*)application {
    (void)application;
    SeriousIOS_DiagnosticsLog("lifecycle", "memory_warning");
    SeriousIOS_DiagnosticsWriteSummary("memory-warning");
}

- (void)applicationWillTerminate:(UIApplication*)application {''',
        "memory warning diagnostics",
    )

    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("host_source", type=Path)
    parser.add_argument("--build-id", default="local")
    args = parser.parse_args()
    source = args.host_source.resolve()
    if not source.is_file():
        raise SystemExit(f"host source does not exist: {source}")
    transform(source, args.build_id)
    print(
        f"Applied OpenGL ES 1.1, crash-loop-safe diagnostics, and flight recorder UI to {source}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
