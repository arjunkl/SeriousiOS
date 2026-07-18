#!/usr/bin/env python3
"""Replace the generated diagnostic export with one consolidated report."""

from __future__ import annotations

import argparse
from pathlib import Path


EXPORT_METHOD = r'''- (void)exportDiagnostics {
    SeriousIOS_DiagnosticsWriteSummary("manual-export");
    SeriousIOS_DiagnosticsFlush();

    UIViewController* presenter = [self presentingViewController];
    if (presenter == nil) {
        return;
    }

    NSFileManager* fileManager = NSFileManager.defaultManager;
    const char* userPath = SeriousIOS_GetUserPath();
    NSString* reportRoot = userPath != nullptr && *userPath != '\0'
        ? [NSString stringWithUTF8String:userPath]
        : NSTemporaryDirectory();
    if (reportRoot.length == 0) {
        reportRoot = NSTemporaryDirectory();
    }
    NSString* reportPath = [reportRoot
        stringByAppendingPathComponent:@"SeriousIOS-diagnostics-report.txt"];

    NSMutableData* report = [NSMutableData data];
    void (^appendText)(NSString*) = ^(NSString* text) {
        if (text.length == 0) {
            return;
        }
        NSData* encoded = [text dataUsingEncoding:NSUTF8StringEncoding];
        if (encoded != nil) {
            [report appendData:encoded];
        }
    };
    void (^appendSection)(NSString*, NSString*) = ^(NSString* title, NSString* path) {
        appendText([NSString stringWithFormat:
            @"\n\n==================== %@ ====================\n",
            title]);
        if (path.length == 0 || ![fileManager fileExistsAtPath:path]) {
            appendText(@"[not present]\n");
            return;
        }
        NSError* readError = nil;
        NSData* data = [NSData dataWithContentsOfFile:path
                                             options:NSDataReadingMappedIfSafe
                                               error:&readError];
        if (data == nil) {
            appendText([NSString stringWithFormat:
                @"[read failed: %@ %ld]\n",
                readError.domain ?: @"unknown",
                (long)readError.code]);
            return;
        }
        [report appendData:data];
        appendText(@"\n");
    };

    NSString* generatedAt = [[NSISO8601DateFormatter new] stringFromDate:[NSDate date]];
    appendText(@"SeriousiOS consolidated diagnostic report\n");
    appendText([NSString stringWithFormat:@"generated_at=%@\n", generatedAt]);
    appendText([NSString stringWithFormat:@"encounter=%@\n", kEncounterName]);

    NSString* userRoot = userPath != nullptr && *userPath != '\0'
        ? [NSString stringWithUTF8String:userPath]
        : nil;
    const char* temporaryPath = SeriousIOS_GetTemporaryPath();
    NSString* temporaryRoot = temporaryPath != nullptr && *temporaryPath != '\0'
        ? [NSString stringWithUTF8String:temporaryPath]
        : nil;

    appendSection(@"BUILD INFO", userRoot == nil
        ? nil
        : [userRoot stringByAppendingPathComponent:@"SeriousIOS-build-info.txt"]);
    appendSection(@"APPLICATION CHECKPOINT", userRoot == nil
        ? nil
        : [userRoot stringByAppendingPathComponent:@"application-runtime-checkpoint.txt"]);
    appendSection(@"CORE STARTUP CHECKPOINT", temporaryRoot == nil
        ? nil
        : [temporaryRoot stringByAppendingPathComponent:@"core-startup-checkpoint.txt"]);
    appendSection(@"GAME RUNTIME CHECKPOINT", temporaryRoot == nil
        ? nil
        : [temporaryRoot stringByAppendingPathComponent:@"game-runtime-checkpoint.txt"]);
    appendSection(@"SERIOUS SAM ENGINE LOG", userRoot == nil
        ? nil
        : [userRoot stringByAppendingPathComponent:@"SeriousSam.log"]);

    const char* logPath = SeriousIOS_DiagnosticsGetLogPath();
    if (logPath != nullptr && *logPath != '\0') {
        NSString* currentLog = [NSString stringWithUTF8String:logPath];
        appendSection(@"SERIOUSIOS LOG — OLDEST ROTATION",
            [currentLog stringByAppendingString:@".2"]);
        appendSection(@"SERIOUSIOS LOG — PREVIOUS ROTATION",
            [currentLog stringByAppendingString:@".1"]);
        appendSection(@"SERIOUSIOS LOG — CURRENT", currentLog);
    } else {
        appendSection(@"SERIOUSIOS LOG", nil);
    }

    NSError* writeError = nil;
    if (![report writeToFile:reportPath
                     options:NSDataWritingAtomic
                       error:&writeError]) {
        SeriousIOS_DiagnosticsLog(
            "host",
            "diagnostics_report_write_failed domain=%s code=%ld",
            writeError.domain.UTF8String,
            (long)writeError.code);
        UIAlertController* alert = [UIAlertController
            alertControllerWithTitle:@"Diagnostic export failed"
                             message:[NSString stringWithFormat:
                                 @"Could not create the consolidated report (%@ %ld).",
                                 writeError.domain,
                                 (long)writeError.code]
                      preferredStyle:UIAlertControllerStyleAlert];
        [alert addAction:[UIAlertAction actionWithTitle:@"OK"
                                                  style:UIAlertActionStyleDefault
                                                handler:nil]];
        [presenter presentViewController:alert animated:YES completion:nil];
        return;
    }

    NSURL* reportURL = [NSURL fileURLWithPath:reportPath];
    UIActivityViewController* share = [[UIActivityViewController alloc]
        initWithActivityItems:@[reportURL]
        applicationActivities:nil];
    share.popoverPresentationController.sourceView = _diagnosticsButton;
    share.popoverPresentationController.sourceRect = _diagnosticsButton.bounds;
    SeriousIOS_DiagnosticsLog(
        "host",
        "diagnostics_export_presented file_count=1 report_bytes=%lu",
        (unsigned long)report.length);
    [presenter presentViewController:share animated:YES completion:nil];
}'''


