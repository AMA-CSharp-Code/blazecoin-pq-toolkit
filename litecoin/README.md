# The same post-quantum key-hash output on Litecoin Core: regtest port

One patch against Litecoin Core `v0.21.5.8` (`litecoin-project/litecoin`, commit `ec1b6489`, the latest release on
16 November 2026) that ports the Bitcoin Core regtest implementation in `../bitcoin/` to an older codebase with MWEB (MimbleWimble Extension Blocks). Not
a proposal; the deployment is set to never activate on mainnet or testnet.

## What it does

- The same output and spend as the Bitcoin patch: `OP_2 <TaggedHash("PQKeyHash", keyblob)>` as witness version 2,
  a witness of exactly two items `<signature 2420> <keyblob 1313>`, the BIP-341 message layout with `ext_flag` 2
  and SIGHASH_DEFAULT only, FIPS 204 ML-DSA-44, deterministic signing. As there, witness version 2 with a 32-byte
  program is BIP-360's P2MR (pay to Merkle root) template, so the choice is a regtest placeholder.
- **The context string is `litecoin-pq-v1`, not `bitcoin-pq-v1`.** A signature made for one build does not verify
  on the other. That is deliberate (no cross-chain replay) and a unit test asserts it.
- `DEPLOYMENT_PQ` as an old-style BIP-9 deployment on bit 3 (Taproot uses 2, MWEB 4): ALWAYS_ACTIVE on regtest,
  NEVER_ACTIVE on mainnet and testnet. `SCRIPT_VERIFY_PQ` is script flag bit 21 and joins the standard flag set.
- No collision with MWEB: witness version 2 is unused on Litecoin (Taproot is 1, the MWEB HogAddr 8, peg-in 9).
- The address needs no new code: the output encodes as Bech32m under the segwit prefix (`rltc1z...` on regtest).
- Relay policy, dust pricing and the precomputation of the BIP-341 single hashes follow the Bitcoin patch.
  `DeferringSignatureChecker` forwards the new check.
- The tree is C++14 with autotools, so the sources are added to `src/Makefile.am` and
  `src/Makefile.test.include`, and `Span`, `CHashWriter` and `tx.nVersion` stand in for the newer APIs.
- Three existing functional tests are modified because the program is now defined on regtest: `p2p_segwit.py`
  uses a 33-byte program for version 2, `feature_taproot.py` skips version 2 with a 32-byte program, and
  `rpc_blockchain.py` expects the `pq` entry under `softforks`; `transaction_tests.cpp` gains the flag name.

## Measured

| | Litecoin regtest | Bitcoin regtest |
|---|---|---|
| Post-quantum input | 3,904 WU | 3,904 WU |
| Honest spend, one input and one 34-byte output script | 4,118 WU / 1,030 vB | 4,118 WU / 1,030 vB |
| Witness | 3,740 bytes | 3,740 bytes |

They match because the transaction format and the weight rule are the same and MWEB adds nothing to a transaction
with no MWEB part. The dust threshold for the new output is 30,570 litoshi against 2,940 for P2WPKH (pay to witness public key hash): ten times
Bitcoin's figures, because Litecoin's default dust rate is ten times higher.

## What differs in behaviour

- **The error label for a bad signature.** In Litecoin 0.21 the mandatory script-flag set is P2SH (pay to script hash) alone, so a
  spend with a bad post-quantum signature is rejected as
  `non-mandatory-script-verify-flag (PQ signature is invalid)`, in the mempool and in a block alike (the Bitcoin
  build says `block-script-verify-flag-failed`). The block is still invalid; only the label differs. With the default parallel script checking, one run reported a
  block with a bad signature as a bare `block-validation-failed`; the functional test starts its node with
  `-par=1`, as Litecoin's own `feature_taproot.py` does, to get the script error.
- **Missing transaction data.** 0.21 has no `MissingDataBehavior`; the new check fails closed with
  `SCRIPT_ERR_UNKNOWN_ERROR` when the precomputed data or the spent outputs are absent. A unit test covers it.
