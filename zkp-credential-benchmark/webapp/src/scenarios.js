// Scenario definitions mirror Chapter 3, Table 3.2 exactly -- same circuits,
// same attribute counts, same predicate logic as the benchmark experiment.
// Each scenario's `fields` array drives the auto-generated form in app.js.

export const SCENARIOS = {
  scenario1: {
    id: "scenario1",
    label: "Scenario 1 — Minimal Predicate",
    description: "1 attribute. Proves age ≥ minimum age, without revealing the age.",
    circuitFile: "circuits/scenario1.json",
    fields: [
      { name: "age", label: "Age", visibility: "private", kind: "field", default: 25 },
      { name: "minimum_age", label: "Minimum age required", visibility: "public", kind: "field", default: 18 },
    ],
  },

  scenario2: {
    id: "scenario2",
    label: "Scenario 2 — Multi-Attribute Disclosure",
    description: "4 attributes: two range checks plus two set-membership (whitelist) checks.",
    circuitFile: "circuits/scenario2.json",
    fields: [
      { name: "age", label: "Age", visibility: "private", kind: "field", default: 25 },
      { name: "income", label: "Income", visibility: "private", kind: "field", default: 5000 },
      { name: "country_code", label: "Country code", visibility: "private", kind: "field", default: 44, hint: "must be one of the allowed countries below" },
      { name: "membership_tier", label: "Membership tier", visibility: "private", kind: "field", default: 2, hint: "must be one of the allowed tiers below" },
      { name: "minimum_age", label: "Minimum age required", visibility: "public", kind: "field", default: 18 },
      { name: "minimum_income", label: "Minimum income required", visibility: "public", kind: "field", default: 3000 },
      { name: "allowed_countries", label: "Allowed country codes", visibility: "public", kind: "field[]", size: 3, default: [1, 44, 233] },
      { name: "allowed_membership_tiers", label: "Allowed membership tiers", visibility: "public", kind: "field[]", size: 3, default: [1, 2, 3] },
    ],
  },

  scenario3: {
    id: "scenario3",
    label: "Scenario 3 — Full Credential Integrity",
    description: "8 attributes: range checks plus a Poseidon commitment check. The commitment is computed automatically from the 8 attributes (exactly as an issuer would have computed it at enrollment) — you don't type it in.",
    circuitFile: "circuits/scenario3.json",
    fields: [
      { name: "age", label: "Age", visibility: "private", kind: "field", default: 25 },
      { name: "income", label: "Income", visibility: "private", kind: "field", default: 5000 },
      { name: "country_code", label: "Country code", visibility: "private", kind: "field", default: 233 },
      { name: "membership_tier", label: "Membership tier", visibility: "private", kind: "field", default: 2 },
      { name: "credit_score", label: "Credit score", visibility: "private", kind: "field", default: 700 },
      { name: "years_employed", label: "Years employed", visibility: "private", kind: "field", default: 4 },
      { name: "education_level", label: "Education level", visibility: "private", kind: "field", default: 3 },
      { name: "residency_years", label: "Residency years", visibility: "private", kind: "field", default: 6 },
      { name: "minimum_age", label: "Minimum age required", visibility: "public", kind: "field", default: 18 },
      { name: "minimum_income", label: "Minimum income required", visibility: "public", kind: "field", default: 3000 },
      { name: "minimum_credit_score", label: "Minimum credit score required", visibility: "public", kind: "field", default: 600 },
    ],
    derivedCommitment: {
      // Poseidon hash_8 over these 8 fields, in this order, matching
      // scripts/generate_synthetic_data.py's gen_scenario3() exactly.
      helperCircuit: "circuits/hash8.json",
      sourceFields: [
        "age", "income", "country_code", "membership_tier",
        "credit_score", "years_employed", "education_level", "residency_years",
      ],
      outputField: "credential_commitment",
      outputLabel: "Credential commitment (Poseidon hash of the 8 attributes, public)",
    },
  },

  scenario4: {
    id: "scenario4",
    label: "Scenario 4 — Advanced Identity Proof",
    description: "16 attributes: a Poseidon commitment plus a depth-4 Merkle membership proof. Click “Generate a valid membership proof” to build a fresh, genuinely valid registry root the same way the thesis's synthetic-data generator does (no real registry exists in this demo).",
    circuitFile: "circuits/scenario4.json",
    fields: [
      { name: "fields", label: "16 identity attributes (fields[0]=age, fields[1]=income by convention)", visibility: "private", kind: "field[]", size: 16, default: [25, 5000, 233, 2, 700, 4, 3, 6, 1, 2, 3, 4, 5, 6, 7, 8] },
      { name: "minimum_age", label: "Minimum age required", visibility: "public", kind: "field", default: 18 },
      { name: "minimum_income", label: "Minimum income required", visibility: "public", kind: "field", default: 3000 },
    ],
    merkle: {
      // Mirrors gen_scenario4() in scripts/generate_synthetic_data.py:
      // leaf = hash_16(fields); walk 4 levels of hash_2 with random
      // siblings and directions to derive a genuinely valid root.
      leafHelperCircuit: "circuits/hash16.json",
      pathHelperCircuit: "circuits/hash2.json",
      depth: 4,
      pathField: "merkle_path",
      indexBitsField: "merkle_index_bits",
      rootField: "registry_root",
      rootLabel: "Registry root (public)",
    },
  },
};

export const SCENARIO_ORDER = ["scenario1", "scenario2", "scenario3", "scenario4"];
