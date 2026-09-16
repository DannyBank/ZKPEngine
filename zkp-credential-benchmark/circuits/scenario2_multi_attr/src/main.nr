// Scenario 2: Multi-Attribute Disclosure
// 4 attributes, moderate predicate complexity:
// two range checks plus two set-membership (whitelist) lookups.

fn is_member(value: Field, allowed_set: [Field; 3]) -> bool {
    let mut found = false;
    for i in 0..3 {
        found |= value == allowed_set[i];
    }
    found
}

fn main(
    age: Field,
    income: Field,
    country_code: Field,
    membership_tier: Field,
    minimum_age: pub Field,
    minimum_income: pub Field,
    allowed_countries: pub [Field; 3],
    allowed_membership_tiers: pub [Field; 3],
) {
    // Range check 1: age
    assert(age as u64 >= minimum_age as u64);

    // Range check 2: income
    assert(income as u64 >= minimum_income as u64);

    // Set-membership lookup 1: country whitelist
    assert(is_member(country_code, allowed_countries));

    // Set-membership lookup 2: membership tier whitelist
    assert(is_member(membership_tier, allowed_membership_tiers));
}

#[test]
fn test_passes_when_all_predicates_satisfied() {
    main(25, 5000, 233, 2, 18, 3000, [1, 44, 233], [1, 2, 3]);
}

#[test(should_fail)]
fn test_fails_when_country_not_whitelisted() {
    main(25, 5000, 999, 2, 18, 3000, [1, 44, 233], [1, 2, 3]);
}
