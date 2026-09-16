// Thin wrapper around NoirJS + bb.js. Every function here runs entirely in
// the browser (WASM) -- no server, no CLI, matching the "holder" role in
// Chapter 3's Issuer/Holder/Verifier model (Section 3.6).
import { Noir } from "@noir-lang/noir_js";
import { Barretenberg, UltraHonkBackend } from "@aztec/bb.js";

const circuitCache = new Map();
let bbApiPromise = null;

// The Barretenberg WASM API is expensive to spin up (it starts a pool of
// Web Workers), so it is created once and reused across every proof in
// the session, exactly like a real prover-side application would.
function getBbApi() {
  if (!bbApiPromise) {
    const threads = Math.max(1, navigator.hardwareConcurrency || 4);
    bbApiPromise = Barretenberg.new({ threads });
  }
  return bbApiPromise;
}

export async function loadCircuit(url) {
  if (circuitCache.has(url)) return circuitCache.get(url);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch ${url}: ${res.status}`);
  const json = await res.json();
  circuitCache.set(url, json);
  return json;
}

/** Executes a circuit (witness generation only) and returns { witness, returnValue }. */
export async function execute(circuitJson, inputs) {
  const noir = new Noir(circuitJson);
  return await noir.execute(inputs);
}

/**
 * Full client-side proving pipeline for one of the four benchmark circuits:
 * generate the witness, then generate an EVM-targeted (Keccak) UltraHonk
 * proof -- the same proof format `bb prove -t evm` produces on the CLI,
 * so it verifies against the exact same Scenario<N>Verifier.sol contracts
 * Chapter 3/4 already deployed and measured.
 *
 * onProgress(stage) is called with 'witness' then 'proving' then 'done' so
 * the UI can show a spinner with a meaningful label.
 */
export async function proveEvm(circuitJson, inputs, onProgress = () => {}) {
  const t0 = performance.now();
  onProgress("witness");
  const { witness } = await execute(circuitJson, inputs);
  const t1 = performance.now();

  onProgress("proving");
  const api = await getBbApi();
  const backend = new UltraHonkBackend(circuitJson.bytecode, api);
  const proofData = await backend.generateProof(witness, { verifierTarget: "evm" });
  const t2 = performance.now();

  onProgress("done");
  return {
    proof: proofData.proof, // Uint8Array
    publicInputs: proofData.publicInputs, // string[] (hex)
    timings: {
      witnessMs: t1 - t0,
      provingMs: t2 - t1,
      totalMs: t2 - t0,
    },
  };
}

export function proofToHex(proofBytes) {
  return "0x" + Array.from(proofBytes).map((b) => b.toString(16).padStart(2, "0")).join("");
}
