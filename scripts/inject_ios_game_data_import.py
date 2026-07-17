#!/usr/bin/env python3
"""Inject safe original-game-data import into the generated SeriousiOS host."""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class PlannedFile:
    source: Path
    destination_relative: PurePosixPath
    category: str


@dataclass(frozen=True)
class PlanResult:
    item_type: str
    files: tuple[PlannedFile, ...]
    skipped: int


def _safe_relative(relative: PurePosixPath) -> bool:
    if relative.is_absolute() or not relative.parts:
        return False
    return all(part not in ("", ".", "..") for part in relative.parts)


def _regular_files(root: Path) -> tuple[list[Path], int]:
    files: list[Path] = []
    skipped = 0
    for current_root, directory_names, file_names in os.walk(root, followlinks=False):
        current = Path(current_root)
        safe_directories: list[str] = []
        for directory_name in directory_names:
            candidate = current / directory_name
            if candidate.is_symlink():
                skipped += 1
            else:
                safe_directories.append(directory_name)
        directory_names[:] = safe_directories
        for file_name in file_names:
            candidate = current / file_name
            if candidate.is_symlink() or not candidate.is_file():
                skipped += 1
                continue
            files.append(candidate)
    return files, skipped


def plan_selection(selected: Path) -> PlanResult:
    if selected.is_symlink():
        return PlanResult("unsupported", (), 1)
    if selected.is_file():
        if selected.suffix.lower() == ".gro":
            return PlanResult(
                "gro_file",
                (PlannedFile(selected, PurePosixPath(selected.name), "gro"),),
                0,
            )
        return PlanResult("unsupported_file", (), 1)
    if not selected.is_dir():
        return PlanResult("missing", (), 1)

    if selected.name.lower() == "levels":
        descendants, skipped = _regular_files(selected)
        planned: list[PlannedFile] = []
        for source in descendants:
            relative = PurePosixPath(source.relative_to(selected).as_posix())
            if not _safe_relative(relative):
                skipped += 1
                continue
            planned.append(
                PlannedFile(source, PurePosixPath("Levels") / relative, "levels")
            )
        return PlanResult("levels_folder", tuple(planned), skipped)

    planned = []
    skipped = 0
    for child in selected.iterdir():
        if child.is_symlink():
            skipped += 1
            continue
        if child.is_file() and child.suffix.lower() == ".gro":
            planned.append(PlannedFile(child, PurePosixPath(child.name), "gro"))
            continue
        if child.is_dir() and child.name.lower() == "levels":
            descendants, nested_skipped = _regular_files(child)
            skipped += nested_skipped
            for source in descendants:
                relative = PurePosixPath(source.relative_to(child).as_posix())
                if not _safe_relative(relative):
                    skipped += 1
                    continue
                planned.append(
                    PlannedFile(source, PurePosixPath("Levels") / relative, "levels")
                )
            continue
        skipped += 1
    return PlanResult("game_directory", tuple(planned), skipped)


