# SeriousiOS UIKit host baseline

## Proven revision

- SeriousiOS branch revision: `352d9c2882cfcf99b98638f463d22d8cecb10ab4`
- Pinned SeriousSamClassic revision: `80b9893e5b74e5a2160eaf63e6d6b3f3981dfbbd`
- Target: `arm64-apple-ios15.0`
- Build products: unsigned `.app` and `.ipa` host shells for TFE and TSE
- Runtime prerequisite: strict no-dead-strip static closure passed for both encounters

## Product results

| Encounter | Product | Architecture | Info.plist |
|---|---|---|---|
| The First Encounter | `SeriousIOS-TFE.app` | Mach-O 64-bit executable arm64 | Valid |
| The Second Encounter | `SeriousIOS-TSE.app` | Mach-O 64-bit executable arm64 | Valid |

### Executable hashes

- TFE: `62034c67334c1d0080a4a9d5e1e7987117d58e2757074a0c8b9c2ff5f382c91b`
- TSE: `091f3caa79a56497709d80f3e33241411d808e953bed297a13e77ae34fbadf8c`

### Unsigned IPA hashes

- TFE: `43f5fed8ebc0d6b5a73779a8b4ac68e628ba775d180c901946ccb05804a2c67c`
- TSE: `60f6311b65e7ca905ec81fc4dee840576da9f4a880984f866dccdd6955f55fa1`

These IPA containers are deliberately unsigned and contain no copyrighted Serious Sam data. They are host-shell artifacts for downstream user-controlled signing and are not yet expected to initialize the engine or reach a game screen.

## Host capabilities included

- `UIApplicationMain` and an application delegate
- Full-screen landscape view controller
- `CAEAGLLayer`-backed view
- OpenGL ES 2 `EAGLContext`
- Color and depth renderbuffers
- Complete framebuffer validation
- Explicit ownership and activation of the EAGL context
- Drawable-size propagation to the Serious Engine SDL compatibility layer
- Presentation callback used by `SDL_GL_SwapWindow`
- Static entity, Game, and shader registration before startup
- Explicit per-encounter sandbox roots for game data, user files, cache, and temporary files
- Native iOS filesystem adapter instead of desktop SDL/Linux path discovery
- Separate bundle identifiers and executables for TFE and TSE
- Reproducible unsigned IPA packaging

## Linked Apple frameworks

The host executables link the platform surface currently required by the port:

- Foundation
- UIKit
- CoreFoundation
- CoreGraphics
- QuartzCore
- OpenGLES
- AudioToolbox
- AVFoundation
- CoreMotion
- GameController
- Security
- SystemConfiguration

## What this proves

Both complete, strict-closure Serious Sam Classic runtime graphs can be embedded in real arm64 UIKit application executables with valid app metadata, explicit sandbox paths, an EAGL-backed presentation surface, and reproducible unsigned IPA containers.

## What this does not prove

- Launch on physical hardware
- Successful engine initialization
- Original data archive discovery or validation
- First menu frame
- Audible audio output
- Touch, gyro, or controller input behavior
- Background and foreground restoration
- Successful signing or installation

The next milestone is a controlled pre-data engine-startup probe. The host will call `SE_InitEngine` only after its paths, registries, EAGL context, and drawable are ready, using an empty game ID so the first checkpoint does not require the proprietary Player class or `.gro` archives.