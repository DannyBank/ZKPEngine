// Per-network contract addresses. Fill these in after running
// `forge script script/DeployDemo.s.sol ...` for that network (the script
// prints each address -- see webapp/README.md Step 3).
//
// A per-viewer override typed into the "Contract address" field in the UI
// is saved to localStorage and always wins over the defaults below, so you
// never have to edit this file just to try a fresh deployment.
export const NETWORKS = {
  31337: {
    name: "Local Anvil",
    explorer: null,
    contracts: {
      // Addresses from this project's own local Anvil test deployment.
      // Anvil resets its state on every restart, so if you restart Anvil
      // you MUST redeploy and either edit these defaults or paste the new
      // addresses into the UI (they'll be remembered from then on).
      scenario1: "0x8A791620dd6260079BF849Dc5567aDC3F2FdC318",
      scenario2: "0xB7f8BC63BbcaD18155201308C8f3540b07f84F5e",
      scenario3: "0x0DCd1Bf9A1b36cE34237eEaFef220932846BCD82",
      scenario4: "0x0B306BF915C4d645ff596e518fAf3F9669b97016",
    },
  },
  11155111: {
    name: "Sepolia",
    explorer: "https://sepolia.etherscan.io/tx/",
    contracts: {
      // Fill these in yourself after deploying to Sepolia with your own
      // funded key -- see webapp/README.md Step 5. Left blank on purpose:
      // never ship or share a testnet deployment you don't control.
      scenario1: "",
      scenario2: "",
      scenario3: "",
      scenario4: "",
    },
  },
};

export function getNetworkConfig(chainId) {
  return NETWORKS[chainId] || null;
}
