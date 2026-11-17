# A post-quantum key-hash output as witness version 2 for Bitcoin Core: regtest implementation

One patch against Bitcoin Core master (`bitcoin/bitcoin` `a527a00`, 13 November 2026, version 32.99, the development line after the v32 branch) that
builds section 4 of `BITCOIN-PORTING-NOTE.md` and runs it on regtest. Not a proposal; the deployment is set
never to activate on any live network.

## What it does

- Witness version 2 with a 32-byte program: `OP_2 <TaggedHash("PQKeyHash", keyblob)>`. Bech32m address like any
  witness program. The key blob is one algorithm byte (0x01 = ML-DSA-44) plus the 1,312-byte public key.
  Witness version 2 with a 32-byte program is the template BIP-360 assigns to P2MR (pay to Merkle root), so the choice here is a
  regtest placeholder.
- Spend: empty scriptSig, witness of exactly two items, `<signature 2420> <keyblob 1313>`. No annex, no script path.
- Message: the BIP-341 layout with `ext_flag` 2 and SIGHASH_DEFAULT only, under the tag `PQSighash`; verified with
  FIPS 204 ML-DSA-44 under the context string `bitcoin-pq-v1`. Deterministic signing, no RNG (random number generator) in consensus code.
- `DEPLOYMENT_PQ` as a BIP-9 deployment (bit 3): ALWAYS_ACTIVE on regtest, NEVER_ACTIVE on mainnet, testnet3,
  testnet4 and signet. `SCRIPT_VERIFY_PQ` joins the consensus and standard flag sets (Core master guards the
  consensus set with a consteval allow-list, so a new consensus flag has to be added there explicitly, and
  keeps a second list of all consensus flags, `GetAllConsensusScriptFlags`, which needs it too).
- Dust for the new output type is priced from its real 3,740-byte witness.
- Relay policy treats a spend of the new program as standard only where the deployment is active; elsewhere it
  stays an undefined witness version and is refused at the mempool door.
- The BIP-341 single hashes are precomputed for a transaction that spends the new program, as they are for
  Taproot (Core prepares them only when it sees an `OP_1` output; a new version that reuses the message has to
  be added there; Marscoin's branch needed the same change, its test is `p2wpqh_precomputation_detects_spends`).
- `DeferringSignatureChecker` forwards the new check to the checker it wraps, as it does the Schnorr check.
- Three existing functional tests are modified, because on regtest the program is now defined and the deployment
  is listed: `p2p_segwit.py` uses a 33-byte program for version 2, `feature_taproot.py` skips version 2 with a
  32-byte program, and `rpc_blockchain.py` expects the `pq` deployment and the `PQ` flag in `getdeploymentinfo`.

## Measured (unit test, `src/test/pq_witness_tests.cpp`)

- Input weight **3,904 WU (weight units)**; a one-input, one-output spend 3,986 WU / 997 vB (with a
  one-byte output script; the functional test below uses a 34-byte one, which adds 132 WU). The porting note's section 5 arithmetic said 3,904 WU; the build agrees. The test asserts these three figures and the dust threshold below as exact values.
- Dust threshold for the new output: **3,057 sat** against 294 sat for P2WPKH (pay to witness public key hash) at the default dust rate.
- The honest spend verifies under the new rules and is anyone-can-spend to a node without them (discouraged by
  policy); nine mutations each fail with the expected error (six distinct errors). The suite has five cases; one checks that a wrapped
  checker passes the new check on.
- Core's whole unit test binary (`test_bitcoin`, 822 cases in this build without the wallet) passes with the
  patch.

## Measured (two-node functional test, `test/functional/feature_pq_witness.py`)

node0 is the upgraded node. node1 is started with `-vbparams=pq:1:1` and plays the un-upgraded network.

- The honest spend relays and is mined on the upgraded node: **4,118 WU / 1,030 vB** for one input and one
  34-byte output script, of which the input is **3,904 WU**; the test asserts those three figures and the 3,740-byte witness as exact values. The un-upgraded node refuses to relay it
  (`bad-txns-nonstandard-inputs`).
- **The soft-fork property:** a block carrying a spend with one flipped signature bit is accepted by the
  un-upgraded node and rejected by the upgraded node (`block-script-verify-flag-failed (PQ signature is invalid)`).
- At the upgraded node's mempool door a flipped signature, a key blob that does not hash to the program and a
  third witness item each fail with their own error; a 1,000-sat output of the new type is dust.

## Status

The whole unit test binary and the new functional test pass on regtest, and so do the existing functional tests
`p2p_segwit.py`, `feature_taproot.py`, `rpc_blockchain.py` and `mempool_accept.py`. The rest of the functional
suite was not run; `feature_segwit.py` needs the wallet, which this build leaves out. Not run on any test
network, not reviewed by anyone outside.

The same output type was ported separately to Litecoin Core v0.21.5.8, on regtest only, with the same weights
(`BITCOIN-PORTING-NOTE.md`, section 4). The two-node test found two defects the unit tests had missed (the relay-policy check
and the precomputation above). The Litecoin port and the re-test after it found the rest: `DeferringSignatureChecker`
did not forward the new check, the list of all consensus flags lacked the new flag (Core's `versionbits_tests`
reports it), `p2p_segwit.py` and `feature_taproot.py` assumed version 2 with a 32-byte program was undefined, and
`rpc_blockchain.py` did not expect the new deployment. All are fixed in this patch.

## Build and run

```
git clone https://github.com/bitcoin/bitcoin && cd bitcoin && git checkout a527a00
git am /path/to/0001-*.patch
cmake -B build -G Ninja -DBUILD_GUI=OFF -DENABLE_WALLET=OFF -DENABLE_IPC=OFF -DBUILD_TESTS=ON
cmake --build build -j
./build/bin/test_bitcoin -t pq_witness_tests
python3 build/test/functional/feature_pq_witness.py      # needs dilithium-py
```

MIT, like the code in this repository. The vendored `src/crypto/mldsa/` is the pq-crystals reference implementation. The vendored code keeps its authors' terms: public domain under CC0, with Apache 2.0 or GPL 2.0 offered as alternatives.
