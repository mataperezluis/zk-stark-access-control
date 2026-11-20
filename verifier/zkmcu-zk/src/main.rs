mod wallet;
mod memory;
fn main() {
    if wallet::run(&std::env::args().collect::<Vec<_>>()).is_err() {
        eprintln!("operation failed; check command, files, witness, policy and canonical encodings");
        std::process::exit(1);
    }
}

