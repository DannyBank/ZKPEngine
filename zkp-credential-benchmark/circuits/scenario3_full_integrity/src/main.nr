// Scenario 3: Full Credential Integrity
// 8 attributes: range checks combined with a Poseidon hash
// commitment check (proves the 8 attributes match a publicly
// known credential commitment issued earlier, without revealing
// the attributes themselves).

use poseidon::poseidon::bn254::hash_8;

fn main(
    // 8 private credential attributes
    age: Field,
    income: Field,
    country_code: Field,
    membership_tier: Field,
    credit_score: Field,
    years_employed: Field,
    education_level: Field,
    residency_years: Field,
    // Public predicate thresholds
    minimum_age: pub Field,
    minimum_income: pub Field,
    minimum_credit_score: pub Field,
    // Public commitment issued by the credential issuer at enrollment time
    credential_commitment: pub Field,
) {
    // Range checks
    assert(age as u64 >= minimum_age as u64);
    assert(income as u64 >= minimum_income as u64);
    assert(credit_score as u64 >= minimum_credit_score as u64);

    // Poseidon hash commitment check: the 8 attributes must hash
    // to the credential commitment the issuer published on-chain.
    let computed_commitment = hash_8([
        age, income, country_code, membership_tier,
        credit_score, years_employed, education_level, residency_years,
    ]);
    assert(computed_commitment == credential_commitment);
}

#[test]
fn test_passes_when_commitment_and_predicates_match() {
    let attrs = [25, 5000, 233, 2, 700, 4, 3, 6];
    let commitment = hash_8(attrs);
    main(25, 5000, 233, 2, 700, 4, 3, 6, 18, 3000, 600, commitment);
}
