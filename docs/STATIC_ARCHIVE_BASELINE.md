# Static arm64 iOS archive baseline

This baseline is tied to SeriousSamClassic commit:

`80b9893e5b74e5a2160eaf63e6d6b3f3981dfbbd`

The runtime-only Xcode graphs configure for `iphoneos`, `arm64`, and an iOS 15.0 deployment target. Every configured runtime target now compiles independently as a static archive.

## The First Encounter

| Target | Archive | Size | SHA-256 |
|---|---|---:|---|
| `Engine` | `libEngine.a` | 3,504,456 bytes | `33fcbffb4c570a65e7a612adac5565f8951a2de87b30c6b2cfca11d8d7c63d3c` |
| `Entities` | `libEntities.a` | 4,430,336 bytes | `8e763d053cfd9ee78cdadb0a45f88f905f9637ef85392aea20f17de62e16bcfb` |
| `Game` | `libGame.a` | 424,880 bytes | `1fb2510a1e707572e387235150a6292b08a38cf04c29af666249372d2898f3e5` |
| `Shaders` | `libShaders.a` | 82,696 bytes | `388a493a54d09dc491c9602a0f10220cb6684b570735f651298a455e4c7f3a02` |
| `engine_safemath` | `libengine_safemath.a` | 341,672 bytes | `0b38270cce068c253f9b74dc55bdd49e31c7caa736198ed08f3d381a56f0c2d0` |

## The Second Encounter

| Target | Archive | Size | SHA-256 |
|---|---|---:|---|
| `EngineMP` | `libEngineMP.a` | 3,504,464 bytes | `fe4d1583dba2bd87361a87e491855f00dfc1ef6f0a526d0f59c17a29c079a83f` |
| `EntitiesMP` | `libEntitiesMP.a` | 5,623,320 bytes | `3a2dbfdeb7c6447bb56f20f4db5f8e3e24f1aab7038e54b3a5331c64ce3d391d` |
| `GameMP` | `libGameMP.a` | 419,752 bytes | `9768717bd44b3b3df76f47fac16ff1f47ac01e6c77b533da06ba39d3a9d7cc6a` |
| `ShadersMP` | `libShadersMP.a` | 82,696 bytes | `388a493a54d09dc491c9602a0f10220cb6684b570735f651298a455e4c7f3a02` |
| `engine_safemathMP` | `libengine_safemathMP.a` | 341,672 bytes | `0b38270cce068c253f9b74dc55bdd49e31c7caa736198ed08f3d381a56f0c2d0` |

The matching safemath and shader hashes across encounters are expected and useful. Their source sets are currently identical. Engine differs only slightly, while the larger TSE Entities archive reflects its expanded `EntitiesMP` package.

## Portability repairs required to reach this baseline

The coordinated compile pass identified and repaired shared engine issues rather than fixing targets one at a time:

- iOS-specific platform detection separated from macOS;
- portable C selected and x86 assembly disabled;
- Microsoft-extension-compatible 64-bit type handling;
- desktop-only `malloc.h` excluded;
- ARMv7 inline NEON assembly excluded on arm64 iOS;
- bundled zlib's `Byte` typedef restored for iOS;
- host ECC generation separated from cross-compilation;
- Game, Entities, Shaders, Engine and safemath converted to static runtime targets.

## Next validation boundary

Archive success proves compilation, but not final application closure. The next gate must force-load the complete encounter archive set into an iPhoneOS link, include explicit Game, entity and shader registries, and record every unresolved platform or third-party symbol in one coordinated linker report.
