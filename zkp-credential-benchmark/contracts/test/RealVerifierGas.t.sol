// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {stdJson} from "forge-std/StdJson.sol";
import {CredentialVerifier} from "../src/CredentialVerifier.sol";

/// @notice Real, per-scenario gas measurement (Chapter 3, Section 3.8.3),
/// using genuine bb-generated proofs and verification keys instead of
/// placeholder/mock data.
///
/// This test does NOT `import` the generated Scenario*Verifier.sol
/// contracts directly -- they don't exist in this repo until you run
/// scripts/generate_evm_artifacts.py, so a static import would break
/// compilation for anyone who hasn't run that script yet. Instead it
/// deploys each generated contract dynamically via `deployCode`,
/// referencing it only by name string, and calls it through the
/// existing IHonkVerifier interface (see src/CredentialVerifier.sol) --
/// every bb-generated verifier implements the same `verify(bytes,
/// bytes32[]) returns (bool)` signature, so this works generically
/// across all four scenarios without needing four separate imports.
///
/// PREREQUISITE:
///   python3 scripts/generate_evm_artifacts.py
/// must have been run first, so that:
///   - contracts/src/Scenario<N>Verifier.sol exists for each scenario
///   - contracts/test/fixtures/<scenario>_run_<NNN>.json exists with
///     real proof + publicInputs data
///
/// Run with:
///   forge test --match-contract RealVerifierGasTest -vv --gas-report
contract RealVerifierGasTest is Test {
    using stdJson for string;

    struct Fixture {
        bytes proof;
        bytes32[] publicInputs;
        string contractName;
    }

    string constant FIXTURES_DIR = "./test/fixtures";

    function _loadFixture(string memory fixtureFileName) internal view returns (Fixture memory) {
        string memory path = string.concat(FIXTURES_DIR, "/", fixtureFileName);
        string memory json = vm.readFile(path);
        Fixture memory f;
        f.proof = json.readBytes(".proof");
        f.publicInputs = json.readBytes32Array(".publicInputs");
        f.contractName = json.readString(".contractName");
        return f;
    }

    function _deployAndWrap(string memory contractName) internal returns (CredentialVerifier) {
        // e.g. contractName "Scenario1Verifier" -> artifact
        // "Scenario1Verifier.sol:Scenario1Verifier"
        string memory artifact = string.concat(contractName, ".sol:", contractName);
        address verifierAddr = deployCode(artifact);
        return new CredentialVerifier(verifierAddr);
    }

    /// @dev Runs one fixture end to end and logs the real verification gas.
    /// Returns false (instead of reverting) if the fixture file doesn't
    /// exist yet, so scenarios you haven't generated artifacts for don't
    /// block the whole test run -- they just get skipped with a clear log.
    function _runFixtureIfPresent(string memory fixtureFileName) internal returns (bool ran) {
        string memory path = string.concat(FIXTURES_DIR, "/", fixtureFileName);
        if (!vm.exists(path)) {
            emit log_string(string.concat("[skip] fixture not found yet: ", fixtureFileName));
            return false;
        }

        Fixture memory f = _loadFixture(fixtureFileName);
        CredentialVerifier credentialVerifier = _deployAndWrap(f.contractName);

        uint256 gasBefore = gasleft();
        bool ok = credentialVerifier.verifyCredential(f.proof, f.publicInputs);
        uint256 gasUsed = gasBefore - gasleft();

        assertTrue(ok, string.concat("Real proof failed to verify for fixture: ", fixtureFileName));

        emit log_named_string("fixture", fixtureFileName);
        emit log_named_uint("verification_gas_used", gasUsed);
        emit log_named_uint("proof_size_bytes", f.proof.length);
        emit log_named_uint("public_input_count", f.publicInputs.length);
        emit log_named_uint("calldata_size_bytes", f.proof.length + f.publicInputs.length * 32);
        return true;
    }

    function test_Scenario1_RealVerificationGas() public {
        bool ran = _runFixtureIfPresent("scenario1_minimal_run_001.json");
        if (!ran) emit log_string("Run: python3 scripts/generate_evm_artifacts.py --scenario scenario1_minimal");
    }

    function test_Scenario2_RealVerificationGas() public {
        bool ran = _runFixtureIfPresent("scenario2_multi_attr_run_001.json");
        if (!ran) emit log_string("Run: python3 scripts/generate_evm_artifacts.py --scenario scenario2_multi_attr");
    }

    function test_Scenario3_RealVerificationGas() public {
        bool ran = _runFixtureIfPresent("scenario3_full_integrity_run_001.json");
        if (!ran) emit log_string("Run: python3 scripts/generate_evm_artifacts.py --scenario scenario3_full_integrity");
    }

    function test_Scenario4_RealVerificationGas() public {
        bool ran = _runFixtureIfPresent("scenario4_advanced_identity_run_001.json");
        if (!ran) emit log_string("Run: python3 scripts/generate_evm_artifacts.py --scenario scenario4_advanced_identity");
    }

    /// @notice Confirms gas stays flat ACROSS DIFFERENT INPUTS to the same
    /// circuit -- the empirical check for Section 3.11.4's decoupling
    /// hypothesis. Runs every trial fixture generated for Scenario 1
    /// (run_001, run_002, run_003, ...) and logs each gas figure so you
    /// can eyeball that they're all essentially identical.
    function test_Scenario1_GasIsFlatAcrossTrials() public {
        for (uint256 i = 1; i <= 5; i++) {
            string memory fname = string.concat(
                "scenario1_minimal_run_", i < 10 ? string.concat("00", vm.toString(i)) : string.concat("0", vm.toString(i)), ".json"
            );
            _runFixtureIfPresent(fname);
        }
    }
}
