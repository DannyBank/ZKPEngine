use poseidon::poseidon::bn254::hash_8;
fn main(fields: [Field; 8]) {
    let h = hash_8(fields);
    println(f"HASH={h}");
}
