import { SCENARIOS, SCENARIO_ORDER } from "./scenarios.js";
import { loadCircuit, proveEvm, proofToHex } from "./prover.js";
import { hash8, buildRandomMerkleProof } from "./derive.js";
import { connectWallet, contractAddressFor, saveContractAddress, submitProof } from "./chain.js";

const state = {
  scenarioId: "scenario1",
  wallet: null, // { provider, signer, chainId, address }
  lastProof: null, // { proofHex, publicInputsHex, scenarioId }
};

const el = (id) => document.getElementById(id);

function currentScenario() {
  return SCENARIOS[state.scenarioId];
}

// ---------------------------------------------------------------------
// Scenario picker + dynamic form
// ---------------------------------------------------------------------

function renderScenarioTabs() {
  const nav = el("scenario-tabs");
  nav.innerHTML = "";
  for (const id of SCENARIO_ORDER) {
    const s = SCENARIOS[id];
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "nav-link" + (id === state.scenarioId ? " active" : "");
    btn.textContent = s.label;
    btn.addEventListener("click", () => {
      state.scenarioId = id;
      renderScenarioTabs();
      renderForm();
      resetResults();
    });
    const li = document.createElement("li");
    li.className = "nav-item";
    li.appendChild(btn);
    nav.appendChild(li);
  }
}

function fieldInputId(name, index) {
  return index === undefined ? `field-${name}` : `field-${name}-${index}`;
}

function renderForm() {
  const s = currentScenario();
  el("scenario-description").textContent = s.description;

  const container = el("credential-fields");
  container.innerHTML = "";

  for (const field of s.fields) {
    const wrap = document.createElement("div");
    wrap.className = "mb-3";

    const label = document.createElement("label");
    label.className = "form-label";
    label.textContent = `${field.label} (${field.visibility})`;
    wrap.appendChild(label);

    if (field.hint) {
      const hint = document.createElement("div");
      hint.className = "form-text";
      hint.textContent = field.hint;
      wrap.appendChild(hint);
    }

    if (field.kind === "field") {
      const input = document.createElement("input");
      input.type = "number";
      input.className = "form-control";
      input.id = fieldInputId(field.name);
      input.value = field.default;
      wrap.appendChild(input);
    } else if (field.kind === "field[]") {
      const row = document.createElement("div");
      row.className = "row g-2";
      for (let i = 0; i < field.size; i++) {
        const col = document.createElement("div");
        col.className = "col-3 col-md-2";
        const input = document.createElement("input");
        input.type = "number";
        input.className = "form-control form-control-sm";
        input.id = fieldInputId(field.name, i);
        input.value = field.default[i];
        input.title = `${field.name}[${i}]`;
        col.appendChild(input);
        row.appendChild(col);
      }
      wrap.appendChild(row);
    }

    container.appendChild(wrap);
  }

  // Scenario-specific derived-value UI.
  const derivedBox = el("derived-box");
  derivedBox.innerHTML = "";
  derivedBox.classList.add("d-none");

  if (s.derivedCommitment) {
    derivedBox.classList.remove("d-none");
    derivedBox.innerHTML = `
      <div class="alert alert-secondary">
        <div class="fw-semibold">${s.derivedCommitment.outputLabel}</div>
        <div id="derived-commitment-value" class="font-monospace small text-break">not computed yet</div>
      </div>`;
  }

  if (s.merkle) {
    derivedBox.classList.remove("d-none");
    derivedBox.innerHTML = `
      <div class="alert alert-secondary">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <div class="fw-semibold">Merkle membership (demo)</div>
          <button id="generate-merkle-btn" type="button" class="btn btn-sm btn-outline-primary">
            Generate a valid membership proof
          </button>
        </div>
        <div class="small">Siblings: <span id="merkle-siblings" class="font-monospace">not generated yet</span></div>
        <div class="small">Directions: <span id="merkle-bits" class="font-monospace">not generated yet</span></div>
        <div class="small">${s.merkle.rootLabel}: <span id="merkle-root" class="font-monospace text-break">not generated yet</span></div>
      </div>`;
    el("generate-merkle-btn").addEventListener("click", onGenerateMerkleProof);
  }
}

function readFieldValues() {
  const s = currentScenario();
  const inputs = {};
  for (const field of s.fields) {
    if (field.kind === "field") {
      inputs[field.name] = String(el(fieldInputId(field.name)).value);
    } else if (field.kind === "field[]") {
      inputs[field.name] = Array.from({ length: field.size }, (_, i) =>
        String(el(fieldInputId(field.name, i)).value)
      );
    }
  }
  return inputs;
}

// ---------------------------------------------------------------------
// Derived-value generation (Scenario 3 commitment / Scenario 4 Merkle)
// ---------------------------------------------------------------------

state.merkleProof = null; // { siblings, indexBits, root }

async function onGenerateMerkleProof() {
  const s = currentScenario();
  const btn = el("generate-merkle-btn");
  btn.disabled = true;
  btn.textContent = "Computing (Poseidon in-browser)...";
  try {
    const inputs = readFieldValues();
    const leaf = await hash16OfFields(inputs.fields);
    const proof = await buildRandomMerkleProof(leaf, s.merkle.depth);
    state.merkleProof = proof;
    el("merkle-siblings").textContent = "[" + proof.siblings.join(", ") + "]";
    el("merkle-bits").textContent = "[" + proof.indexBits.join(", ") + "]";
    el("merkle-root").textContent = proof.root;
  } catch (err) {
    alert("Failed to generate membership proof: " + err.message);
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate a valid membership proof";
  }
}