def apply_plan(plans: list[PlanResult], destination: Path) -> tuple[int, int]:
    copied = 0
    replaced = 0
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    for plan in plans:
        for item in plan.files:
            if not _safe_relative(item.destination_relative):
                raise RuntimeError("unsafe destination")
            target = destination.joinpath(*item.destination_relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            resolved_parent = target.parent.resolve()
            if destination_root != resolved_parent and destination_root not in resolved_parent.parents:
                raise RuntimeError("destination escaped root")
            if target.exists():
                if target.is_dir():
                    raise RuntimeError("destination is a directory")
                target.unlink()
                replaced += 1
            shutil.copy2(item.source, target)
            copied += 1
    return copied, replaced


STATUS_METHODS = r'''- (BOOL)fileExistsAndIsNonEmptyAtURL:(NSURL*)url {
    NSNumber* fileSize = nil;
    const BOOL exists = [NSFileManager.defaultManager fileExistsAtPath:url.path];
    if (!exists || ![url getResourceValue:&fileSize forKey:NSURLFileSizeKey error:nil]) {
        return NO;
    }
    return fileSize.unsignedLongLongValue > 0;
}

- (BOOL)requiredSentinelExists {
    NSURL* dataDirectory = [self gameDataDirectoryURL];
    if (dataDirectory == nil) {
        return NO;
    }
    NSURL* sentinel = [dataDirectory URLByAppendingPathComponent:kRequiredGameDataSentinel];
    return [self fileExistsAndIsNonEmptyAtURL:sentinel];
}

- (BOOL)requiredLooseLevelExists {
#if defined(SERIOUSIOS_TFE)
    NSURL* dataDirectory = [self gameDataDirectoryURL];
    if (dataDirectory == nil) {
        return NO;
    }
    NSURL* level = [dataDirectory URLByAppendingPathComponent:@"Levels/01_Hatshepsut.wld"];
    return [self fileExistsAndIsNonEmptyAtURL:level];
#else
    return YES;
#endif
}

- (BOOL)hasCompleteGameData {
    return [self requiredSentinelExists] && [self requiredLooseLevelExists];
}

- (void)refreshImportedGameDataStatus {
    const BOOL archivesFound = [self requiredSentinelExists];
    const BOOL levelsFound = [self requiredLooseLevelExists];
    NSURL* dataDirectory = [self gameDataDirectoryURL];
    NSArray<NSURL*>* files = [NSFileManager.defaultManager contentsOfDirectoryAtURL:dataDirectory
                                                          includingPropertiesForKeys:@[NSURLFileSizeKey]
                                                                             options:NSDirectoryEnumerationSkipsHiddenFiles
                                                                               error:nil];
    NSUInteger groCount = 0;
    unsigned long long groBytes = 0;
    for (NSURL* file in files) {
        if ([file.pathExtension caseInsensitiveCompare:@"gro"] != NSOrderedSame) {
            continue;
        }
        NSNumber* fileSize = nil;
        [file getResourceValue:&fileSize forKey:NSURLFileSizeKey error:nil];
        groCount += 1;
        groBytes += fileSize.unsignedLongLongValue;
    }

#if defined(SERIOUSIOS_TFE)
    if (archivesFound && levelsFound) {
        _startupLabel.textColor = UIColor.systemGreenColor;
        _startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\nCore engine initialized\nOriginal archives and Levels/01_Hatshepsut.wld found\n%lu .gro files, %@\nClose and reopen the app to run the full application checkpoint",
            kEncounterName,
            (unsigned long)groCount,
            formattedByteCount(groBytes)];
    } else if (archivesFound) {
        _startupLabel.textColor = UIColor.systemOrangeColor;
        _startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\nOriginal archives found, but Levels/01_Hatshepsut.wld is missing\nImport the original Levels folder",
            kEncounterName];
    } else if (levelsFound) {
        _startupLabel.textColor = UIColor.systemOrangeColor;
        _startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\nOriginal Levels folder found, but required archive %@ is missing\nImport the original game directory or .gro files",
            kEncounterName,
            kRequiredGameDataSentinel];
    } else {
        _startupLabel.textColor = UIColor.whiteColor;
        _startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\nWaiting for original game data\nImport the original game directory, .gro files, or Levels folder",
            kEncounterName];
    }
#else
    if (archivesFound) {
        _startupLabel.textColor = UIColor.systemGreenColor;
        _startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\nRequired archive found: %@\n%lu .gro files, %@\nClose and reopen the app to run the full application checkpoint",
            kEncounterName,
            kRequiredGameDataSentinel,
            (unsigned long)groCount,
            formattedByteCount(groBytes)];
    } else {
        _startupLabel.textColor = UIColor.whiteColor;
        _startupLabel.text = [NSString stringWithFormat:
            @"SeriousiOS %@\nWaiting for original game data\nRequired archive: %@",
            kEncounterName,
            kRequiredGameDataSentinel];
    }
#endif
#if defined(SERIOUSIOS_TFE)
    const BOOL anyDataFound = archivesFound || levelsFound;
#else
    const BOOL anyDataFound = archivesFound;
#endif
    [_importButton setTitle:anyDataFound
        ? @"Re-import original game data"
        : @"Import original game data"
        forState:UIControlStateNormal];
}
'''


IMPORT_METHODS = r'''- (void)beginGameDataImport {
    UIViewController* presenter = [self presentingViewController];
    if (presenter == nil) {
        return;
    }

    UIDocumentPickerViewController* picker = [[UIDocumentPickerViewController alloc]
        initForOpeningContentTypes:@[UTTypeFolder, UTTypeData]
        asCopy:YES];
    picker.delegate = self;
    picker.allowsMultipleSelection = YES;
    picker.modalPresentationStyle = UIModalPresentationFormSheet;
    [presenter presentViewController:picker animated:YES completion:nil];
}

- (void)documentPicker:(UIDocumentPickerViewController*)controller
    didPickDocumentsAtURLs:(NSArray<NSURL*>*)urls {
    (void)controller;
    _importButton.enabled = NO;
    _startupLabel.textColor = UIColor.whiteColor;
    _startupLabel.text = [NSString stringWithFormat:
        @"SeriousiOS %@\nCopying selected original game data…",
        kEncounterName];

    NSURL* destinationDirectory = [self gameDataDirectoryURL];
    if (destinationDirectory == nil) {
        _importButton.enabled = YES;
        _startupLabel.textColor = UIColor.systemRedColor;
        _startupLabel.text = @"SeriousiOS data directory is unavailable";
        return;
    }
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        NSFileManager* fileManager = NSFileManager.defaultManager;
        __block NSUInteger groCopied = 0;
        __block NSUInteger levelsCopied = 0;
        __block NSUInteger skipped = 0;
        __block NSUInteger replaced = 0;
        __block unsigned long long copiedBytes = 0;
        __block NSError* firstError = nil;

        BOOL (^safeRelativePath)(NSString*) = ^BOOL(NSString* relativePath) {
            if (relativePath.length == 0 || relativePath.isAbsolutePath) {
                return NO;
            }
            NSString* standardized = relativePath.stringByStandardizingPath;
            if ([standardized isEqualToString:@".."] || [standardized hasPrefix:@"../"] || [standardized hasPrefix:@"/"]) {
                return NO;
            }
            for (NSString* component in standardized.pathComponents) {
                if ([component isEqualToString:@".."] || [component isEqualToString:@"."]) {
                    return NO;
                }
            }
            return YES;
        };

        BOOL (^copyFile)(NSURL*, NSString*, BOOL) = ^BOOL(
            NSURL* sourceURL,
            NSString* destinationRelativePath,
            BOOL levelsFile) {
            if (!safeRelativePath(destinationRelativePath)) {
                skipped += 1;
                return NO;
            }
            NSString* standardizedRelative = destinationRelativePath.stringByStandardizingPath;
            NSURL* destinationURL = [destinationDirectory URLByAppendingPathComponent:standardizedRelative];
            NSString* destinationRoot = destinationDirectory.path.stringByStandardizingPath;
            NSString* destinationPath = destinationURL.path.stringByStandardizingPath;
            NSString* requiredPrefix = [destinationRoot stringByAppendingString:@"/"];
            if (![destinationPath hasPrefix:requiredPrefix]) {
                skipped += 1;
                return NO;
            }

            NSNumber* isRegular = nil;
            NSNumber* isSymbolicLink = nil;
            [sourceURL getResourceValue:&isRegular forKey:NSURLIsRegularFileKey error:nil];
            [sourceURL getResourceValue:&isSymbolicLink forKey:NSURLIsSymbolicLinkKey error:nil];
            if (!isRegular.boolValue || isSymbolicLink.boolValue) {
                skipped += 1;
                return NO;
            }

            NSURL* parent = [destinationURL URLByDeletingLastPathComponent];
            NSError* directoryError = nil;
            if (![fileManager createDirectoryAtURL:parent
                       withIntermediateDirectories:YES
                                        attributes:nil
                                             error:&directoryError]) {
                if (firstError == nil) {
                    firstError = directoryError;
                }
                return NO;
            }

            BOOL destinationIsDirectory = NO;
            const BOOL destinationExists = [fileManager
                fileExistsAtPath:destinationURL.path
                isDirectory:&destinationIsDirectory];
            if (destinationExists && destinationIsDirectory) {
                if (firstError == nil) {
                    firstError = [NSError errorWithDomain:@"SeriousIOSImport"
                                                     code:2
                                                 userInfo:@{NSLocalizedDescriptionKey: @"A destination file path is occupied by a directory"}];
                }
                return NO;
            }

            NSString* temporaryName = [NSString stringWithFormat:
                @".%@.seriousios-import-%@",
                destinationURL.lastPathComponent,
                [NSUUID UUID].UUIDString];
            NSURL* temporaryURL = [parent URLByAppendingPathComponent:temporaryName];
            NSError* copyError = nil;
            if (![fileManager copyItemAtURL:sourceURL toURL:temporaryURL error:&copyError]) {
                if (firstError == nil) {
                    firstError = copyError;
                }
                return NO;
            }

            NSError* installError = nil;
            if (destinationExists) {
                if (![fileManager replaceItemAtURL:destinationURL
                                       withItemAtURL:temporaryURL
                                      backupItemName:nil
                                             options:0
                                    resultingItemURL:nil
                                               error:&installError]) {
                    [fileManager removeItemAtURL:temporaryURL error:nil];
                    if (firstError == nil) {
                        firstError = installError;
                    }
                    return NO;
                }
                replaced += 1;
            } else if (![fileManager moveItemAtURL:temporaryURL
                                             toURL:destinationURL
                                             error:&installError]) {
                [fileManager removeItemAtURL:temporaryURL error:nil];
                if (firstError == nil) {
                    firstError = installError;
                }
                return NO;
            }
            NSNumber* fileSize = nil;
            [destinationURL getResourceValue:&fileSize forKey:NSURLFileSizeKey error:nil];
            copiedBytes += fileSize.unsignedLongLongValue;
            if (levelsFile) {
                levelsCopied += 1;
            } else {
                groCopied += 1;
            }
            return YES;
        };

        void (^copyLevelsFolder)(NSURL*) = ^(NSURL* levelsRoot) {
            NSString* rootPath = levelsRoot.path.stringByStandardizingPath;
            NSString* rootPrefix = [rootPath stringByAppendingString:@"/"];
            NSDirectoryEnumerator<NSURL*>* enumerator = [fileManager
                enumeratorAtURL:levelsRoot
                includingPropertiesForKeys:@[
                    NSURLIsDirectoryKey,
                    NSURLIsRegularFileKey,
                    NSURLIsSymbolicLinkKey,
                    NSURLFileSizeKey
                ]
                options:NSDirectoryEnumerationSkipsHiddenFiles
                errorHandler:^BOOL(NSURL* url, NSError* error) {
                    (void)url;
                    if (firstError == nil) {
                        firstError = error;
                    }
                    return YES;
                }];
            for (NSURL* childURL in enumerator) {
                NSNumber* isDirectory = nil;
                NSNumber* isSymbolicLink = nil;
                [childURL getResourceValue:&isDirectory forKey:NSURLIsDirectoryKey error:nil];
                [childURL getResourceValue:&isSymbolicLink forKey:NSURLIsSymbolicLinkKey error:nil];
                if (isSymbolicLink.boolValue) {
                    skipped += 1;
                    if (isDirectory.boolValue) {
                        [enumerator skipDescendants];
                    }
                    continue;
                }
                if (isDirectory.boolValue) {
                    continue;
                }
                NSString* childPath = childURL.path.stringByStandardizingPath;
                if (![childPath hasPrefix:rootPrefix]) {
                    skipped += 1;
                    continue;
                }
                NSString* relative = [childPath substringFromIndex:rootPrefix.length];
                NSString* destinationRelative = [@"Levels" stringByAppendingPathComponent:relative];
                copyFile(childURL, destinationRelative, YES);
            }
        };

        for (NSURL* selectedURL in urls) {
            const BOOL accessed = [selectedURL startAccessingSecurityScopedResource];
            @autoreleasepool {
                NSNumber* isDirectory = nil;
                NSNumber* isRegular = nil;
                NSNumber* isSymbolicLink = nil;
                [selectedURL getResourceValue:&isDirectory forKey:NSURLIsDirectoryKey error:nil];
                [selectedURL getResourceValue:&isRegular forKey:NSURLIsRegularFileKey error:nil];
                [selectedURL getResourceValue:&isSymbolicLink forKey:NSURLIsSymbolicLinkKey error:nil];

                NSString* itemType = @"unsupported";
                if (isSymbolicLink.boolValue) {
                    skipped += 1;
                } else if (isRegular.boolValue
                    && [selectedURL.pathExtension caseInsensitiveCompare:@"gro"] == NSOrderedSame) {
                    itemType = @"gro_file";
                    copyFile(selectedURL, selectedURL.lastPathComponent, NO);
                } else if (isDirectory.boolValue
                    && [selectedURL.lastPathComponent caseInsensitiveCompare:@"Levels"] == NSOrderedSame) {
                    itemType = @"levels_folder";
                    copyLevelsFolder(selectedURL);
                } else if (isDirectory.boolValue) {
                    itemType = @"game_directory";
                    NSError* listingError = nil;
                    NSArray<NSURL*>* children = [fileManager contentsOfDirectoryAtURL:selectedURL
                                                            includingPropertiesForKeys:@[
                                                                NSURLIsDirectoryKey,
                                                                NSURLIsRegularFileKey,
                                                                NSURLIsSymbolicLinkKey
                                                            ]
                                                                               options:NSDirectoryEnumerationSkipsHiddenFiles
                                                                                 error:&listingError];
                    if (children == nil && firstError == nil) {
                        firstError = listingError;
                    }
                    for (NSURL* childURL in children) {
                        NSNumber* childDirectory = nil;
                        NSNumber* childRegular = nil;
                        NSNumber* childSymbolicLink = nil;
                        [childURL getResourceValue:&childDirectory forKey:NSURLIsDirectoryKey error:nil];
                        [childURL getResourceValue:&childRegular forKey:NSURLIsRegularFileKey error:nil];
                        [childURL getResourceValue:&childSymbolicLink forKey:NSURLIsSymbolicLinkKey error:nil];
                        if (childSymbolicLink.boolValue) {
                            skipped += 1;
                        } else if (childRegular.boolValue
                            && [childURL.pathExtension caseInsensitiveCompare:@"gro"] == NSOrderedSame) {
                            copyFile(childURL, childURL.lastPathComponent, NO);
                        } else if (childDirectory.boolValue
                            && [childURL.lastPathComponent caseInsensitiveCompare:@"Levels"] == NSOrderedSame) {
                            copyLevelsFolder(childURL);
                        } else {
                            skipped += 1;
                        }
                    }
                } else {
                    skipped += 1;
                }
                SeriousIOS_DiagnosticsLog(
                    "import",
                    "selected type=%s root=%s encounter=%s",
                    itemType.UTF8String,
                    selectedURL.lastPathComponent.UTF8String,
                    kEncounterPathComponent.UTF8String);
            }
            if (accessed) {
                [selectedURL stopAccessingSecurityScopedResource];
            }
        }

        const BOOL archivesFound = [self requiredSentinelExists];
        const BOOL levelsFound = [self requiredLooseLevelExists];
        NSString* classification = nil;
#if defined(SERIOUSIOS_TFE)
        const NSInteger tfeLevelStatus = levelsFound ? 1 : 0;
        if (firstError != nil) {
            classification = @"partial_failure";
        } else if (archivesFound && levelsFound) {
            classification = @"complete";
        } else if (archivesFound) {
            classification = @"archives_present_levels_missing";
        } else if (levelsFound) {
            classification = @"levels_present_archives_missing";
        } else {
            classification = @"incomplete";
        }
#else
        const NSInteger tfeLevelStatus = -1;
        if (firstError != nil) {
            classification = @"partial_failure";
        } else {
            classification = archivesFound ? @"complete" : @"archives_missing";
        }
#endif
        SeriousIOS_DiagnosticsLog(
            "import",
            "complete encounter=%s gro_copied=%lu levels_copied=%lu bytes=%llu skipped=%lu replaced=%lu archive_sentinel=%d tfe_level=%ld classification=%s error_domain=%s error_code=%ld",
            kEncounterPathComponent.UTF8String,
            (unsigned long)groCopied,
            (unsigned long)levelsCopied,
            copiedBytes,
            (unsigned long)skipped,
            (unsigned long)replaced,
            archivesFound,
            (long)tfeLevelStatus,
            classification.UTF8String,
            firstError == nil ? "none" : firstError.domain.UTF8String,
            firstError == nil ? 0L : (long)firstError.code);

        dispatch_async(dispatch_get_main_queue(), ^{
            self->_importButton.enabled = YES;
            [self refreshImportedGameDataStatus];
            if (firstError != nil) {
                self->_startupLabel.textColor = UIColor.systemOrangeColor;
                self->_startupLabel.text = [self->_startupLabel.text stringByAppendingFormat:
                    @"\nImport partially failed (%@ %ld). Existing game data was preserved.",
                    firstError.domain,
                    (long)firstError.code];
            } else if (archivesFound && levelsFound) {
                self->_startupLabel.text = [self->_startupLabel.text stringByAppendingFormat:
                    @"\nImported %lu archives and %lu Levels files (%@).",
                    (unsigned long)groCopied,
                    (unsigned long)levelsCopied,
                    formattedByteCount(copiedBytes)];
            }
        });
    });
}
'''


def _replace_block(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"start marker not found: {start_marker}")
    end = text.find(end_marker, start + len(start_marker))
    if end < 0:
        raise RuntimeError(f"end marker not found: {end_marker}")
    return text[:start] + replacement.rstrip() + "\n\n" + text[end:]


def transform_text(text: str) -> str:
    if "gro_copied=%lu levels_copied=%lu" in text:
        raise RuntimeError("game-data import is already injected")
    startup_old = "const BOOL hasValidatedGameData = [self requiredSentinelExists];"
    if text.count(startup_old) != 1:
        raise RuntimeError("expected one diagnostic startup data check")
    text = text.replace(
        startup_old,
        "const BOOL hasValidatedGameData = [self hasCompleteGameData];",
        1,
    )
    text = text.replace("Import original .gro files", "Import original game data")
    text = text.replace("Re-import original .gro files", "Re-import original game data")
    text = _replace_block(
        text,
        "- (BOOL)requiredSentinelExists {",
        "- (UIViewController*)presentingViewController {",
        STATUS_METHODS,
    )
    text = _replace_block(
        text,
        "- (void)beginGameDataImport {",
        "- (void)documentPickerWasCancelled:",
        IMPORT_METHODS,
    )
    required = (
        "[self hasCompleteGameData]",
        "Levels/01_Hatshepsut.wld",
        "gro_copied=%lu levels_copied=%lu",
        "selected type=%s root=%s encounter=%s",
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"transformed host missing token: {token}")
    if "Import original .gro files" in text or "Re-import original .gro files" in text:
        raise RuntimeError("obsolete importer wording remains")
    return text


def transform(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    path.write_text(transform_text(original), encoding="utf-8")


def self_test() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "GOG Serious Sam"
        levels = source / "Levels"
        nested = levels / "Sub"
        nested.mkdir(parents=True)
        (source / "1_00_music.gro").write_bytes(b"gro-new")
        (source / "ignore.exe").write_bytes(b"no")
        (source / "ignore.dll").write_bytes(b"no")
        (levels / "01_Hatshepsut.wld").write_bytes(b"world")
        (nested / "Extra.dat").write_bytes(b"nested")

        levels_plan = plan_selection(levels)
        assert levels_plan.item_type == "levels_folder"
        assert {str(item.destination_relative) for item in levels_plan.files} == {
            "Levels/01_Hatshepsut.wld",
            "Levels/Sub/Extra.dat",
        }

        game_plan = plan_selection(source)
        assert game_plan.item_type == "game_directory"
        destinations = {str(item.destination_relative) for item in game_plan.files}
        assert destinations == {
            "1_00_music.gro",
            "Levels/01_Hatshepsut.wld",
            "Levels/Sub/Extra.dat",
        }
        assert game_plan.skipped == 2

        destination = root / "GameData"
        destination.mkdir()
        existing_gro = destination / "existing.gro"
        existing_gro.write_bytes(b"keep")
        existing_level = destination / "Levels" / "01_Hatshepsut.wld"
        existing_level.parent.mkdir()
        existing_level.write_bytes(b"old")
        copied, replaced = apply_plan([levels_plan], destination)
        assert copied == 2
        assert replaced == 1
        assert existing_gro.read_bytes() == b"keep"
        assert existing_level.read_bytes() == b"world"
        assert (destination / "Levels" / "Sub" / "Extra.dat").read_bytes() == b"nested"

        assert not _safe_relative(PurePosixPath("../escape.wld"))
        assert not _safe_relative(PurePosixPath("Levels/../../escape.wld"))
        assert _safe_relative(PurePosixPath("Levels/Sub/Extra.dat"))

        individual = plan_selection(source / "1_00_music.gro")
        assert [str(item.destination_relative) for item in individual.files] == [
            "1_00_music.gro"
        ]

    fixture = '''const BOOL hasValidatedGameData = [self requiredSentinelExists];
[_importButton setTitle:@"Import original .gro files" forState:UIControlStateNormal];
- (BOOL)requiredSentinelExists { return NO; }
- (void)refreshImportedGameDataStatus {}
- (UIViewController*)presentingViewController { return nil; }
- (void)beginGameDataImport {}
- (void)documentPicker:(UIDocumentPickerViewController*)controller didPickDocumentsAtURLs:(NSArray<NSURL*>*)urls {}
- (void)documentPickerWasCancelled:(UIDocumentPickerViewController*)controller {}
'''
    transformed = transform_text(fixture)
    assert "[self hasCompleteGameData]" in transformed
    assert "Levels/01_Hatshepsut.wld" in transformed
    assert "Import original game data" in transformed
    assert "gro_copied=%lu levels_copied=%lu" in transformed
    print("SeriousiOS game-data import self-test passed")


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
    print(f"Injected safe original-game-data import into {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
