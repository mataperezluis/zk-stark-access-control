use access_zk::{air::*, *};
use p3_field::PrimeField32;
use serde::{Deserialize, Serialize};
use std::{fs, io::Write, path::Path, time::Instant};
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
type Words = [u32; 6];
#[derive(Serialize, Deserialize)]
struct Registry { epoch: u32, root: Words, leaves: Vec<Words> }
#[derive(Serialize, Deserialize)]
struct Wallet { secret: Words, index: usize, siblings: [Words; TREE_DEPTH], epoch: u32 }
fn words(d: Digest) -> Words { d.map(|v| v.as_canonical_u32()) }
fn field(d: Words) -> Result<Digest> {
    if d.iter().any(|n| *n >= PRIME) { return Err("noncanonical field".into()); }
    Ok(d.map(Val::new))
}
fn random() -> Digest {
    core::array::from_fn(|_| loop {
        let mut b = [0; 4]; getrandom::fill(&mut b).expect("OS RNG");
        let n = u32::from_le_bytes(b);
        if n < PRIME { break Val::new(n); }
    })
}
fn save(path: &Path, data: &impl Serialize) -> Result<()> {
    let mut f = fs::OpenOptions::new().create_new(true).write(true).open(path)?;
    f.write_all(serde_json::to_string_pretty(data)?.as_bytes())?; Ok(())
}
fn tree(leaves: &[Words], index: usize) -> Result<(Digest, [Words; TREE_DEPTH])> {
    if leaves.len() != 1 << TREE_DEPTH || index >= leaves.len() { return Err("registry size".into()); }
    let mut nodes = leaves.iter().copied().map(field).collect::<Result<Vec<_>>>()?;
    let mut at = index;
    let siblings = core::array::from_fn(|_| {
        let sibling = words(nodes[at ^ 1]);
        nodes = nodes.chunks_exact(2).map(|p| hash_pair(p[0], p[1])).collect();
        at >>= 1;
        sibling
    });
    Ok((nodes[0], siblings))
}
fn registry(path: &str) -> Result<Registry> {
    let r: Registry = serde_json::from_slice(&fs::read(path)?)?;
    if words(tree(&r.leaves, 0)?.0) != r.root || r.epoch == 0 { return Err("registry root".into()); }
    Ok(r)
}
pub fn run(args: &[String]) -> Result<()> {
    match args.get(1).map(String::as_str) {
        Some("init") if args.len() == 3 => {
            let out = Path::new(&args[2]);
            fs::create_dir_all(out)?;
            if out.join("registry.json").exists() { return Err("registry exists".into()); }
            let secrets: Vec<_> = (0..4).map(|_| random()).collect();
            // Random fillers have no retained preimages; only the four enrolled secrets are exported.
            let mut leaves: Vec<_> = (0..1 << TREE_DEPTH).map(|_| words(random())).collect();
            for (i, secret) in secrets.iter().enumerate() { leaves[i] = words(hash_leaf(*secret)); }
            let root = tree(&leaves, 0)?.0;
            for (index, secret) in secrets.iter().enumerate() {
                let wallet = Wallet { secret: words(*secret), index, siblings: tree(&leaves, index)?.1, epoch: 1 };
                save(&out.join(format!("credential-{index}.json")), &wallet)?;
            }
            save(&out.join("registry.json"), &Registry { epoch: 1, root: words(root), leaves })?;
            println!("{{\"credentials\":4,\"registry_slots\":1024,\"hiding\":true}}");
        }
        Some("policy-header") if args.len() == 4 => {
            let r = registry(&args[2])?;
            let header = format!("#pragma once\n#include <stdint.h>\n#define ACCESS_POLICY_CONFIGURED 1\n#define ACCESS_POLICY_EPOCH {}u\nstatic const uint8_t ACCESS_POLICY_ROOT[24] = {{{}}};\n",
                r.epoch, encode_digest(field(r.root)?).iter().map(u8::to_string).collect::<Vec<_>>().join(","));
            fs::OpenOptions::new().create_new(true).write(true).open(&args[3])?.write_all(header.as_bytes())?;
            println!("{{\"policy_written\":true}}");
        }
        Some("context") if args.len() == 5 => {
            let r = registry(&args[2])?;
            let mut ctx = [0u8; 128]; ctx[..24].copy_from_slice(&encode_digest(field(r.root)?));
            getrandom::fill(&mut ctx[32..96]).map_err(|_| "OS RNG")?;
            ctx[96..100].copy_from_slice(&r.epoch.to_le_bytes());
            ctx[100..104].copy_from_slice(&1u32.to_le_bytes());
            ctx[104..108].copy_from_slice(&args[3].parse::<u32>()?.to_le_bytes());
            ctx[112..128].copy_from_slice(&POLICY_ID);
            fs::write(&args[4], ctx)?;
            println!("{{\"offline_context\":true}}");
        }
        Some("prove") if args.len() == 6 => {
            let wallet: Wallet = serde_json::from_slice(&fs::read(&args[2])?)?;
            let context = fs::read(&args[3])?;
            if context.len() != CONTEXT_BYTES || u32::from_le_bytes(context[96..100].try_into()?) != wallet.epoch {
                return Err("stale witness or context size".into());
            }
            let siblings_vec = wallet.siblings.into_iter().map(field).collect::<Result<Vec<_>>>()?;
            let siblings = siblings_vec.try_into().map_err(|_| "witness shape")?;
            let w = membership_witness(field(wallet.secret)?, siblings, wallet.index, &context)?;
            let public = encode_public_inputs(&pack_public_inputs(&w));
            let baseline = crate::memory::reset();
            let start = Instant::now();
            let proof = prove(&w, &context)?;
            let generation_ms = start.elapsed().as_secs_f64() * 1000.0;
            let prove_peak = crate::memory::peak_additional(baseline);
            let baseline = crate::memory::reset();
            let start = Instant::now();
            verify(&proof, &public, &context)?;
            let verify_ms = start.elapsed().as_secs_f64() * 1000.0;
            let verify_peak = crate::memory::peak_additional(baseline);
            fs::write(&args[4], &proof)?; fs::write(&args[5], public)?;
            println!("{{\"proof_bytes\":{},\"generation_ms\":{generation_ms:.3},\"self_verify_ms\":{verify_ms:.3},\"prover_additional_heap_peak\":{prove_peak},\"verifier_additional_heap_peak\":{verify_peak},\"hiding\":true}}", proof.len());
        }
        Some("verify") if args.len() == 5 => {
            let proof = fs::read(&args[2])?; let public = fs::read(&args[3])?; let context = fs::read(&args[4])?;
            let baseline = crate::memory::reset(); let start = Instant::now();
            verify(&proof, &public, &context)?;
            println!("{{\"valid\":true,\"verify_ms\":{:.3},\"additional_heap_peak\":{}}}",
                start.elapsed().as_secs_f64() * 1000.0, crate::memory::peak_additional(baseline));
        }
        Some("revoke") if args.len() == 5 => {
            let mut r = registry(&args[2])?; let index: usize = args[3].parse()?;
            if index >= r.leaves.len() { return Err("index".into()); }
            r.leaves[index] = words(random()); r.root = words(tree(&r.leaves, 0)?.0);
            r.epoch = r.epoch.checked_add(1).ok_or("epoch overflow")?;
            save(Path::new(&args[4]), &r)?;
            println!("{{\"registry_revoked\":true,\"epoch\":{}}}", r.epoch);
        }
        Some("refresh") if args.len() == 5 => {
            let r = registry(&args[2])?;
            let mut w: Wallet = serde_json::from_slice(&fs::read(&args[3])?)?;
            if w.index >= r.leaves.len() || words(hash_leaf(field(w.secret)?)) != r.leaves[w.index] {
                return Err("revoked".into());
            }
            w.siblings = tree(&r.leaves, w.index)?.1; w.epoch = r.epoch;
            save(Path::new(&args[4]), &w)?;
            println!("{{\"witness_refreshed\":true}}");
        }
        _ => return Err("usage: init DIR | policy-header REGISTRY HEADER | context REGISTRY OP OUTPUT | prove WALLET CONTEXT PROOF PUBLIC | verify PROOF PUBLIC CONTEXT | revoke REGISTRY INDEX OUTPUT | refresh REGISTRY WALLET OUTPUT".into()),
    }
    Ok(())
}

