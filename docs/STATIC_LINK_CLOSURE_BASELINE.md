# SeriousiOS static link closure baseline

## Proven revision

- SeriousiOS branch revision: `6b6932cb1588fa2eec08e782745a382b65980c4e`
- Pinned SeriousSamClassic revision: `80b9893e5b74e5a2160eaf63e6d6b3f3981dfbbd`
- Target: `arm64-apple-ios15.0`
- SDK: Apple `iphoneos`
- Link mode: every runtime archive force-loaded into one executable per encounter

## Closure result

| Encounter | Link status | Undefined symbols | Duplicate symbols | Product |
|---|---:|---:|---:|---|
| The First Encounter | 0 | 0 | 0 | Mach-O 64-bit executable arm64 |
| The Second Encounter | 0 | 0 | 0 | Mach-O 64-bit executable arm64 |

### Product hashes

- TFE: `b72b46554aadf3a0738a15747b68515e25ea26fb00c782cc8b2d338ada5c95bf`
- TSE: `6bf6f2026e6dbd222fd4d2280996422fc57da3c7bb27a23a11bebcccf770de9d`

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
- The SeriousiOS SDL compatibility layer provides the exact platform-service symbol surface required for closure.

## What this proves

Both complete Serious Sam Classic runtime graphs can be compiled and linked as self-contained arm64 iPhoneOS executables without unresolved or duplicate symbols.

## What this does not prove

- UIKit application lifecycle and scene startup
- EAGL or Metal-backed drawable creation and presentation
- Successful engine initialization with original game data
- Audio playback
- Touch, gyro, or GameController runtime behavior
- Foreground/background restoration
- IPA signing or installation

The next milestone is a minimal UIKit host that links one encounter at a time, supplies a real render surface and bundle/document paths, registers static modules, and reaches a controlled engine-startup checkpoint before loading copyrighted game data.
