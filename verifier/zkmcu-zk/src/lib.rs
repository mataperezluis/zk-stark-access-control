#![no_std]
extern crate alloc;
#[cfg(feature = "prover")]
use alloc::vec::Vec;
use p3_field::{PrimeCharacteristicRing, PrimeField32};
use p3_uni_stark::StarkGenericConfig;
pub mod air;
pub mod config;

pub const MAX_PROOF_SIZE: usize = 524288;
pub const CONTEXT_BYTES: usize = 128;
pub const PUBLIC_BYTES: usize = air::NUM_PUBLIC_INPUTS * 4;
pub const POLICY_ID: [u8; 16] = *b"ZK-P3-ACCESS-V1!";
pub const PRIME: u32 = 0x78000001;
pub type Digest = [air::Val; air::DIGEST_WIDTH];

pub fn encode_digest(d: Digest) -> [u8; 24] {
    let mut out = [0u8; 24];
    for (i, v) in d.iter().enumerate() { out[i*4..i*4+4].copy_from_slice(&v.as_canonical_u32().to_le_bytes()); }
    out
}
pub fn decode_digest(bytes: &[u8]) -> Result<Digest, &'static str> {
    if bytes.len() != 24 { return Err("digest size"); }
    let mut out = [air::Val::ZERO; air::DIGEST_WIDTH];
    for (i, b) in bytes.chunks_exact(4).enumerate() {
        let v = u32::from_le_bytes(b.try_into().unwrap());
        if v >= PRIME { return Err("noncanonical field"); }
        out[i] = air::Val::new(v);
    }
    Ok(out)
}
pub fn parse_public(bytes: &[u8]) -> Result<[air::Val; air::NUM_PUBLIC_INPUTS], &'static str> {
    if bytes.len() != PUBLIC_BYTES { return Err("public size"); }
    let mut out = [air::Val::ZERO; air::NUM_PUBLIC_INPUTS];
    for (i, b) in bytes.chunks_exact(24).enumerate() {
        out[i*6..i*6+6].copy_from_slice(&decode_digest(b)?);
    }
    Ok(out)
}

pub fn membership_witness(secret: Digest, siblings: [Digest; air::TREE_DEPTH], index: usize,
                          context: &[u8]) -> Result<air::PqSemaphoreWitness, &'static str> {
    if context.len() != CONTEXT_BYTES || index >= 1 << air::TREE_DEPTH { return Err("witness shape"); }
    let scope = context_digest(b"scope", context);
    let signal_hash = context_digest(b"operation", context);
    let leaf = air::hash_leaf(secret);
    let direction_bits = core::array::from_fn(|i| (index >> i) & 1 == 1);
    let mut path_digests = [[air::Val::ZERO; 6]; air::TREE_DEPTH];
    let mut current = leaf;
    for level in 0..air::TREE_DEPTH {
        current = if direction_bits[level] { air::hash_pair(siblings[level], current) }
                  else { air::hash_pair(current, siblings[level]) };
        path_digests[level] = current;
    }
    if encode_digest(current) != context[..24] { return Err("credential not in registry"); }
    Ok(air::PqSemaphoreWitness { id: secret, scope, signal_hash, siblings, direction_bits,
        leaf, merkle_root: current, nullifier: air::hash_pair(secret, scope),
        scope_hash: air::hash_pair(scope, signal_hash), path_digests })
}
/// Domain-separated, unbiased hash-to-field via BLAKE3 XOF rejection sampling.
pub fn context_digest(domain: &[u8], context: &[u8]) -> Digest {
    let mut h = blake3::Hasher::new_derive_key("esp32-s3-private-maintenance/v1");
    h.update(&(domain.len() as u32).to_le_bytes()); h.update(domain); h.update(context);
    let mut xof = h.finalize_xof();
    let mut out = [air::Val::ZERO; 6];
    for value in &mut out {
        loop {
            let mut b = [0u8; 4]; xof.fill(&mut b);
            let n = u32::from_le_bytes(b);
            if n < PRIME { *value = air::Val::new(n); break; }
        }
    }
    out
}
/// Expected context is reconstructed by the device; it is never trusted from the host.
pub fn check_context(public: &[u8], context: &[u8]) -> Result<(), &'static str> {
    if context.len() != CONTEXT_BYTES || context[112..] != POLICY_ID { return Err("context encoding"); }
    let p = parse_public(public)?;
    if encode_digest(p[..6].try_into().unwrap()) != context[..24] { return Err("root"); }
    if p[12..18] != context_digest(b"operation", context) { return Err("operation binding"); }
    if p[24..30] != context_digest(b"scope", context) { return Err("scope binding"); }
    Ok(())
}
pub fn verify(proof: &[u8], public: &[u8], context: &[u8]) -> Result<(), &'static str> {
    check_context(public, context)?;
    if proof.is_empty() || proof.len() > MAX_PROOF_SIZE { return Err("proof size"); }
    let public = parse_public(public)?;
    let (proof, rest): (config::Proof, _) = postcard::take_from_bytes(proof).map_err(|_| "proof encoding")?;
    if !rest.is_empty() { return Err("trailing proof bytes"); }
    // 256 real rows + 256 random rows. Host cannot choose trace size/security policy.
    if proof.degree_bits != 9 { return Err("trace shape"); }
    let config = config::make_config([[0u8; 32]; 3]); // Verification consumes no RNG.
    if config.is_zk() != 1 { return Err("hiding disabled"); }
    p3_uni_stark::verify(&config, &air::build_air(), &proof, &public)
        .map_err(|_| "invalid STARK")
}

#[cfg(feature = "prover")]
pub fn prove(witness: &air::PqSemaphoreWitness, context: &[u8]) -> Result<Vec<u8>, &'static str> {
    let public = air::pack_public_inputs(witness);
    let public_bytes = air::encode_public_inputs(&public);
    check_context(&public_bytes, context)?;
    let mut seeds = [[0u8; 32]; 3];
    for seed in &mut seeds { getrandom::fill(seed).map_err(|_| "OS RNG failed")?; }
    let config = config::make_config(seeds);
    if config.is_zk() != 1 { return Err("hiding disabled"); }
    let trace = p3_matrix::dense::RowMajorMatrix::new(air::build_trace_values(witness), air::trace_width());
    let proof = p3_uni_stark::prove(&config, &air::build_air(), trace, &public);
    let bytes = postcard::to_allocvec(&proof).map_err(|_| "proof serialization")?;
    if bytes.len() > MAX_PROOF_SIZE { return Err("proof size"); }
    Ok(bytes)
}

