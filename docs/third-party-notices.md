# Third-party source and licenses

| Source | Location and license |
| --- | --- |
| zkmcu | selected reference files in vendor/zkmcu, commit 69b59e6b999ed69c5663878486f425cf8ed8fd14; MIT OR Apache-2.0, upstream license files retained; see vendor/zkmcu/README.md |
| Niek-Kamer Plonky3 fork | vendor/Plonky3, commit 6ffc1fbe46637dd5d62a6b3f423546a4c04b12d6; upstream MIT/Apache license files retained |
| JD9853 LCD driver | firmware/components/esp_lcd_jd9853; copied from the Waveshare demo with Espressif Apache-2.0 SPDX notices retained; see its SOURCE.md |
| Bitmap font | firmware/include/display_font.h; copied from the earlier local project; no author/license notice was found in the file, so provenance and redistribution permission remain unresolved |
| AXS5106 protocol/pins | Waveshare reference archive in original .reference; touch header credits Espressif, Apache-2.0; attribution retained in new polling adapter |
| Rust/Cargo dependencies | exact resolved versions/checksums in Cargo.lock; local downloads retain package license metadata |

The adapted AIR preserves zkmcu attribution. Its custom schedule, public scope, masking dimensions
and hiding configuration are local modifications; upstream cryptographic audit claims must not
be interpreted as an audit of these modifications.

The zkmcu directory is a reference-source subset, not an independently buildable
copy of the complete upstream workspace. Its original Git metadata and unrelated
applications are not included. The separately pinned Plonky3 source provides the
actual Cargo dependencies. No global Git or Rust toolchain settings are changed.

A documentation-only local edit in Plonky3's
`air/src/symbolic/variable.rs` removes an unrelated implementation citation. The
degree calculation and executable code are unchanged from the pinned revision.

The original project code is licensed under the top-level MIT license, copyright
2026 Luis Alejandro Mata. Upstream sources retain their own copyright and license
notices. The copied bitmap font's provenance remains unresolved; the project MIT
license does not assign new rights to that separately attributed asset.

The publication exporter retains upstream license files and copies source trees
without nested .git metadata.

