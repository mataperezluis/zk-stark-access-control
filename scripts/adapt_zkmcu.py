"""Reproducible adaptation of zkmcu's membership AIR, retaining upstream license."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root / "vendor/zkmcu/crates/zkmcu-verifier-plonky3/src/pq_semaphore.rs").read_text(encoding="utf-8")
# Remove non-hiding PCS/configuration and its wire wrappers; retain the original AIR and witness code.
start = source.index("type Challenge =")
end = source.index("/// Auxiliary columns", start)
source = source[:start] + source[end:]
start = source.index("// ============================================================================\n// Build a `Config`")
end = source.index("/// Run the audited Poseidon2-", start)
source = source[:start] + source[end:]
drop = ["use p3_challenger::DuplexChallenger;", "use p3_commit::ExtensionMmcs;",
        "use p3_dft::Radix2DitParallel;", "use p3_field::extension::BinomialExtensionField;",
        "use p3_fri::{FriParameters, TwoAdicFriPcs};", "use p3_merkle_tree::MerkleTreeMmcs;",
        "use p3_symmetric::{PaddingFreeSponge, Permutation, TruncatedPermutation};",
        "use p3_uni_stark::{verify, verify_run_to_completion, StarkConfig};", "use crate::Error;"]
for line in drop: source = source.replace(line, "")
source = source.replace("use p3_field::{Dup, Field, PrimeCharacteristicRing};", "use p3_field::{Dup, PrimeCharacteristicRing};\nuse p3_symmetric::Permutation;")
source = source.replace("pub const NUM_TRACE_ROWS: usize = 16;", "pub const NUM_TRACE_ROWS: usize = 256;")
source = source.replace("pub const NUM_PUBLIC_INPUTS: usize = 4 * DIGEST_WIDTH;", "pub const NUM_PUBLIC_INPUTS: usize = 5 * DIGEST_WIDTH;")
source = source.replace("    pub scope_col: [T; DIGEST_WIDTH],", "    pub scope_col: [T; DIGEST_WIDTH],\n    pub hop_count: T,")
source = source.replace("    + DIGEST_WIDTH; // scope_col", "    + DIGEST_WIDTH + 1; // scope_col + hop_count")
# Fixed state machine: all-padding / omitted root / shortened path must be impossible.
marker = "        // 2. Selector booleanity."
schedule = """        builder.when_first_row().assert_one(local.is_leaf);
        builder.when_first_row().assert_zero(local.hop_count);
        builder.when_last_row().assert_one(local.is_padding);
        builder.when_last_row().assert_eq(local.hop_count, Val::from_u32(TREE_DEPTH as u32));
        {
            let mut t = builder.when_transition();
            t.assert_zero(next.is_leaf);
            t.assert_eq(next.is_merkle_hop, local.is_leaf.into() + local.is_merkle_hop.into() - local.is_root_check.into());
            t.assert_eq(next.is_nullifier, local.is_root_check);
            t.assert_eq(next.is_scope, local.is_nullifier);
            t.assert_eq(next.is_padding, local.is_scope.into() + local.is_padding.into());
            t.assert_eq(next.hop_count, local.hop_count.into() + local.is_merkle_hop.into());
        }
        // Scope is public and challenge-specific; the host cannot choose a permanent scope.
        for j in 0..DIGEST_WIDTH {
            builder.assert_eq(local.scope_col[j], public[4 * DIGEST_WIDTH + j]);
        }

"""
source = source.replace(marker, schedule + marker)
source = source.replace("        cols.scope_col = witness.scope;", "        cols.scope_col = witness.scope;\n        cols.hop_count = Val::from_u32(row_idx.saturating_sub(1).min(TREE_DEPTH) as u32);")
source = source.replace("    out[3 * d..4 * d].copy_from_slice(&witness.scope_hash);", "    out[3 * d..4 * d].copy_from_slice(&witness.scope_hash);\n    out[4 * d..5 * d].copy_from_slice(&witness.scope);")
source = source.replace("type Perm = Poseidon2BabyBear<16>;", "")
# Original config import no longer needs the concrete permutation type.
source = source.replace("    Poseidon2BabyBear, BABYBEAR", "    BABYBEAR")
banner = """// Adapted from Niek-Kamer/zkmcu commit 69b59e6b999ed69c5663878486f425cf8ed8fd14.
// MIT OR Apache-2.0; see ../../vendor/zkmcu/LICENSE-MIT and LICENSE-APACHE.
// Local changes: remove non-hiding configuration; 256 base rows; enforce execution
// schedule and depth; bind public scope; use hiding PCS in sibling config.rs.
// Upstream comments below describe its original layout and security claims.

"""
target = root / "verifier/zkmcu-zk/src/air.rs"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(banner + source, encoding="utf-8")
print("Adapted zkmcu AIR with fixed schedule and public scope")

