use access_zk::{air::*, *};
use p3_field::PrimeCharacteristicRing;
use p3_matrix::dense::RowMajorMatrix;
use std::{borrow::BorrowMut, sync::OnceLock, time::Instant};

fn fixture() -> (PqSemaphoreWitness, [u8; 128]) {
    // Fixed secrets only in tests, never in a provisioned policy.
    let id = core::array::from_fn(|i| Val::from_u32(1000 + i as u32));
    let index = 37;
    let mut nodes: Vec<Digest> = (0..1 << TREE_DEPTH).map(|i| {
        hash_leaf(core::array::from_fn(|j| Val::from_u32((i * 7 + j + 2000) as u32)))
    }).collect();
    nodes[index] = hash_leaf(id);
    let mut at = index;
    let mut siblings = [[Val::ZERO; 6]; TREE_DEPTH];
    for sibling in &mut siblings {
        *sibling = nodes[at ^ 1];
        nodes = nodes.chunks_exact(2).map(|p| hash_pair(p[0], p[1])).collect();
        at >>= 1;
    }
    let mut context = [0u8; 128];
    context[..24].copy_from_slice(&encode_digest(nodes[0]));
    context[32..64].fill(0x58);
    context[64..80].fill(0x64);
    context[80..96].fill(0x42);
    context[96..100].copy_from_slice(&1u32.to_le_bytes());
    context[100..104].copy_from_slice(&99u32.to_le_bytes());
    context[104..108].copy_from_slice(&1u32.to_le_bytes());
    context[112..].copy_from_slice(&POLICY_ID);
    (membership_witness(id, siblings, index, &context).unwrap(), context)
}
fn sample() -> &'static (Vec<u8>, Vec<u8>, [u8; 128]) {
    static DATA: OnceLock<(Vec<u8>, Vec<u8>, [u8; 128])> = OnceLock::new();
    DATA.get_or_init(|| {
        let (w, ctx) = fixture();
        let start = Instant::now();
        let bytes = prove(&w, &ctx).unwrap();
        eprintln!("MEASURE proof_bytes={} generation_ms={:.3} trace_columns={}",
                  bytes.len(), start.elapsed().as_secs_f64() * 1000.0, trace_width());
        (bytes, encode_public_inputs(&pack_public_inputs(&w)), ctx)
    })
}

#[test]
fn authorized_member_verifies() {
    let (p, inputs, ctx) = sample();
    let start = Instant::now();
    verify(p, inputs, ctx).unwrap();
    eprintln!("MEASURE verify_ms={:.3}", start.elapsed().as_secs_f64() * 1000.0);
}
#[test]
fn private_proofs_are_randomized_and_hiding_is_enabled() {
    let (w, ctx) = fixture();
    let other = prove(&w, &ctx).unwrap();
    assert_ne!(&other, &sample().0);
    let (proof, _): (config::Proof, _) = postcard::take_from_bytes(&other).unwrap();
    assert!(proof.commitments.random.is_some());
    assert!(proof.opened_values.random.is_some());
    assert_eq!(proof.degree_bits, 9);
}
#[test]
fn incorrect_secret_or_membership_path_rejected() {
    let (w, ctx) = fixture();
    let mut secret = w.id; secret[0] += Val::ONE;
    assert!(membership_witness(secret, w.siblings, 37, &ctx).is_err());
    let mut siblings = w.siblings; siblings[0][1] += Val::ONE;
    assert!(membership_witness(w.id, siblings, 37, &ctx).is_err());
    assert!(membership_witness(w.id, w.siblings, 36, &ctx).is_err());
}
#[test]
fn altered_context_fields_and_revoked_registry_rejected() {
    let (p, inputs, ctx) = sample();
    for offset in [0, 32, 64, 80, 96, 100, 104, 108, 112] {
        let mut changed = *ctx; changed[offset] ^= 1;
        assert!(verify(p, inputs, &changed).is_err(), "context offset {offset}");
    }
    // Epoch/root changes invalidate both stale witness and stale proofs.
    let (w, _) = fixture();
    let mut revoked = *ctx; revoked[0] ^= 1; revoked[96] = 2;
    assert!(membership_witness(w.id, w.siblings, 37, &revoked).is_err());
}
#[test]
fn altered_public_fields_rejected() {
    let (p, inputs, ctx) = sample();
    for offset in [0, 24, 48, 72, 96] {
        let mut changed = inputs.clone(); changed[offset] ^= 1;
        assert!(verify(p, &changed, ctx).is_err());
    }
}
#[test]
fn malformed_encoding_and_oversized_proof_rejected() {
    let (p, inputs, ctx) = sample();
    for length in [0, 1, 20, p.len()/2] {
        assert!(verify(&p[..length], inputs, ctx).is_err());
    }
    let mut trailing = p.clone(); trailing.push(0);
    assert!(verify(&trailing, inputs, ctx).is_err());
    assert!(verify(&vec![0; MAX_PROOF_SIZE+1], inputs, ctx).is_err());
    let mut noncanonical = inputs.clone();
    noncanonical[..4].copy_from_slice(&PRIME.to_le_bytes());
    assert!(verify(p, &noncanonical, ctx).is_err());
    // Hiding metadata is mandatory, independently of byte randomization tests.
    let (mut missing_mask, _): (config::Proof, _) = postcard::take_from_bytes(p).unwrap();
    missing_mask.commitments.random = None;
    assert!(verify(&postcard::to_allocvec(&missing_mask).unwrap(), inputs, ctx).is_err());
    let (mut wrong_degree, _): (config::Proof, _) = postcard::take_from_bytes(p).unwrap();
    wrong_degree.degree_bits = 8;
    assert!(verify(&postcard::to_allocvec(&wrong_degree).unwrap(), inputs, ctx).is_err());
}
#[test]
fn modified_commitment_rejected_by_actual_verifier() {
    let (p, inputs, ctx) = sample();
    // Mutate a digest while preserving proof encoding.
    let mut changed = p.clone();
    changed[8] ^= 1;
    assert!(verify(&changed, inputs, ctx).is_err());
}
#[test]
fn selectors_cannot_skip_membership_or_root_check() {
    let (w, _) = fixture();
    let public = pack_public_inputs(&w);
    let width = trace_width();
    let mut values = build_trace_values(&w);
    let trace = RowMajorMatrix::new(values.clone(), width);
    p3_air::check_constraints(&build_air(), &trace, &public);
    // A valid Poseidon2 trace with all-padding selectors satisfied upstream's
    // conditional checks. Our fixed schedule rejects this attempted bypass.
    for row in values.chunks_exact_mut(width) {
        let c: &mut PqSemaphoreCols<Val> = row.borrow_mut();
        c.is_leaf=Val::ZERO; c.is_merkle_hop=Val::ZERO; c.is_root_check=Val::ZERO;
        c.is_nullifier=Val::ZERO; c.is_scope=Val::ZERO; c.is_padding=Val::ONE;
    }
    let bad = RowMajorMatrix::new(values, width);
    assert!(std::panic::catch_unwind(|| p3_air::check_constraints(&build_air(), &bad, &public)).is_err());
}

