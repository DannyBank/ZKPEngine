// Scenario 1: Minimal Predicate
// 1 attribute, minimal range check.
// Proves: holder's private age satisfies age >= minimum_age,
// without revealing the actual age.

fn main(age: Field, minimum_age: pub Field) {
    let age_u64 = age as u64;
    let minimum_age_u64 = minimum_age as u64;
    assert(age_u64 >= minimum_age_u64);
}

#[test]
fn test_passes_when_age_meets_minimum() {
    main(25, 18);
}

#[test(should_fail)]
fn test_fails_when_age_below_minimum() {
    main(15, 18);
}
