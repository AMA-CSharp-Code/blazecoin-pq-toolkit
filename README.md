# Blazecoin post-quantum toolkit

What it cost, what broke and how to check it: ML-DSA-44 (NIST FIPS 204) as a native output type on a scrypt
proof-of-work chain that has run since 2014, built on a Bitcoin Core 28 fork with legacy script and no SegWit.
Live on mainnet since block 4,250,000 (16 September 2026). Everything here is free to use; see [Licences](#licences)
and the [patent pledge](PATENT-PLEDGE.md).

Written for the people doing the same work on Dogecoin, Litecoin and Bitcoin. It is a data point, not a proposal.

## Start here

| Read | If you want |
|---|---|
| [REPORT.md](REPORT.md) | the field report: design in one page, measured costs (CPU, bytes, a 24-block consolidation run), what eight weeks of mainnet showed (a load test by one operator: 99.98% of the post-quantum spends are the operator's own), the thirteen findings and their fixes, where the design is weaker, what does and does not carry to other chains |
| [BITCOIN-PORTING-NOTE.md](BITCOIN-PORTING-NOTE.md) | the companion note: what would have to change to carry this output type to Bitcoin, what it would cost on Bitcoin's limits, where BIP-360 already went instead, and the Blazecoin Quantum Bridge (section 8): the three states a coin passes through and the conversion wallet that carries it across them, on one chain |
| [DEFECTS.md](DEFECTS.md) | every finding with its severity and, where there is a fix, the commit and the test that pins it |
| [DESIGN-COMPARISON.md](DESIGN-COMPARISON.md) | this design beside Dogecoin's draft, BIP-360, BIP-361, SHRINCS, Marscoin and Soqucoin, from each project's own text |

## Check it in five minutes

```
cd toolkit/vectors
pip install dilithium-py          # pure-Python ML-DSA, used only by the verifier and the generator
python verify_p2pqh.py            # 68 synthetic checks + 27 real mainnet inputs, expected: 0 mismatches
```

`verify_p2pqh.py` is about 150 lines and shares no code with the node or the wallets. It applies every consensus
rule for a post-quantum input, in the node's order, to `pqsig_vectors.json` (synthetic, deterministic, reproducible
byte for byte by `generate_pqsig_vectors.py`) and to `mainnet_examples.json` (two real transactions with every
prevout, including the first post-quantum spend on the chain: 26 inputs, block 4,255,329). The 68 synthetic
checks are 39 spend cases (the 40 in the file less the one that is evaluated before activation, which the
verifier does not run) and 29 digests.

## Which of your coins are exposed

A separate tool, for your own coins on Bitcoin or Blazecoin. It is the first job of the Blazecoin Quantum Bridge
(REPORT.md section 10.3; porting note, section 8):

```
cd toolkit/triage
python pq_triage.py --descriptor "wpkh(zpub6r.../<0;1>/*)"    # or addresses; watch-only, no keys
```

It tells you which coins are exposed (key already on the chain), which are hash-safe until spent, and which
are post-quantum; `toolkit/triage/README.md` has the rules and the limits.

## What is in the repository

| Path | What it gives you |
|---|---|
| `toolkit/vectors/verify_p2pqh.py` | the reference verifier |
| `toolkit/vectors/pqsig_vectors.json`, `toolkit/vectors/generate_pqsig_vectors.py` | 3 derivations, 29 signed inputs across 3 transactions, 40 spend cases of which 11 must fail with a named error; the generator |
| `toolkit/vectors/mainnet_examples.json`, `toolkit/vectors/fetch_mainnet_examples.py` | the two real transactions and how the file was made |
| `dogecoin/0001-*.patch`, `0002-*.patch`, `README.md` | the design-comparison section 6 soft fork built on Dogecoin Core 1.14.99 and run on regtest: OP_NOP10 as OP_CHECKPQSIGVERIFY, canonical 520-byte chunks, P2SH-wrapped, activation by height; unit and functional tests; measured sizes; the version-bits finding |
| `bitcoin/0001-*.patch`, `README.md` | the porting note's section 4 built on Bitcoin Core master and run on regtest: the output as witness version 2, unit tests and a two-node soft-fork test; measured weights; the places in Core that had to learn the new program |
| `litecoin/0001-*.patch`, `README.md`, test scripts | the same output type ported to Litecoin Core v0.21.5.8 (MWEB, autotools, C++14) and run on regtest: identical weights, no MWEB collision, its own context string; what differs on an older codebase |
| `toolkit/triage/pq_triage.py`, `toolkit/triage/test_pq_triage.py` | the Bridge's first job as a watch-only tool: addresses, xpub or descriptor in, exposed / hash-safe / post-quantum out, for Bitcoin (any Esplora) and Blazecoin (the project's block indexer); standard library only; tests on the published BIP vectors |
| `toolkit/recount_from_node.py` | recounts the mainnet figures of REPORT.md section 6 from any full node over RPC, without an index (read-only; about four minutes) |
| `toolkit/consolidation_run.py` | reads a node wallet and reports a consolidation run (inputs, bytes, fees, blocks filled); the figures in REPORT.md section 5 |
| `toolkit/queries/*.sql` | the counting queries behind REPORT.md section 6, against the project's block indexer schema; adapt the table names; the block range counted there is already in the queries |

