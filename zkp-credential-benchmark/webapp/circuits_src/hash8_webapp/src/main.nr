// Browser-facing twin of tools/hash8_helper: identical Poseidon call, but
// returns the hash as a public Field instead of printing it, so NoirJS can
// read it directly from the execution's returnValue.
use poseidon::poseidon::bn254::hash_8;

fn main(fields: [Field; 8]) -> pub Field {
    hash_8(fields)
}

#[test]
fn test_matches_helper() {
    let f = [1, 2, 3, 4, 5, 6, 7, 8];
    assert(main(f) == hash_8(f));
}
