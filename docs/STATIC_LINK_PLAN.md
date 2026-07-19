# SeriousiOS static-link conversion plan

## Baseline at the pinned upstream revision

Both TFE and TSE currently expose the same build shape:

- 13 CMake targets
- 5 executables
- 7 shared libraries
- 1 static library
- 53 `target_link_libraries` declarations
- 116 textual references to dynamic-loader APIs across runtime and desktop tools

The iOS port must not mechanically preserve all of those targets. It needs one application host and only the runtime libraries required by the selected encounter.

## Runtime lookup seams that matter

### 1. Game module

`SeriousSam/SeriousSam.cpp::InitializeGame` uses `CDynamicLoader` to resolve `GAME_Create`. Upstream already defines a `STATICALLY_LINKED` filename path, but symbol resolution still passes through the Unix dynamic loader.

**iOS contract:** link `Game`/`GameMP` statically and register `GAME_Create` explicitly in `SeriousIOSStaticRegistry`.

### 2. Entity class packages

`Engine/Entities/EntityClass.cpp::Read_t` reads the package and class names from game data, then resolves `<ClassName>_DLLClass`. Under `STATICALLY_LINKED`, it opens the main process and uses `dlsym`.

**iOS contract:** generated registry code must register every compiled `<ClassName>_DLLClass` address. Package names remain meaningful for data compatibility but do not select a runtime library.

### 3. Shader package

`Engine/Graphics/Shader.cpp::Read_t` reads the exported shader function and descriptor names, then resolves both through `CDynamicLoader`.

**iOS contract:** statically compiled shader entry points must be registered by their existing serialized names.

## References that are not part of the initial iOS runtime

The dependency report also finds loader references in WorldEditor, DedicatedServer, GameGUI, Direct3D, Windows OpenGL setup, multimonitor support and import/export tooling. Those targets or source paths should be excluded from the iOS target instead of ported.

OpenGL function-address resolution must be treated separately from game-module loading. The first renderer milestone will use a fixed OpenGL ES interface, so desktop extension probing must not be routed through the gameplay symbol registry.

## Required target transformation

For each selected encounter:

1. Build `ecc-se`, Flex and Bison outputs on the macOS host before cross-compilation.
2. Compile Engine, Entities, Game, Shaders and required audio libraries as static targets.
3. Define `PLATFORM_IOS=1`, `PLATFORM_UNIX=1`, `STATICALLY_LINKED=1` and `USE_PORTABLE_C=1`.
4. Exclude editor, dedicated-server, Direct3D, desktop OpenGL-windowing and system-library discovery paths.
5. Generate a registry translation unit that references every required export, defeating dead stripping without relying on `-all_load` as the primary mechanism.
6. Replace the iOS `CDynamicLoader` implementation with a registry-backed adapter.
7. Link one encounter at a time during early validation. A launcher can select TFE or TSE only after both isolated graphs work.

## Validation gates

A static-link milestone is complete only when CI records:

- the full generated-source manifest;
- the transformed target list;
- the exact static archives produced;
- the registry symbol count and names;
- unresolved-symbol output from a final dry link;
- confirmation that no runtime `.dylib`, `.so` or `.dll` is expected for Game, Entities or Shaders.
