#!/usr/bin/env python3
"""
export_proof_for_solidity.py

Converts the raw binary files `bb prove` writes (target/proof and, when
public inputs are separated out, target/public_inputs) into the hex
formats Solidity/Foundry expects:

  - proof      -> a single 0x-prefixed hex string, for `bytes calldata proof`
  - public_inputs -> a comma-separated list of 0x-prefixed 32-byte hex
                      words, for `bytes32[] calldata publicInputs`

This is a formatting convenience only -- it does not touch the
cryptographic content of the proof in any way, it just re-encodes bytes
already produced by `bb prove` / `bb write_vk` into a form you can paste
into a Foundry test (see contracts/test/CredentialVerifier.gas.t.sol)
or pass to `cast send`.

Usage:
    python3 export_proof_for_solidity.py \
        --proof ../circuits/scenario1_minimal/target/proof \
        --public-inputs ../circuits/scenario1_minimal/target/public_inputs \
        --out ../results/scenario1_calldata.txt
"""

import argparse
from pathlib import Path


def proof_to_hex(proof_path: Path) -> str:
    data = proof_path.read_bytes()
    return "0x" + data.hex()


def public_inputs_to_hex_list(public_inputs_path: Path, word_size: int = 32) -> list:
    """bb writes public inputs as a flat byte blob, each field element
    padded/encoded as `word_size` bytes (32 for BN254 Field elements).
    Splits that blob into individual 0x-prefixed 32-byte words."""
    data = public_inputs_path.read_bytes()
    if len(data) % word_size != 0:
        raise ValueError(
            f"public_inputs file length ({len(data)} bytes) is not a multiple of "
            f"{word_size} -- check you're pointing at the right file / bb version."
        )
    words = [data[i : i + word_size] for i in range(0, len(data), word_size)]
    return ["0x" + w.hex() for w in words]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof", required=True, help="Path to bb's raw `proof` output file")
    parser.add_argument("--public-inputs", required=False, default=None,
                         help="Path to bb's raw `public_inputs` output file (if separated from the proof)")
    parser.add_argument("--out", required=False, default=None,
                         help="Optional file to write the formatted calldata to; otherwise prints to stdout")
    args = parser.parse_args()

    proof_path = Path(args.proof)
    if not proof_path.exists():
        raise SystemExit(f"ERROR: proof file not found: {proof_path}")

    proof_hex = proof_to_hex(proof_path)

    public_inputs_hex = []
    if args.public_inputs:
        pi_path = Path(args.public_inputs)
        if pi_path.exists():
            public_inputs_hex = public_inputs_to_hex_list(pi_path)
        else:
            print(f"WARNING: public-inputs file not found at {pi_path}; "
                  f"continuing with an empty publicInputs array.")

    lines = []
    lines.append(f"// --- Solidity calldata for {proof_path} ---")
    lines.append(f"bytes memory proof = hex\"{proof_hex[2:]}\";")
    lines.append(f"// proof length: {len(proof_hex[2:]) // 2} bytes")
    lines.append("")
    lines.append(f"bytes32[] memory publicInputs = new bytes32[]({len(public_inputs_hex)});")
    for i, word in enumerate(public_inputs_hex):
        lines.append(f"publicInputs[{i}] = {word};")
    lines.append("")
    lines.append("// cast send equivalent (single-line hex args):")
    lines.append(f"// proof:         {proof_hex}")
    lines.append(f"// publicInputs:  [{', '.join(public_inputs_hex)}]")

    output = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(output + "\n")
        print(f"Wrote Solidity-ready calldata to {args.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()
