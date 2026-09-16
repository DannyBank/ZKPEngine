// Client-side re-implementation of the Poseidon-derived fields that
// scripts/generate_synthetic_data.py computes offline (via `nargo execute`
// on tools/hash8_helper / hash16_helper / hash2_helper). Here the same
// Poseidon calls run in the browser via NoirJS, using return-value twins
// of those helper circuits (circuits_src/hash*_webapp) so the result can
// be read directly from noir.execute()'s returnValue instead of parsing
// println output, which isn't available to a WASM prover in the browser.
import { loadCircuit, execute } from "./prover.js";

/** Poseidon hash_8 of 8 field values, matching tools/hash8_helper. */
export async function hash8(fields8) {
  const circuit = await loadCircuit("circuits/hash8.json");
  const { returnValue } = await execute(circuit, { fields: fields8.map(String) });
  return returnValue;
}

/** Poseidon hash_16 of 16 field values, matching tools/hash16_helper. */
export async function hash16(fields16) {
  const circuit = await loadCircuit("circuits/hash16.json");
  const { returnValue } = await execute(circuit, { fields: fields16.map(String) });
  return returnValue;
}

/** Poseidon hash_2 of two field values, matching tools/hash2_helper. */
export async function hash2(a, b) {
  const circuit = await loadCircuit("circuits/hash2.json");
  const { returnValue } = await execute(circuit, { a: String(a), b: String(b) });
  return returnValue;
}

/**
 * Builds a genuinely valid depth-4 Merkle membership proof for a leaf,
 * exactly mirroring gen_scenario4() in generate_synthetic_data.py:
 * random siblings and directions, walking hash_2 up to a root. Since this
 * demo has no real issuer-run registry, the "random" root produced here
 * is only valid for the sibling/direction values returned alongside it --
 * which is exactly what the Scenario 4 circuit checks.
 */
export async function buildRandomMerkleProof(leaf, depth = 4) {
  const siblings = [];
  const indexBits = [];
  let current = leaf;
  for (let i = 0; i < depth; i++) {
    const sibling = String(1 + Math.floor(Math.random() * 1_000_000_000));
    const bit = Math.random() < 0.5;
    siblings.push(sibling);
    indexBits.push(bit);
    current = bit ? await hash2(sibling, current) : await hash2(current, sibling);
  }
  return { siblings, indexBits, root: current };
}
