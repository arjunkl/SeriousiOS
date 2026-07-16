# SeriousiOS application frame-loop baseline

## Proven build revision

- SeriousiOS branch revision: `1a97d4f11fdfd0d9c9a3e33d13d235564d985da7`
- Pinned SeriousSamClassic revision: `80b9893e5b74e5a2160eaf63e6d6b3f3981dfbbd`
- Target: `arm64-apple-ios15.0`
- Strict full-retention closure: passed for TFE and TSE
- Undefined symbols: 0 for both encounters
- Duplicate symbols: 0 for both encounters
- No-data simulator core checkpoint: passed for TFE and TSE

## Device products

| Encounter | Executable SHA-256 | Unsigned IPA SHA-256 |
|---|---|---|
| The First Encounter | `ab52815380d3f9020f4ed9fefd1a13baa82ea4408210fc630de1bd9ffd2c9b72` | `5ba2aac3b10d95de9407cef72647b7b319cebf4f848ecdb2569e4f40616728dd` |
| The Second Encounter | `2628cb128a2238f9416b30678f004212f423fe75a84e1bc8c75b484e4fe62d16` | `a37bfba32be4f8d55957d3654ff6b70034db92b73b1bcbf2e36b12bb184f44bb` |

The IPAs are unsigned and contain no copyrighted Serious Sam data.

## Six-archive application graph

Each encounter now contains six complete static archives:

TFE:

- `libengine_safemath.a`
- `libEngine.a`
- `libGame.a`
- `libShaders.a`
- `libEntities.a`
- `libSeriousIOSApplication.a`

TSE:

- `libengine_safemathMP.a`
- `libEngineMP.a`
- `libGameMP.a`
- `libShadersMP.a`
- `libEntitiesMP.a`
- `libSeriousIOSApplicationMP.a`

The application archive contains the upstream command-line, level-list, credits, GL settings, LCD drawing, menu, menu-gadget, menu-printing, and `SeriousSam.cpp` application code. UIKit-owned adapters replace the desktop main-window and splash implementations.

## Application lifecycle API

The static application layer exposes a host-controlled C API:

- `SeriousIOS_ApplicationInitialize`
- `SeriousIOS_ApplicationFrame`
- `SeriousIOS_ApplicationSuspend`
- `SeriousIOS_ApplicationResume`
- `SeriousIOS_ApplicationShutdown`
- `SeriousIOS_ApplicationIsInitialized`
- `SeriousIOS_ApplicationGetError`

Initialization reuses the upstream `Init` path and therefore includes:

- SDL-compatible platform initialization
- Explicit iOS executable and sandbox paths
- Serious Engine initialization with the encounter identifier
- default fonts and translations
- user-directory locking
- statically linked Game creation
- LCD, console, controls, player profiles, menu, GL-settings, level-list, and demo-list setup
- display-mode and viewport creation through the UIKit/EAGL adapters

## UIKit frame ownership

When the encounter sentinel is absent, the host continues to run the proprietary-data-free core Engine checkpoint and displays the import interface.

When validated user-owned data is present on a clean launch:

1. The host calls `SeriousIOS_ApplicationInitialize` after the EAGL drawable is ready.
2. UIKit creates a `CADisplayLink` at 60 frames per second.
3. Each active frame calls `SeriousIOS_ApplicationFrame` on the main run loop.
4. The upstream application updates input state, menu state, simulation, menus, console, and rendering through `DoGame`.
5. The existing viewport swaps through the SeriousiOS EAGL presentation callback.
6. The startup overlay is hidden after the first successful application frame.

UIKit remains the owner of process lifetime and frame scheduling. The desktop `main`, `WinMain`, `SubMain`, and blocking message loop are not invoked.

## Lifecycle behavior

- Entering the background calls `SeriousIOS_ApplicationSuspend` and pauses the local game state.
- Returning to the foreground calls `SeriousIOS_ApplicationResume`.
- Application termination calls the upstream cleanup sequence through `SeriousIOS_ApplicationShutdown`.
- Application state and captured errors are written to `application-runtime-checkpoint.txt` in the encounter temporary sandbox.

Checkpoint states include:

- `starting`
- `initialized`
- `suspended`
- `failed`
- `stopped`

## What is proven

- Every upstream runtime and application source compiles for arm64 iPhoneOS and arm64 iPhone Simulator.
- The complete six-archive graph closes with dead stripping disabled.
- Both UIKit hosts compile and package with the frame-loop and lifecycle APIs.
- Both no-data simulator applications still execute the real core Engine initialization checkpoint successfully.

## What still requires a licensed physical-device test

- Full upstream application initialization against complete original TFE data.
- Full upstream application initialization against complete original TSE data.
- The first rendered menu frame on a physical iPhone.
- Verification of menu scaling and viewport geometry at iPhone aspect ratios.
- Audible audio output, foreground restoration, and sustained frame pacing.
- Touch, gyro, and GameController integration.

The next runtime gate is the first licensed-data launch on an iPhone. The visible overlay and sandbox checkpoint file distinguish application initialization failure from a frame-loop failure, and include the captured legacy error string when available.
