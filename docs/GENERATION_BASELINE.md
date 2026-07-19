# Generated-source baseline

This baseline is tied to the pinned SeriousSamClassic revision:

`80b9893e5b74e5a2160eaf63e6d6b3f3981dfbbd`

## Host environment

- macOS GitHub Actions arm64 runner
- Apple Clang 17.0.0 (`clang-1700.0.13.5`)
- Flex 2.6.4
- GNU Bison 3.8.2

## Entity Class Compiler

The TFE and TSE source trees currently produce byte-identical native `ecc-se` binaries.

| Encounter | SHA-256 |
|---|---|
| TFE | `1e356076e9a4212a817c5b222e204bd0df1bfe15003aed8f9dd8eec8e93b481a` |
| TSE | `1e356076e9a4212a817c5b222e204bd0df1bfe15003aed8f9dd8eec8e93b481a` |

Identical binaries are useful evidence that the host-tool implementation has not diverged between encounters. They remain built separately so later upstream changes cannot silently introduce divergence.

## Complete generated corpus

The generation gate runs ECC over every `.es` input found under `Engine/Classes`, `Entities`, and `EntitiesMP`, then runs the engine and Ska Flex/Bison pairs.

| Encounter tree | Entity inputs | Generated C/C++ headers and sources |
|---|---:|---:|
| TFE | 271 | 821 |
| TSE | 271 | 821 |

The broad corpus intentionally includes both standard and MP entity directories for drift detection. Actual runtime registration is encounter-scoped.

## Encounter-scoped entity registries

| Encounter | Scanned packages | Registered `<Class>_DLLClass` exports |
|---|---|---:|
| TFE | `Engine/Classes`, `Entities` | 123 |
| TSE | `Engine/Classes`, `EntitiesMP` | 146 |

The generated registry translation units reference every selected export explicitly. This provides deterministic static-link retention and replaces reliance on `dlopen(NULL)` plus `dlsym` for entity classes on iOS.

## Update rule

Any change to the pinned upstream revision, generator versions, entity counts, registry counts, or ECC hashes must be deliberate and explained in the pull request that updates this file. A mismatch is not automatically a regression, but it is always an architecture-review event.