- **Deployments in RPC.** There is no `getdeploymentinfo`; the deployment appears under `softforks` in
  `getblockchaininfo`, and only on regtest, because 0.21 hides never-active deployments.
- **Litecoin has no list of all consensus flags** of the kind Bitcoin Core master keeps
  (`GetAllConsensusScriptFlags`), so the omission fixed in the Bitcoin patch has no counterpart here.

## Tests

- Unit: the whole `test_litecoin` binary, 533 cases, passes; `pq_witness_tests` has 6 cases (four of the Bitcoin
  patch's five, without the deferring-checker case, plus relay policy with the deployment active and inactive, and
  the fail-closed case).
- Functional: the new `feature_pq_witness.py` passes, and so do twelve existing scripts run with it:
  `rpc_blockchain`, `feature_segwit --legacy-wallet`, `feature_taproot`, `p2p_segwit`, `mweb_basic`,
  `mweb_weight`, `mweb_mempool`, `mweb_mining`, `feature_versionbits_warning`, `mempool_accept`, `feature_block`,
  `rpc_rawtransaction`.
- The exported patch was applied to a second clean checkout of the tag, built, and passed `pq_witness_tests` and
  `feature_pq_witness.py` there.

One thing about the environment, not the port: Litecoin 0.21's test framework calls `hashlib.new('ripemd160')`,
which OpenSSL 3 does not offer by default (Ubuntu 22.04). Five of the existing scripts fail for that reason on the
unmodified tag as well. `openssl-legacy.cnf` loads OpenSSL's legacy provider for the test processes only; the
functional-test script sets it.

## Status and what was not checked

Regtest only; not run on any test network; not reviewed by anyone outside. Not checked: the full functional suite
(13 scripts ran), activation by signalling (only always-active and never-active were exercised), a post-quantum
spend after MWEB activates on regtest or mixed with peg-ins and peg-outs, the P2SH-wrapped form, multi-input
transactions, reorganisations, validation cost, the wallet, GUI, PSBT (partially signed Bitcoin transaction), descriptors, fuzz targets, the
`libbitcoinconsensus` interface, and other compilers and platforms. `DeferringSignatureChecker` forwards the new
check in the code, but no Litecoin unit test covers it.

Porting the design back also improved the Bitcoin patch: it showed that `DeferringSignatureChecker` did not
forward the new check there and that two of Bitcoin Core's own functional tests assumed the program was
undefined. Both are fixed in `../bitcoin/`.

## Build and run (Ubuntu 22.04)

System packages: `build-essential libtool autotools-dev automake pkg-config bsdmainutils python3 libevent-dev
libboost-system-dev libboost-filesystem-dev libboost-test-dev libboost-thread-dev libssl-dev libdb++-dev
libsqlite3-dev libfmt-dev` (`libfmt-dev` is required by Litecoin's `configure` for MWEB). Python modules for the
functional tests: `blake3` and `dilithium-py`.

```
git clone --branch v0.21.5.8 --depth 1 https://github.com/litecoin-project/litecoin.git && cd litecoin
git am /path/to/0001-*.patch          # keep the patch's LF line endings
./autogen.sh
./configure --without-gui --with-incompatible-bdb --disable-bench --without-miniupnpc --without-natpmp --disable-zmq
make -j
src/test/test_litecoin --run_test=pq_witness_tests
OPENSSL_CONF=/path/to/openssl-legacy.cnf python3 test/functional/feature_pq_witness.py
```

Against a built tree, `unit-tests.sh` in this folder runs `pq_witness_tests` and 20 neighbouring suites (not the
whole binary), and `functional-tests.sh` runs the 13 functional scripts listed above.

MIT, like the rest of the code in this repository. The vendored `src/crypto/mldsa/` is the pq-crystals reference
implementation, byte-identical to the copy in the Bitcoin patch. The vendored code keeps its authors' terms: public domain under CC0, with Apache 2.0 or GPL 2.0 offered as alternatives.
