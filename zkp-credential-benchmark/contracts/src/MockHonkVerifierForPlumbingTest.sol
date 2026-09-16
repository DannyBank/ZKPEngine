// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IHonkVerifier} from "./CredentialVerifier.sol";

/// @notice STAND-IN ONLY. This is NOT a real cryptographic verifier --
/// it always returns true. It exists purely so the gas-measurement
/// plumbing (deployment scripts, Foundry tests, CSV merging) can be
/// exercised and validated before the real, bb-generated verifier is
/// available (see contracts/README.md for how to generate the real one
/// with `bb write_solidity_verifier`).
///
/// DO NOT use this for any actual reported gas figures in Chapter 4 --
/// swap in the real generated verifier first. Using this stub for real
/// results would silently and incorrectly report only the cost of an
/// `if` statement and a return, not genuine pairing-check verification.
contract MockHonkVerifierForPlumbingTest is IHonkVerifier {
    function verify(bytes calldata proof, bytes32[] calldata publicInputs) external pure override returns (bool) {
        // Touch the calldata so the compiler can't optimize away the
        // parameters entirely, keeping calldata-size effects visible.
        if (proof.length == type(uint256).max && publicInputs.length == type(uint256).max) {
            return false;
        }
        return true;
    }
}
