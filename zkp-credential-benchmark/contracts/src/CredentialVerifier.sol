// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Minimal interface expected of a bb-generated Honk/PlonK
/// Solidity verifier (see `bb write_solidity_verifier`). The real
/// verifier contract generated for each scenario should implement
/// this same `verify` signature; swap RealVerifierStub for the actual
/// generated contract when running the true experiment.
interface IHonkVerifier {
    function verify(bytes calldata proof, bytes32[] calldata publicInputs) external view returns (bool);
}

/// @notice Deliberately minimal wrapper contract used for gas
/// measurement (Chapter 3, Section 3.8.2). Keeping this contract free
/// of any bookkeeping or access-control logic ensures that the gas
/// figure recorded for verifyCredential() reflects only the underlying
/// cryptographic verification cost, not application overhead.
contract CredentialVerifier {
    IHonkVerifier public immutable verifier;

    constructor(address _verifier) {
        verifier = IHonkVerifier(_verifier);
    }

    function verifyCredential(bytes calldata proof, bytes32[] calldata publicInputs) external view returns (bool) {
        return verifier.verify(proof, publicInputs);
    }
}
