# SeriousiOS core startup checkpoint

## Build evidence

- SeriousiOS branch revision: `9e85fb42365bf8573f963c1cf0ce83389db6cde5`
- Pinned SeriousSamClassic revision: `80b9893e5b74e5a2160eaf63e6d6b3f3981dfbbd`
- Target: `arm64-apple-ios15.0`
- TFE UIKit executable SHA-256: `d25e1d90f0ae3b464dbbe29c47b4327f6a1aa953f03a5529244842a0e6215a66`
- TSE UIKit executable SHA-256: `dcb6ac8cfcf528d89146bec775af440f4b536f220ea94e05c11ff5d8949a552d`
- TFE unsigned IPA SHA-256: `378ded6ae23b17a268f4d01ad5d1cd7f5465930c5ffcd8fee5630ca20a452f0c`
- TSE unsigned IPA SHA-256: `5754b1ca61955f0e6fd5ae2f6ac6a662c555a6e227b4bc6125fdc16b8354c6bf`

Both encounters pass the strict full-retention static link gate with zero undefined symbols and zero duplicate symbols before the UIKit shells are packaged.

## Checkpoint behavior

The host performs the following sequence:

1. Creates per-encounter GameData, user, cache, and temporary directories in the iOS sandbox.
2. Registers all static entity, Game, and shader exports.
3. Creates and validates an OpenGL ES 2 framebuffer backed by `CAEAGLLayer`.
4. Activates the EAGL context.
5. Calls `SE_InitEngine` with an empty game ID.

The empty game ID is deliberate. It exercises the core Engine, graphics, input, timer, filesystem, and sound scaffolding while stopping before Network and `Player.ecl` require original Serious Sam game data.

## Expected device screen

The app begins with a visible diagnostic overlay:

- `Preparing core engine checkpoint…`
- `Starting core engine without game data…`

A successful checkpoint changes the message to:

- `Core engine initialized`
- `Waiting for original game data import`

A caught startup exception changes the message to:

- `Core engine startup failed`
- followed by the captured error text

A process crash, freeze, or immediate termination before either final message is also a failed checkpoint and should be accompanied by the device crash log when available.

## Test constraints

- The IPA is unsigned and must be signed by the tester using AltStore, Xcode, or another user-controlled signing method.
- No copyrighted `.gro` archives are bundled.
- TFE and TSE have separate bundle identifiers and sandbox directories, so both may be installed independently after signing.
- This checkpoint does not attempt to show a menu or run gameplay.

## Pass criterion

The milestone passes only after at least one physical iPhone reaches the `Core engine initialized` message for each encounter without crashing or freezing.

The following milestone will add user-controlled original-data import and validate the required encounter sentinel archive before attempting Game and Player initialization.