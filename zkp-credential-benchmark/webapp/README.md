# ZK Credential Demo (webapp/)

A browser front-end for the same four credential circuits benchmarked in
Chapter 3/4: generate a real proof **entirely client-side** (NoirJS + bb.js,
no server ever sees your private attributes), then submit it to a deployed
verifier contract on a local Anvil node or on Sepolia (ethers.js).

Plain HTML/CSS/JavaScript + Bootstrap for styling — no React, no Vite, no
framework. The only build step (`npm run build`) exists because the two
proving libraries are npm packages that need bundling; the actual page
(`public/index.html`, `src/app.js`, ...) is ordinary, readable JS you can
open and edit directly.

## What this does, and does not, replace

This demo is **not** where Chapter 4's gas figures come from. Its on-chain
contract (`CredentialVerifierDemo`) is a state-changing wrapper so your
wallet can sign a real transaction and you get a real tx hash to look at —
useful for a live demonstration, but *not* the precise, isolated
measurement Chapter 3 §3.8.3 specifies. For the thesis's actual numbers,
use `results/benchmark_results.csv` and the original `CredentialVerifier`
contract, unchanged by anything here.

## Prerequisites

- Node.js and npm (this project was built and tested with Node v26.8.2 to
  match the pinned version in Chapter 3 §3.4)
- `nargo` (v1.0.0-beta.22) and `bb` (5.0.0-nightly.20260522) already on
  PATH — same versions as the rest of this project
- Foundry (`forge`, `anvil`, `cast`)
- A browser wallet extension (e.g. MetaMask) for Steps 4 and 6
- `python3 scripts/generate_evm_artifacts.py` must already have been run
  from the project root at least once, so that `contracts/src/Scenario<N>
  Verifier.sol` exist (Step 2 below imports them directly)

## Step 1 — Install and build

```bash
cd webapp
npm install
npm run build
```

This produces `webapp/dist/` — a complete, self-contained static site
(HTML, CSS, the bundled JS, the four compiled circuits, and the two extra
"return-value" Poseidon helper circuits used to compute the Scenario 3/4
derived fields in-browser).

Re-run `npm run build` any time you edit a file under `src/`.

## Step 2 — Deploy the demo contracts (local Anvil first)

In one terminal, start a local chain:

```bash
anvil
```

Anvil prints 10 funded test accounts and their private keys — these are
**publicly known, throwaway keys with no real value**; never use them, or
this pattern, on a network with real funds.

In another terminal, from the project's `contracts/` directory:

```bash
forge script script/DeployDemo.s.sol \
  --rpc-url http://127.0.0.1:8545 \
  --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
  --broadcast --slow
```

`--slow` matters here: without it, this specific script has been observed
to stall broadcasting eight transactions (four verifiers, each wrapped in
a `CredentialVerifierDemo`) against Anvil's default async broadcaster —
`--slow` submits and confirms them one at a time and completes reliably.

The script prints eight addresses (`Scenario<N>Verifier` and its
`CredentialVerifierDemo` wrapper, per scenario). Copy the four
**`CredentialVerifierDemo`** addresses into `src/network-config.js` under
the `31337` (Local Anvil) network, then `npm run build` again — or just
paste them into the "Contract address" field in the page itself once
connected (it's saved to your browser's local storage from then on).

> Restarting Anvil wipes its state. If you restart it, redeploy and update
> the addresses again.

## Step 3 — Serve and try it locally

```bash
npm run serve
```

Open the printed URL (default `http://localhost:8080`). Do **not** swap
this for a generic static server (e.g. `python -m http.server`) without
adding the same two response headers it sets
(`Cross-Origin-Opener-Policy: same-origin` and
`Cross-Origin-Embedder-Policy: require-corp`) — bb.js's multi-threaded
WASM needs `SharedArrayBuffer`, which browsers only expose on
cross-origin-isolated pages.

## Step 4 — Try the demo (local Anvil)

