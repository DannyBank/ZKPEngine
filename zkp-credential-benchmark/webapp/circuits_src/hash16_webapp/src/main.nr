// Browser-facing twin of tools/hash16_helper: identical Poseidon call, but
// returns the hash as a public Field instead of printing it, so NoirJS can
// read it directly from the execution's returnValue.
use poseidon::poseidon::bn254::hash_16;

fn main(fields: [Field; 16]) -> pub Field {
    hash_16(fields)
}

#[test]
fn test_matches_helper() {
    let f = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16];
    assert(main(f) == hash_16(f));
}
