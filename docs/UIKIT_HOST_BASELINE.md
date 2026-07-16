# SeriousiOS UIKit host baseline

## Proven revision

- SeriousiOS branch revision: `b1bad58792d4dc5dd3f8cf3ae175a3db76408707`
- Pinned SeriousSamClassic revision: `80b9893e5b74e5a2160eaf63e6d6b3f3981dfbbd`
- Target: `arm64-apple-ios15.0`
- Build products: unsigned `.app` host shells for TFE and TSE

## Product results

| Encounter | Product | Architecture | Info.plist |
|---|---|---|---|
| The First Encounter | `SeriousIOS-TFE.app` | Mach-O 64-bit executable arm64 | Valid |
| The Second Encounter | `SeriousIOS-TSE.app` | Mach-O 64-bit executable arm64 | Valid |

### Executable hashes

- TFE: `3c45fdbf4985c5c1fd9d8058e804aefc48c2657e18d27eebbb363cc1d7603caf`
- TSE: `56523718780af0194bc03ebf1ee0b15d250d8b2732caca638e23d7d742e752e5`

## Host capabilities included

- `UIApplicationMain` and an application delegate
- Full-screen landscape view controller
- `CAEAGLLayer`-backed view
- OpenGL ES 2 `EAGLContext`
- Color and depth renderbuffers
- Complete framebuffer validation
- Drawable-size propagation to the Serious Engine SDL compatibility layer
- Presentation callback used by `SDL_GL_SwapWindow`
- Static entity, Game, and shader registration before the window is shown
- Separate bundle identifiers and executables for TFE and TSE

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

Both complete Serious Sam Classic static runtime graphs can be embedded in real arm64 UIKit application executables with valid app metadata and an EAGL-backed presentation surface.

## What this does not prove

- Launch on physical hardware
- Engine initialization
- Data archive discovery or validation
- First menu frame
- Audio output
- Touch, gyro, or controller input behavior
- Background and foreground restoration
- Signing, IPA packaging, or installation

The next milestone is a controlled engine-startup probe. The host must provide explicit bundle, Documents, cache, and temporary paths, call the engine initializer on a managed thread, and report a deterministic checkpoint before copyrighted game data is required.