1. In MetaMask, add/select a local network pointing at
   `http://127.0.0.1:8545`, chain ID `31337`, and import one of Anvil's
   printed test accounts (so it has test ETH to pay gas with).
2. On the page, pick a scenario tab (1–4).
3. Fill in the attribute fields (sensible defaults are pre-filled).
   - **Scenario 3**: the credential commitment is computed automatically
     when you click Generate — you never type it in.
   - **Scenario 4**: click "Generate a valid membership proof" first (this
     builds a fresh, genuinely valid Merkle root the same way the
     thesis's synthetic-data generator does — there is no real credential
     registry in this demo).
4. Click **Generate Proof (client-side)**. The very first proof in a
   browser session can take up to a minute (bb.js downloads the
   Barretenberg structured reference string, the CRS, once and caches it);
   later proofs in the same session are much faster.
5. Click **Connect Wallet**, approve in MetaMask.
6. Paste the matching `CredentialVerifierDemo` address for this scenario
   (pre-filled if you edited `network-config.js`), then click
   **Submit Proof to Blockchain** and confirm the transaction in MetaMask.
7. You'll see the transaction hash, whether the proof verified, and both
   the total transaction gas and the isolated verification-only gas
   (recorded via the contract's own `gasleft()` accounting, same idea as
   Chapter 3 §3.8.3, but not the same contract Chapter 4 measured).

## Step 5 — Deploy to Sepolia (optional, live-network demonstration)

This step spends **real Sepolia testnet ETH from your own wallet** — get
some free from a Sepolia faucet first. Never use anyone else's private
key, and never reuse Anvil's well-known test key here.

```bash
cd contracts
forge script script/DeployDemo.s.sol \
  --rpc-url <your Sepolia RPC URL, e.g. from Alchemy/Infura> \
  --private-key <your own funded Sepolia private key> \
  --broadcast --slow
```

Copy the four `CredentialVerifierDemo` addresses this prints into
`webapp/src/network-config.js` under the `11155111` (Sepolia) network,
then `npm run build` again.

## Step 6 — Try the demo (Sepolia)

Same as Step 4, except: switch MetaMask to the Sepolia network before
connecting. The page detects the network automatically and pre-fills the
Sepolia contract addresses. Transactions here are real, on a public
testnet — anyone can look up the transaction hash on
[sepolia.etherscan.io](https://sepolia.etherscan.io).

## Project layout

```
webapp/
├── package.json         pinned exact versions: noir_js 1.0.0-beta.22,
│                         bb.js 5.0.0-nightly.20260522 (matching Chapter 3
│                         §3.4 exactly), ethers 6.17.0
├── build.mjs             esbuild build script (bundles app + the two bb.js
│                         Web Worker entry points + copies the two WASM
│                         files noir_js needs; see comments inside)
├── serve.mjs             minimal static file server with the COOP/COEP
│                         headers bb.js's threading needs
├── src/
│   ├── scenarios.js      per-scenario form field definitions (mirrors
│   │                     Chapter 3 Table 3.2 and generate_synthetic_data.py)
│   ├── prover.js         NoirJS + bb.js wrapper (witness + EVM proof)
│   ├── derive.js         in-browser Poseidon commitment / Merkle-path
│   │                     helpers for Scenarios 3 and 4
│   ├── chain.js          ethers.js wallet connection + contract calls
│   ├── network-config.js per-network CredentialVerifierDemo addresses
│   └── app.js            UI wiring (DOM only, no framework)
├── public/               index.html + css/style.css (served as-is)
├── circuits/             compiled circuit JSON (scenario1-4 + the three
│                         hash2/hash8/hash16 "return-value" helper
│                         circuits under circuits_src/, see below)
├── circuits_src/         Noir source for the three helper circuits above
│                         -- twins of tools/hash*_helper that return a
│                         public Field instead of printing it, so NoirJS
│                         can read the value directly (a browser prover
│                         can't parse CLI stdout). Does not touch the
│                         original tools/ directory used by the real
│                         experiment.
└── dist/                 build output (generated; safe to delete/rebuild)
```
