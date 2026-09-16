use poseidon::poseidon::bn254::hash_2;
fn main(a: Field, b: Field) {
    let h = hash_2([a, b]);
    println(f"HASH={h}");
}
