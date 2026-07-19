# SeriousiOS user-data and game-runtime gate

## Proven build revision

- SeriousiOS branch revision: `7643d8060f5616e3eef90f48b56005421d2a6907`
- Pinned SeriousSamClassic revision: `80b9893e5b74e5a2160eaf63e6d6b3f3981dfbbd`
- Target: `arm64-apple-ios15.0`
- Strict full-retention closure: passed for TFE and TSE
- Undefined symbols: 0 for both encounters
- Duplicate symbols: 0 for both encounters

## Device products

| Encounter | Executable SHA-256 | Unsigned IPA SHA-256 |
|---|---|---|
| The First Encounter | `568cbada2b6d2d11501096a99386362b71c1d7fc1103962379549e78c28fc94f` | `4867957053c7e0c72eb6a638362f0bc4b09db7aaed88ba4cbe638808ade3e69a` |
| The Second Encounter | `611d6d7022e68db29e3fabfaf60870a4a31b9376c6c724e101b2366e9433bafa` | `d0846acead5f1aa6bf2fa69e0738d1b20b96cd153a80c3ebf8c6f3495f84b88e` |

The IPAs are unsigned and contain no copyrighted game data.

## User-controlled import

The UIKit host exposes a document picker after the pre-data core checkpoint succeeds.

The importer:

- Accepts individual files or a selected directory.
- Recursively discovers files inside a selected directory.
- Copies only files with a `.gro` extension.
- Writes them into the encounter-specific `Documents/SeriousIOS/<encounter>/GameData/` sandbox directory.
- Reports the copied file count and total byte size.
- Does not download, generate, or bundle original game assets.

### Encounter sentinels

- TFE requires `1_00_music.gro`.
- TSE requires `SE1_00_Levels.gro`.

The sentinel is an encounter discriminator, not a complete-data guarantee. Later startup still reports any missing archive, class, script, font, or settings dependency explicitly.

## Clean-launch startup selection

The host chooses one startup path after the EAGL drawable is ready:

1. If the encounter sentinel is absent, it calls `SeriousIOS_StartCoreEngine()` with an empty game ID. This remains the proprietary-data-free platform checkpoint.
2. If the encounter sentinel is present, it calls `SeriousIOS_StartGameRuntime()` with `serioussam` for TFE or `serioussamse` for TSE.

A successful import therefore asks the tester to close and reopen the app. The port deliberately avoids ending and reinitializing the legacy engine inside the same process until reentrancy is proven.

## Full game-runtime checkpoint

The data-dependent checkpoint performs:

1. Explicit iOS sandbox and EAGL validation.
2. `SE_InitEngine` with the real encounter identifier.
3. Original `.gro` archive mounting and encounter-specific Engine initialization.
4. Network and `Classes\\Player.ecl` initialization performed by the upstream Engine path.
5. Static `GAME_Create()` invocation.
6. `CGame::Initialize("Data\\SeriousSam.gms")`.
7. A `game-runtime-checkpoint.txt` result in the app sandbox.

Checkpoint states are `starting`, `initialized`, `failed`, and `stopped`. A failure includes the captured Serious Engine error string when the legacy code throws one.

## What is proven

- The data importer and both encounter variants compile for iPhoneOS.
- The Engine-to-Game bootstrap compiles inside both complete static runtime graphs.
- Both graphs retain zero undefined and duplicate symbols with dead stripping disabled.
- Both unsigned data-aware IPA products are generated reproducibly.

## What still requires user-owned data and hardware

- Actual full game-runtime execution with a licensed TFE data set.
- Actual full game-runtime execution with a licensed TSE data set.
- Verification that every required `.gro` archive is present.
- First menu or gameplay frame.
- Physical-device audio, lifecycle, input, and thermal behavior.

## Next architecture gate

The upstream menu and application loop are not part of the five current runtime archives. They live in a twelve-source `SeriousSam` application target containing command-line, menu, display-mode, splash, window, credits, and rendering-loop code.

The next coordinated task is to create a static iOS application layer, replace `MainWindow.cpp` and `SplashScreen.cpp` with UIKit-owned adapters, and expose explicit initialize, tick, render, suspend, resume, and shutdown entry points instead of importing the desktop executable loop unchanged.