def replace_method(text: str) -> str:
    start_marker = "- (void)exportDiagnostics {"
    end_marker = "- (NSURL*)gameDataDirectoryURL {"
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError("exportDiagnostics method not found")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError("gameDataDirectoryURL marker not found")
    if text.count(start_marker) != 1:
        raise RuntimeError("expected exactly one exportDiagnostics method")
    return text[:start] + EXPORT_METHOD + "\n\n" + text[end:]


def transform(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    transformed = replace_method(original)
    required = (
        "SeriousIOS-diagnostics-report.txt",
        "initWithActivityItems:@[reportURL]",
        "SERIOUS SAM ENGINE LOG",
        "SERIOUSIOS LOG — CURRENT",
        "diagnostics_export_presented file_count=1",
    )
    for token in required:
        if token not in transformed:
            raise RuntimeError(f"consolidated export missing token: {token}")
    if "initWithActivityItems:files" in transformed:
        raise RuntimeError("multi-file diagnostic export remains")
    path.write_text(transformed, encoding="utf-8")


def self_test() -> None:
    fixture = '''- (void)exportDiagnostics {
    NSMutableArray<NSURL*>* files = [NSMutableArray array];
    UIActivityViewController* share = [[UIActivityViewController alloc]
        initWithActivityItems:files
        applicationActivities:nil];
}

- (NSURL*)gameDataDirectoryURL { return nil; }
'''
    transformed = replace_method(fixture)
    assert "SeriousIOS-diagnostics-report.txt" in transformed
    assert "initWithActivityItems:@[reportURL]" in transformed
    assert "initWithActivityItems:files" not in transformed
    assert transformed.count("- (void)exportDiagnostics {") == 1
    assert transformed.count("- (NSURL*)gameDataDirectoryURL {") == 1
    print("SeriousiOS consolidated diagnostics self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("host_source", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        if args.host_source is None:
            return 0
    if args.host_source is None:
        parser.error("host_source is required unless only --self-test is used")
    source = args.host_source.resolve()
    if not source.is_file():
        raise SystemExit(f"host source does not exist: {source}")
    transform(source)
    print(f"Injected consolidated diagnostic export into {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
