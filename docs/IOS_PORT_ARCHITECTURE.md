# SeriousiOS port architecture

## Scope

SeriousiOS targets Serious Sam Classic: The First Encounter and The Second Encounter in one iOS application. The application contains no copyrighted game data and imports legally owned `.gro` files.

## Non-negotiable build rules

1. iOS is a distinct platform, not a synonym for macOS.
2. All target code is arm64 and uses portable C/C++; x86 assembly is disabled.
3. Host build tools such as `ecc-se`, Flex, and Bison run on the macOS CI host before target compilation.
4. Engine, entity, game, and shader modules are statically linked and explicitly registered. Runtime `.dll`, `.so`, and desktop plugin discovery are prohibited on iOS.
5. TFE and TSE dependency graphs must pass compile and link-map validation independently before an IPA packaging job is introduced.
6. Full builds are blocked until fast architecture checks pass.

## Source strategy

The modern `tx00100xt/SeriousSamClassic` tree is the engine base. The Android port is a reference for GLES2, mobile lifecycle, input mapping, and static-link adaptations. `arjunkl/eDukeiOS` is the reference for UIKit touch controls, CoreMotion gyro, sustained aim-fire, layout editing, and app lifecycle fixes. Exact revisions are recorded in `Dependencies.lock`.

## Build stages

### Stage A: source audit

Checkout pinned source revisions and verify known desktop assumptions remain visible. The audit fails loudly when upstream structure changes.

### Stage B: host tools

Build `ecc-se` for the macOS host. Generate entity sources and parser/scanner outputs once, then preserve a manifest of generated files.

### Stage C: target static libraries

Cross-compile arm64 iOS libraries in this order:

1. bundled zlib/ogg/vorbis or pinned XCFramework equivalents
2. engine safe-math library
3. Engine
4. Entities / EntitiesMP
5. Game / GameMP
6. Shaders / ShadersMP
7. Serious Sam executable-facing glue

No target may rely on unresolved `dynamic_lookup` symbols.

### Stage D: native shell

Create a UIKit application shell with an SDL-compatible render surface, filesystem importer, audio session, lifecycle coordinator, and game selector.

### Stage E: controls

Connect `SeriousIOSInputBridge` to the engine controls. The bridge owns state synchronization while UIKit owns gesture interpretation. Touch and gyro deltas are consumed once per engine poll; held actions remain active until explicitly released.

## Validation gates

A milestone is accepted only when its outputs can be inspected without beginning the next stage. Required artifacts include CMake cache, target list, generated-source manifest, complete linker commands, unresolved-symbol report, and dependency graph.
