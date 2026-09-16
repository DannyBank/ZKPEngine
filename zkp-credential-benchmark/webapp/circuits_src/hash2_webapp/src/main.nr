// Browser-facing twin of tools/hash2_helper: identical Poseidon call, but
// returns the hash as a public Field instead of printing it, so NoirJS can
// read it directly from the execution's returnValue rather than parsing
// stdout (which is not available to a WASM-in-browser prover).
use poseidon::poseidon::bn254::hash_2;

fn main(a: Field, b: Field) -> pub Field {
    hash_2([a, b])
}

#[test]
fn test_matches_helper() {
    assert(main(1, 2) == hash_2([1, 2]));
}
