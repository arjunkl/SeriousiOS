# SeriousiOS strict static link closure baseline

## Proven revision

- SeriousiOS branch revision: `352d9c2882cfcf99b98638f463d22d8cecb10ab4`
- Pinned SeriousSamClassic revision: `80b9893e5b74e5a2160eaf63e6d6b3f3981dfbbd`
- Target: `arm64-apple-ios15.0`
- SDK: Apple `iphoneos`
- Link mode: every runtime archive force-loaded into one executable per encounter
- Dead stripping: disabled for the closure audit
- CI reporting: both encounter reports are emitted before the paired gate can fail

## Closure result

| Encounter | Link status | Undefined symbols | Duplicate symbols | Product |
|---|---:|---:|---:|---|
| The First Encounter | 0 | 0 | 0 | Mach-O 64-bit executable arm64 |
| The Second Encounter | 0 | 0 | 0 | Mach-O 64-bit executable arm64 |

### Product hashes

- TFE: `17b5347d9ee763a60aafb0ad3bdf6a00a7ecf4df4358ab34782b8bffce246ff0`
- TSE: `d8f9693b6429eff5094da2f7836af24ddb72035aa7532c3d0f17acb3f8bdcc31`

## Runtime archive set

TFE force-loads:

- `libengine_safemath.a`
- `libEngine.a`
- `libGame.a`
- `libShaders.a`
- `libEntities.a`

TSE force-loads:

- `libengine_safemathMP.a`
- `libEngineMP.a`
- `libGameMP.a`
- `libShadersMP.a`
- `libEntitiesMP.a`

The final links also include generated entity, Game, and shader registries plus the SeriousiOS host-global translation unit.

## Why this is stricter than the earlier baseline

The earlier proof used `-dead_strip`. That verified reachable-section closure but allowed dormant startup, filesystem, error, audio, and lifecycle sections to be discarded before relocation. The strict audit removes dead stripping while force-loading every archive, so every compiled runtime object and all of its referenced platform services must resolve successfully.

This exposed and repaired the remaining platform surface rather than leaving it hidden:

- SDL initialization and custom event allocation
- Periodic timer creation and cancellation
- Base and preference path discovery
- OpenGL ES context creation, activation, attributes, drawable size, and swap interval
- Display-mode and window-state queries
- Audio-device discovery and callback timing
- Joystick discovery and neutral fallback behavior
- Message-box, allocation, formatting, and utility functions

## Structural repairs represented by this baseline

- Runtime `dlopen` and `dlsym` lookup is replaced by an explicit static symbol registry.
- CMake selects static runtime libraries and excludes desktop executables and tools.
- Host-side entity compilation remains separate from the iPhoneOS target build.
- Generated registries follow the actual CMake entity selection and exclude event-only or comment-only support units.
- ARMv7-only assembly paths are excluded from arm64 iOS builds.
- Legacy portability defects in integer declarations, bundled zlib, and desktop headers are patched reproducibly.
- Shader helper functions required across former shared-library boundaries are exported explicitly.
- Header-defined TFE light-coordinate tables use internal linkage.
- The camera and GameAgent initialization globals no longer collide after static flattening.
- Linux and BSD filesystem discovery is replaced by explicit iOS sandbox paths and a native POSIX filesystem adapter.
- The SeriousiOS SDL compatibility layer supplies the complete retained platform-service symbol surface required by both games.

## What this proves

Both complete Serious Sam Classic runtime graphs, including dormant startup and platform objects, can be compiled and linked as self-contained arm64 iPhoneOS executables without unresolved or duplicate symbols.

## What this does not prove

- Successful execution on physical hardware
- Completion of `SE_InitEngine`
- Original game-data discovery or validation
- First menu or gameplay frame
- Audible audio output from the virtual callback bridge
- Touch, gyro, or GameController runtime behavior
- Foreground and background restoration
- Signing or installation

The next milestone is a controlled pre-data engine-startup probe that calls `SE_InitEngine` only after sandbox paths, static registries, and the EAGL drawable are ready.