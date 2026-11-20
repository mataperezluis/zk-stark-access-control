# Publication review

Review date: November 20, 2026. Scope: the standalone `zk-stark-access-control`
application and a source-only export for the accompanying blog post. The surrounding
weather/HMAC workspace is not part of the proposed public repository.

## Private files and publication boundaries

- Local credential JSON files exist under `secrets/`. Their contents must remain private.
- A full 16 MiB original flash backup exists under `artifacts/backup/`. It may contain
  the previous firmware's secrets and is excluded in full, along with other artifacts.
- The generated policy header contains only a public root/epoch. It is excluded
  because readers need their own matching registry and credentials. The working
  header is retained locally.
- `.gitignore` excludes these locations and additional credential/configuration,
  dump, key and build-output patterns. Ignore rules alone do not sanitize history.
- The source export explicitly includes application source, documentation, tests,
  Cargo manifests/lockfile and required vendored sources/licenses. It omits private
  files, installation-specific policy, toolchains, build products and nested Git metadata.
- Local user-specific absolute paths in the historical host-test log were sanitized;
  an unmodified copy is retained under ignored `artifacts/publication-review/`.

## Git history

The surrounding workspace and the publication snapshot have local Git repositories
with no commits or remotes at the time of this review. The publication snapshot has
its own index and `main` branch. Vendored sources are ordinary files without nested
repository metadata. No hosted repository has been created or updated by this review.

## Reproducibility

- The README describes the actual Windows build wrappers and Python 3.12+ setup.
- New users generate credentials and the public policy locally. No private demo
  credentials, flash images or prebuilt firmware are distributed.
- The required Plonky3 path dependencies, selected AIR reference files and upstream
  licenses remain in the publication snapshot. The Cargo workspace contains the
  active host proof package and the embedded static library only.
- Hardware tests are separated from host tests. Policy lifecycle testing is explicitly
  identified as a reflash operation, and the historical neighboring-project isolation
  check is not presented as a standalone validation command.
- Recorded device measurements remain dated historical evidence, not new hardware
  measurements made during this publication review.

## Remaining licensing decisions

There is no top-level license for original application code. A license has not been
chosen on the author's behalf. The copied `firmware/include/display_font.h` also has
no clear author/license notice; resolve its provenance or replace it with an asset
whose redistribution terms are known. The JD9853 driver has Apache-2.0 SPDX notices.
See [third-party notices](third-party-notices.md).

## Verification performed during this review

- Eight Rust security tests passed using the active `access-zk` package in release
  mode with locked, offline dependency resolution. The selector-bypass test's
  intentionally caught constraint panic is an expected passing rejection case.
- Four Python USB framing tests passed. No real-device tests, reflashing or new
  hardware benchmarks were performed during this review.
- The embedded Rust static library rebuilt successfully for
  `xtensa-esp32s3-none-elf`, and the complete PlatformIO firmware build passed.
  The firmware version is explicitly kept at `1` so builds also work in a new Git
  repository without commits or tags.
- The source snapshot contains 612 source/documentation files plus its SHA-256
  publication manifest. Every manifest entry is checked against its file, and the
  staging check verifies ordinary files with no gitlinks or omitted files.
- Cargo dependency resolution passes offline for the Windows host: 70 resolved
  packages and only the two active workspace members.
- Exact comparisons against five local credential secrets and private credential
  file hashes found no copies in the snapshot. Pattern checks for common GitHub,
  OpenAI and AWS tokens and private-key blocks found no matches.
- First-party documentation links resolve within the snapshot. Selected reference
  sources retain their upstream contents; documentation-only vendor changes are
  listed in the third-party notices.
- The exporter was adjusted to omit generated upstream fuzz corpora and agent/editor
  scratch files, in addition to its private-file and build-output exclusions.

## Review limits

This work checks publication hygiene and documented reproducibility. It does not
establish cryptographic security, a complete zero-knowledge guarantee, absence of
all possible secrets, or production readiness. See the [threat model](threat-model.md)
and [cryptographic design](cryptographic-design.md).
