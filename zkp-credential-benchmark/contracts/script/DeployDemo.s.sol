// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console} from "forge-std/Script.sol";
import {CredentialVerifierDemo} from "../src/CredentialVerifierDemo.sol";

// Static imports (rather than the dynamic deployCode() pattern used in
// test/RealVerifierGas.t.sol) are required here: forge script's
// broadcaster only auto-deploys and links a generated verifier's
// external Solidity libraries (RelationsLib, ZKTranscriptLib, etc.) when
// the contract is reachable through a normal `import`. `deployCode()`
// bypasses that auto-linking and fails with "no bytecode for contract;
// is it abstract or unlinked?" in script/broadcast mode, even though the
// identical pattern works fine inside `forge test`.
//
// PREREQUISITE: run `python3 scripts/generate_evm_artifacts.py` first so
// that contracts/src/Scenario<N>Verifier.sol exist -- this file will not
// compile otherwise.
import {Scenario1Verifier} from "../src/Scenario1Verifier.sol";
import {Scenario2Verifier} from "../src/Scenario2Verifier.sol";
import {Scenario3Verifier} from "../src/Scenario3Verifier.sol";
import {Scenario4Verifier} from "../src/Scenario4Verifier.sol";

/// @notice Deploys the four generated Scenario<N>Verifier contracts (and
/// whatever external libraries they need, auto-linked by forge) plus a
/// CredentialVerifierDemo wrapper for each, so the webapp/ demo can submit
/// real proofs against them.
///
/// Usage (local Anvil -- run `anvil` in another terminal first):
///   forge script script/DeployDemo.s.sol \
///     --rpc-url http://127.0.0.1:8545 \
///     --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
///     --broadcast
///   (0xac09... is Anvil's own well-known, publicly documented default
///   test account #0 key -- safe for local-only use, never for Sepolia)
///
/// Usage (Sepolia -- use your OWN funded key/RPC, never anyone else's):
///   forge script script/DeployDemo.s.sol \
///     --rpc-url <your Sepolia RPC URL> \
///     --private-key <your own Sepolia private key> \
///     --broadcast --verify
///
/// After it runs, copy the four printed CredentialVerifierDemo addresses
/// into webapp/src/network-config.js under the matching network.
contract DeployDemo is Script {
    function run() external {
        vm.startBroadcast();

        Scenario1Verifier v1 = new Scenario1Verifier();
        CredentialVerifierDemo d1 = new CredentialVerifierDemo(address(v1), "scenario1");
        console.log("Scenario1Verifier deployed at:", address(v1));
        console.log("scenario1 CredentialVerifierDemo deployed at:", address(d1));

        Scenario2Verifier v2 = new Scenario2Verifier();
        CredentialVerifierDemo d2 = new CredentialVerifierDemo(address(v2), "scenario2");
        console.log("Scenario2Verifier deployed at:", address(v2));
        console.log("scenario2 CredentialVerifierDemo deployed at:", address(d2));

        Scenario3Verifier v3 = new Scenario3Verifier();
        CredentialVerifierDemo d3 = new CredentialVerifierDemo(address(v3), "scenario3");
        console.log("Scenario3Verifier deployed at:", address(v3));
        console.log("scenario3 CredentialVerifierDemo deployed at:", address(d3));

        Scenario4Verifier v4 = new Scenario4Verifier();
        CredentialVerifierDemo d4 = new CredentialVerifierDemo(address(v4), "scenario4");
        console.log("Scenario4Verifier deployed at:", address(v4));
        console.log("scenario4 CredentialVerifierDemo deployed at:", address(d4));

        vm.stopBroadcast();
    }
}