async function hash16OfFields(fields16) {
  const { hash16 } = await import("./derive.js");
  return hash16(fields16);
}

// ---------------------------------------------------------------------
// Proof generation
// ---------------------------------------------------------------------

function setProofStatus(text) {
  el("proof-status").textContent = text;
}

function resetResults() {
  el("proof-status").textContent = "";
  el("proof-result").classList.add("d-none");
  el("tx-result").classList.add("d-none");
  el("submit-proof-btn").disabled = true;
  state.lastProof = null;
}

async function onGenerateProof() {
  const s = currentScenario();
  const genBtn = el("generate-proof-btn");
  genBtn.disabled = true;
  el("proof-result").classList.add("d-none");
  el("tx-result").classList.add("d-none");

  try {
    const inputs = readFieldValues();

    if (s.derivedCommitment) {
      setProofStatus("Computing Poseidon commitment in-browser...");
      const attrs = s.derivedCommitment.sourceFields.map((name) => inputs[name]);
      const commitment = await hash8(attrs);
      inputs[s.derivedCommitment.outputField] = commitment;
      el("derived-commitment-value").textContent = commitment;
    }

    if (s.merkle) {
      if (!state.merkleProof) {
        throw new Error('Click "Generate a valid membership proof" first.');
      }
      inputs[s.merkle.pathField] = state.merkleProof.siblings;
      inputs[s.merkle.indexBitsField] = state.merkleProof.indexBits;
      inputs[s.merkle.rootField] = state.merkleProof.root;
    }

    setProofStatus("Loading circuit...");
    const circuit = await loadCircuit(s.circuitFile);

    const result = await proveEvm(circuit, inputs, (stage) => {
      if (stage === "witness") setProofStatus("Generating witness (NoirJS)...");
      if (stage === "proving")
        setProofStatus(
          "Generating proof (bb.js, UltraHonk, EVM target)... first proof of the session " +
            "can take up to a minute while the CRS downloads; later proofs are much faster."
        );
    });

    const proofHex = proofToHex(result.proof);
    state.lastProof = { proofHex, publicInputsHex: result.publicInputs, scenarioId: s.id };

    setProofStatus("Proof generated.");
    el("proof-result").classList.remove("d-none");
    el("proof-witness-time").textContent = result.timings.witnessMs.toFixed(1);
    el("proof-proving-time").textContent = result.timings.provingMs.toFixed(1);
    el("proof-size").textContent = result.proof.length;
    el("proof-public-inputs").textContent = JSON.stringify(result.publicInputs, null, 2);

    el("submit-proof-btn").disabled = !state.wallet;
  } catch (err) {
    setProofStatus("Failed: " + err.message);
    console.error(err);
  } finally {
    genBtn.disabled = false;
  }
}

// ---------------------------------------------------------------------
// Wallet + on-chain submission
// ---------------------------------------------------------------------

async function onConnectWallet() {
  try {
    state.wallet = await connectWallet();
    renderWalletStatus();
    el("submit-proof-btn").disabled = !state.lastProof;
  } catch (err) {
    alert(err.message);
  }
}

function renderWalletStatus() {
  const box = el("wallet-status");
  if (!state.wallet) {
    box.textContent = "Not connected.";
    return;
  }
  const { address, chainId } = state.wallet;
  const networkName = chainId === 31337 ? "Local Anvil" : chainId === 11155111 ? "Sepolia" : `Chain ${chainId}`;
  box.innerHTML = `Connected: <span class="font-monospace">${address}</span> on <strong>${networkName}</strong> (chainId ${chainId})`;
  const addrInput = el("contract-address-input");
  addrInput.value = contractAddressFor(chainId, state.scenarioId);
}

async function onSubmitProof() {
  if (!state.wallet || !state.lastProof) return;
  const btn = el("submit-proof-btn");
  btn.disabled = true;
  el("tx-status").textContent = "Waiting for wallet signature and confirmation...";
  el("tx-result").classList.add("d-none");

  try {
    const address = el("contract-address-input").value.trim();
    if (!address) throw new Error("Enter a deployed CredentialVerifierDemo contract address first.");
    saveContractAddress(state.wallet.chainId, state.lastProof.scenarioId, address);

    const result = await submitProof(
      state.wallet.signer,
      address,
      state.lastProof.proofHex,
      state.lastProof.publicInputsHex
    );

    el("tx-status").textContent = "Confirmed.";
    el("tx-result").classList.remove("d-none");
    el("tx-hash").textContent = result.txHash;
    el("tx-verified").textContent = String(result.verified);
    el("tx-verified").className = result.verified ? "text-success fw-bold" : "text-danger fw-bold";
    el("tx-gas-total").textContent = result.totalGasUsed.toString();
    el("tx-gas-verification").textContent = result.verificationGasUsed
      ? result.verificationGasUsed.toString()
      : "n/a";
  } catch (err) {
    el("tx-status").textContent = "Failed: " + err.message;
    console.error(err);
  } finally {
    btn.disabled = false;
  }
}

// ---------------------------------------------------------------------
// Wire up
// ---------------------------------------------------------------------

function init() {
  renderScenarioTabs();
  renderForm();
  renderWalletStatus();

  el("generate-proof-btn").addEventListener("click", onGenerateProof);
  el("connect-wallet-btn").addEventListener("click", onConnectWallet);
  el("submit-proof-btn").addEventListener("click", onSubmitProof);

  if (window.ethereum) {
    window.ethereum.on?.("chainChanged", () => window.location.reload());
    window.ethereum.on?.("accountsChanged", () => window.location.reload());
  }
}

init();