The node-side material lives in the node repository, `github.com/AMA-CSharp-Code/blazecoin-core` (MIT). It is a
snapshot of the development tree with its own history, so commit hashes quoted in this package will not resolve
there. The benchmark, known-answer tests and fuzz targets listed below are in it from commit `4634755`
(17 November 2026); copies are also in this repository under [`node-files/`](node-files/README.md), with checksums:

| Path there | What it is |
|---|---|
| `PQ_SIGNATURES.md` | the specification and its decision log, activation record and test record (it carries a dated correction to its sigop paragraph: see the report's reference list) |
| `src/script/pq.h`, `src/script/pq.cpp`, `src/crypto/mldsa44.h`, `src/crypto/mldsa44.cpp`, `src/crypto/mldsa/` | the consensus code, the wrapper, and the vendored FIPS 204 reference implementation |
| `src/bench/pq_verify.cpp` | the benchmark in REPORT.md section 5 |
| `src/test/mldsa44_kat_tests.cpp`, `src/test/mldsa44_acvp_data.h` | NIST's ACVP known-answer cases for ML-DSA-44 (79 cases) pinned as unit tests |
| `src/test/pqsig_tests.cpp` | the node's tests against `pqsig_vectors.json` |
| `src/test/fuzz/pq_script.cpp`, `test/pqsig/run_pq_fuzz_seeds.py` | three fuzz targets for the script path and a seed-corpus runner |
| `test/functional/feature_blazecoin_pqsig.py` | the functional test that signs in Python, independent of the wallet |

## Numbers people ask for first

- ML-DSA-44 public key 1,312 bytes, signature 2,420 bytes; a post-quantum input is about 25.6 times the bytes of a
  P2PKH (pay to public key hash) input and about 1.8 times its CPU on this node (REPORT.md section 5).
- 26 post-quantum inputs is the largest transaction that stays under the 100 KB standardness limit here.
- Wallets sign deterministically (FIPS 204 with rnd = 0); consensus accepts any valid FIPS 204 signature. FIPS 204
  context string bound to the chain, hash-committed key, 32-byte key hash, address prefix `BQ`, 52 characters.
  The output type is called P2PQH, pay to post-quantum key hash, in the code and the toolkit.

## Changes in version 1.0.1 (17 November 2026)

Version 1.0 was published earlier the same day. A search of the Delving Bitcoin forum after publication found related
work that 1.0 did not cite. Version 1.0.1 adds it and corrects what it changes. No measurement, test vector, patch or
defect entry is changed.

- **Two drafts for Bitcoin describe almost the same witness output for ML-DSA-65** as the regtest build in this
  repository: Echelon Labs Research (April 2026) and Zaenus (November 2026). The porting note, section 6, now credits
  them with the design shape, says what the build here does and does not add beside them, and records the objections
  already raised to a single-key ML-DSA output.
- **A draft exposure classification for existing Bitcoin outputs** (duncan0k, September 2026) already covers the sorting
  of coins and the move-exposed-first advice that this repository calls the first job of the Blazecoin Quantum Bridge.
  The porting note (section 8), the report (section 10.3) and the triage README now say so.
- **KVANTA5**, a new chain with ML-DSA-87 from its first block, posted mainnet figures in July 2026 (report, section 10.2).
- **The state of Bitcoin's own discussion of output types** is described (porting note, section 6), and the date the
  proposal that became BIP-360 was first posted is corrected to 8 June 2024.

## Contact and corrections

hyperminer on bitcointalk, or admin@blazecoin.co.uk. If a number here does not match what you measure, say so.
The toolkit reproduces the sizes, the vectors and the regtest results; the benchmark needs your own hardware,
and the mainnet counts need a chain index or a full node (the queries and `toolkit/recount_from_node.py` are
given; which addresses are the operator's is my own attribution and cannot be checked from outside). REPORT.md section 11 says which is which.

## Licences

Code, data and patches (`toolkit/`, `bitcoin/`, `litecoin/`, `dogecoin/`, `node-files/`): MIT, see [LICENSE](LICENSE). Documents:
CC BY 4.0, see [LICENSE-DOCS](LICENSE-DOCS).
No patents have been or will be sought on any of it: [PATENT-PLEDGE.md](PATENT-PLEDGE.md).
