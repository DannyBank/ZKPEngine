use poseidon::poseidon::bn254::hash_16;
fn main(fields: [Field; 16]) {
    let h = hash_16(fields);
    println(f"HASH={h}");
}
