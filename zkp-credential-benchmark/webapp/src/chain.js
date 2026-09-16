// All Ethereum interaction, via ethers.js + MetaMask (window.ethereum).
// The same code path is used for both the local Anvil network and Sepolia
// -- only the network MetaMask is currently connected to differs, which is
// exactly how a real dApp works (Section 3.6: the Verifier here is always
// "whatever chain the wallet points at").
import { ethers } from "ethers";
import { getNetworkConfig } from "./network-config.js";

const DEMO_ABI = [
  "function verifyAndRecord(bytes proof, bytes32[] publicInputs) returns (bool)",
  "event CredentialVerified(address indexed prover, bool verified, uint256 verificationGasUsed)",
];

export async function connectWallet() {
  if (!window.ethereum) {
    throw new Error("No wallet found. Install MetaMask (or another injected wallet) to continue.");
  }
  const provider = new ethers.BrowserProvider(window.ethereum);
  await provider.send("eth_requestAccounts", []);
  const signer = await provider.getSigner();
  const network = await provider.getNetwork();
  return { provider, signer, chainId: Number(network.chainId), address: await signer.getAddress() };
}

export function contractAddressFor(chainId, scenarioId) {
  const stored = localStorage.getItem(`zkdemo:${chainId}:${scenarioId}`);
  if (stored) return stored;
  const cfg = getNetworkConfig(chainId);
  return cfg ? cfg.contracts[scenarioId] || "" : "";
}

export function saveContractAddress(chainId, scenarioId, address) {
  localStorage.setItem(`zkdemo:${chainId}:${scenarioId}`, address);
}

/**
 * Submits a real, signed, mined transaction calling verifyAndRecord() on
 * the deployed CredentialVerifierDemo for this scenario -- not a read-only
 * call -- so MetaMask prompts for a signature and there is a genuine tx
 * hash + gas receipt to show, on Anvil or on Sepolia alike.
 */
export async function submitProof(signer, contractAddress, proofHex, publicInputsHex) {
  const contract = new ethers.Contract(contractAddress, DEMO_ABI, signer);
  const tx = await contract.verifyAndRecord(proofHex, publicInputsHex);
  const receipt = await tx.wait();

  let verified = null;
  let verificationGasUsed = null;
  for (const log of receipt.logs) {
    try {
      const parsed = contract.interface.parseLog(log);
      if (parsed && parsed.name === "CredentialVerified") {
        verified = parsed.args.verified;
        verificationGasUsed = parsed.args.verificationGasUsed;
      }
    } catch {
      // Not one of our events; ignore.
    }
  }

  return {
    txHash: receipt.hash,
    totalGasUsed: receipt.gasUsed,
    verified,
    verificationGasUsed,
  };
}
