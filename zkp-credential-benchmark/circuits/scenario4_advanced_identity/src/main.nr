// Scenario 4: Advanced Identity Proof
// 16 attributes: multi-field validation, a Poseidon hash
// commitment over all 16 fields, and a Merkle membership proof
// that the resulting credential commitment belongs to a
// publicly known registry of issued credentials (depth-4 tree).

use poseidon::poseidon::bn254::{hash_2, hash_16};

// Manually recompute a Merkle root from a leaf, its sibling path,
// and the path directions (0 = leaf is left child, 1 = leaf is right child).
fn compute_merkle_root(leaf: Field, index_bits: [bool; 4], path: [Field; 4]) -> Field {
    let mut current = leaf;
    for i in 0..4 {
        let sibling = path[i];
        current = if !index_bits[i] {
            hash_2([current, sibling])
        } else {
            hash_2([sibling, current])
        };
    }
    current
}

fn main(
    // 16 private identity/credential attributes
    fields: [Field; 16],
    // Public predicate thresholds (applied to the first two fields:
    // age and income, by convention of the credential schema)
    minimum_age: pub Field,
    minimum_income: pub Field,
    // Merkle membership proof that this credential was actually issued
    merkle_path: [Field; 4],
    merkle_index_bits: [bool; 4],
    registry_root: pub Field,
) {
    // Multi-field validation (range checks on two representative fields)
    assert(fields[0] as u64 >= minimum_age as u64);
    assert(fields[1] as u64 >= minimum_income as u64);

    // Poseidon commitment over all 16 attributes
    let leaf = hash_16(fields);

    // Merkle membership verification against the public registry root
    let computed_root = compute_merkle_root(leaf, merkle_index_bits, merkle_path);
    assert(computed_root == registry_root);
}

#[test]
fn test_passes_for_valid_membership_and_predicates() {
    let fields: [Field; 16] = [
        25, 5000, 233, 2, 700, 4, 3, 6,
        1, 2, 3, 4, 5, 6, 7, 8,
    ];
    let leaf = hash_16(fields);

    // Build a tiny depth-4 tree by hand for the test: leaf is always
    // combined with fixed dummy siblings, walking left at every level.
    let sibling: Field = 999;
    let level1 = hash_2([leaf, sibling]);
    let level2 = hash_2([level1, sibling]);
    let level3 = hash_2([level2, sibling]);
    let root = hash_2([level3, sibling]);

    main(
        fields,
        18,
        3000,
        [sibling, sibling, sibling, sibling],
        [false, false, false, false],
        root,
    );
}
