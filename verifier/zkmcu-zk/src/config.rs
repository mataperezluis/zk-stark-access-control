use alloc::vec::Vec;
use p3_blake3::Blake3;
use p3_challenger::{HashChallenger, SerializingChallenger32};
use p3_commit::ExtensionMmcs;
use p3_dft::Radix2DitParallel;
use p3_field::extension::BinomialExtensionField;
use p3_fri::{FriParameters, HidingFriPcs};
use p3_merkle_tree::MerkleTreeHidingMmcs;
use p3_symmetric::{CompressionFunctionFromHasher, SerializingHasher};
use p3_uni_stark::StarkConfig;
use rand::SeedableRng;
use rand_chacha::ChaCha20Rng;
use crate::air::Val;

type Challenge = BinomialExtensionField<Val, 4>;
type FieldHash = SerializingHasher<Blake3>;
type Compress = CompressionFunctionFromHasher<Blake3, 2, 32>;
type ValMmcs = MerkleTreeHidingMmcs<Val, u8, FieldHash, Compress, ChaCha20Rng, 2, 32, 8>;
type ChallengeMmcs = ExtensionMmcs<Val, Challenge, ValMmcs>;
type Challenger = SerializingChallenger32<Val, HashChallenger<u8, Blake3, 32>>;
type Pcs = HidingFriPcs<Val, Radix2DitParallel<Val>, ValMmcs, ChallengeMmcs, ChaCha20Rng>;
pub type Config = StarkConfig<Pcs, Challenge, Challenger>;
pub type Proof = p3_uni_stark::Proof<Config>;

// zkmcu's 64 queries and 16+17 PoW retained; blowup increased 2 -> 4 for ZK.
// These are NOT a claim of 128-bit security for the complete construction.
fn mmcs(seed: [u8; 32]) -> ValMmcs {
    ValMmcs::new(FieldHash::new(Blake3 {}), Compress::new(Blake3 {}), 0,
                 ChaCha20Rng::from_seed(seed))
}
pub fn make_config(seeds: [[u8; 32]; 3]) -> Config {
    let val_mmcs = mmcs(seeds[0]);
    let challenge_mmcs = ChallengeMmcs::new(mmcs(seeds[1]));
    let params = FriParameters {
        log_blowup: 2, log_final_poly_len: 0, max_log_arity: 1, num_queries: 64,
        commit_proof_of_work_bits: 16, query_proof_of_work_bits: 17,
        mmcs: challenge_mmcs,
    };
    let pcs = Pcs::new(Radix2DitParallel::default(), val_mmcs, params, 4,
                       ChaCha20Rng::from_seed(seeds[2]));
    Config::new(pcs, Challenger::from_hasher(Vec::new(), Blake3 {}))
}

