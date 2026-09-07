fn main(
	my_age: Field,
	min_age: pub Field,
	max_age: pub Field
) {
	let age = my_age as u32;
	let min = min_age as u32;
	let max = max_age as u32;

    assert((age > min) & (age < max));
}