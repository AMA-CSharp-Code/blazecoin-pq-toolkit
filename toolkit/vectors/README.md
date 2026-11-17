# P2PQH test vectors and reference verifier

Everything needed to check an implementation of P2PQH (pay to post-quantum key hash, the post-quantum output type) against ours, without running our node.

| File | What it is |
|---|---|
| `verify_p2pqh.py` | Reference verifier, about 150 lines of Python. Every consensus rule for a PQ input, in the node's order. Shares no code with the generator, the C++ node or the C# wallet. Run it with no arguments to check both vector files. |
| `pqsig_vectors.json` | Synthetic vectors (deterministic). Byte-identical to `test/pqsig/pqsig_vectors.json` in the node repo, which the node's unit tests and the wallet's tests are pinned to. |
| `generate_pqsig_vectors.py` | The generator for the file above (pure Python, dilithium-py). Rerunning it reproduces the file. |
| `mainnet_examples.json` | Real mainnet transactions with the amount and scriptPubKey of every prevout. |
| `fetch_mainnet_examples.py` | How the mainnet file was made (needs a node). |

## What the synthetic vectors cover
- **derivation** (3): master seed and index to the ML-DSA seed, public key, key hash, scriptPubKey and both address forms.
- **sighash** (3 transactions, 29 PQ inputs): 1 input; 1 classic + 2 PQ inputs with a locktime and non-final sequences; 26 PQ
  inputs (98,419 bytes, the most PQ inputs a standard-size transaction can hold). Digest and signature for every PQ input; the full
  preimage for the two small transactions.
- **spend** (40): the 29 valid inputs, and 11 that must fail, each with the exact error: key does not match the hash, reserved
  algorithm id, short public key, three pushes, one push, a non-push opcode in the scriptSig, signature over a different
  amount, signature under a different FIPS 204 context string, an output changed after signing, a short signature, and a
  valid spend evaluated before activation.

## Checked on 2026-11-11
- The generator reproduces `pqsig_vectors.json` exactly (dilithium-py 1.4.0, Python 3.14).
- `verify_p2pqh.py`: 68 checks, 0 mismatches; all 27 PQ inputs of the two mainnet transactions verify (block 4,255,329,
  the first PQ spend on Blazecoin mainnet, 26 inputs; block 4,300,096, one input).
- Signing is deterministic (FIPS 204 with rnd = 0), so signatures are reproducible byte for byte.

## Not covered yet
- No vector for an element over 5,000 bytes (`PUSH_SIZE`) or for the sigop count.
- No negative vector taken from mainnet (there cannot be one: invalid spends are never mined).
- Wallet-level vectors (descriptor strings, seed backup format) are in the wallet repo, not here.
