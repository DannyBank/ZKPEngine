// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Same minimal verifier interface as CredentialVerifier.sol.
interface IHonkVerifier {
    function verify(bytes calldata proof, bytes32[] calldata publicInputs) external view returns (bool);
}

/// @notice Demo-only wrapper used by webapp/. This is a deliberately
/// separate contract from src/CredentialVerifier.sol (the one Chapter 3's
/// gas benchmark actually measures) so that the precise, already-reported
/// Chapter 4 gas figures are never touched by this demo. The only
/// difference is that verifyCredential() here is state-changing rather
/// than `view`, so a wallet (MetaMask) will prompt to sign and mine a
/// real transaction with a real receipt -- useful for a live, clickable
/// demo, but not the right contract to cite for the thesis's own gas
/// numbers (use CredentialVerifier.sol / results/benchmark_results.csv
/// for that).
contract CredentialVerifierDemo {
    IHonkVerifier public immutable verifier;
    string public scenarioLabel;

    event CredentialVerified(address indexed prover, bool verified, uint256 verificationGasUsed);

    constructor(address _verifier, string memory _scenarioLabel) {
        verifier = IHonkVerifier(_verifier);
        scenarioLabel = _scenarioLabel;
    }

    function verifyAndRecord(bytes calldata proof, bytes32[] calldata publicInputs) external returns (bool verified) {
        uint256 gasBefore = gasleft();
        verified = verifier.verify(proof, publicInputs);
        uint256 gasUsed = gasBefore - gasleft();
        emit CredentialVerified(msg.sender, verified, gasUsed);
    }
}
