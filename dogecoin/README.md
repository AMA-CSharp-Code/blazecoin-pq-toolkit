# A post-quantum key-hash spend for Dogecoin Core, as a soft fork: regtest implementation

Two patches against Dogecoin Core 1.14.99 (`dogecoin/dogecoin` master at `b38c83f`, 9 November 2026 UTC) that add the
design sketched in `DESIGN-COMPARISON.md`, section 6, and run it on regtest. Not a proposal and not scheduled on
any live network: the activation height is set to never on mainnet and testnet. It exists so that the Phase 2
questions in Dogecoin's own draft have a running answer to look at, and so the costs are measured on their code
rather than estimated from ours.

## What it does

- `OP_NOP10` becomes `OP_CHECKPQSIGVERIFY` once the chain passes `Consensus::Params::PQSigHeight` (1,500 on
  regtest). To a node without the rule the opcode is still a no-op, so this is a soft fork.
- The redeem script is 34 bytes, `<32-byte key hash> OP_CHECKPQSIGVERIFY`, placed behind ordinary P2SH (pay to script hash), so every
  existing wallet can pay to it today. No new address format. The price is that P2SH's HASH160 reduces the
  output's commitment to 160 bits (about 2^80 work for a quantum preimage search by Grover's algorithm); the
  bare 34-byte output form would keep the 32-byte commitment.
- The spend carries the ML-DSA-44 signature (2,420 bytes) and key blob (1 algorithm byte + 1,312-byte key) in
  canonical chunks under the untouched 520-byte element limit: five pushes of 520, 520, 520, 520, 340 and three
  of 520, 520, 273, then the redeem script. The sizes are fixed by the rule so nobody can re-split the pushes
  and change the txid.
- The opcode reassembles the chunks, checks `TaggedHash("Dogecoin/PQKH/v1", keyblob)` against the committed
  hash, checks the algorithm byte, and verifies FIPS 204 ML-DSA-44 under the context string `dogecoin-tx-v1`
  over a BIP-143-shaped digest that commits to the amount and is computed once per transaction.
- Policy admits exactly that nine-push shape past the 1,650-byte scriptSig limit, up to 3,800 bytes.
- `getblockchaininfo` lists `pqsig` under `softforks` with its activation height.

## What the tests show

`src/test/pq_tests.cpp` (three cases, in Dogecoin's unit suite, which passes whole): the honest spend verifies
under the new rules and evaluates true under the old ones; nine mutations each fail with the expected error (bad
signature byte, wrong amount, another key behind the hash, reserved algorithm id, two non-canonical chunkings,
a missing chunk, an extra push, an output changed after signing).

`qa/rpc-tests/pqsig-softfork.py` (two regtest nodes, the spend built and signed in Python with dilithium-py so the
node is the only thing under test): before the activation height a block carrying a spend with a **bad**
signature is accepted by consensus and one with a good signature relays and mines; after the height the
bad-signature block is rejected by `ConnectBlock` and the good spend still goes through; then the mutations and
the policy limit at the mempool door.

Measured on regtest: scriptSig 3,792 bytes; a one-input, one-output spend 3,879 bytes against a 226-byte classic transaction made by the wallet, which has one input and two outputs (a payment and its change): 17.2 times, between transactions of different shape. Blazecoin's deployed two-push type has a 3,739-byte scriptSig and a
3,782-byte input, against 3,792 and 3,835 here: 53 bytes more per input, 18 of push overhead and the 35-byte
redeem-script push.

## A finding about activation

The first design assumed BIP-9 version bits. They cannot work on Dogecoin: the miner pins the base block version at 4
(`ComputeBlockVersion` is commented out in `miner.cpp`), and the AuxPoW (auxiliary proof of work, that is, merged mining) header packs the merge-mining chain id
into the bits BIP-9 reads, so no deployment can reach `locked_in`: it waits in `started` until its timeout and then fails. That is consistent with SegWit being marked disabled in
Dogecoin's chain parameters and with the CSV deployment window (May 2016 to May 2017) expiring without activating.
The patches therefore activate by height, which is how Dogecoin's consensus parameters now record BIP-65 and BIP-66
(they first activated by block-version supermajority; Marscoin's code records the
same version-bits constraint for its own AuxPoW chain, in `src/consensus/params.h`). A real deployment would need a coordinated height, agreed with the merge-mining pools.

## Build and run

```
git clone https://github.com/dogecoin/dogecoin && cd dogecoin && git checkout b38c83f
git am /path/to/0001-*.patch /path/to/0002-*.patch
./autogen.sh && ./configure --without-gui --disable-bench --with-incompatible-bdb && make -j
./src/test/test_dogecoin -t pq_tests
python3 qa/rpc-tests/pqsig-softfork.py --srcdir=src      # needs dilithium-py; see below
```

The functional test imports `dilithium_py` (pure Python ML-DSA, `pip install dilithium-py`). Dogecoin's qa
framework also imports the `ltc_scrypt` C extension for block hashes; a four-line stand-in is enough for this test and is in this folder: `ltc_scrypt.py`, which calls `hashlib.scrypt(data, salt=data, n=1024, r=1, p=1, dklen=32)` as `getPoWHash`. Copy it into `qa/rpc-tests/` before running the test.

Apply both patches. Patch 1 on its own carries the functional test as first written, for version-bits activation, which the section above explains cannot happen; patch 2 replaces the activation and that test.

## Not done

Wallet support (the spend is built by hand), P2P relay tests, any schedule for a live network, review by anyone
from Dogecoin, Falcon or any scheme other than ML-DSA-44, multisig. The vendored `src/crypto/mldsa/` is the
pq-crystals reference implementation (released by its authors as public domain under CC0, with Apache 2.0 or GPL 2.0
offered as alternatives), configured for deterministic signing with no RNG (random number generator).

MIT, like the rest of the code in this repository and like Dogecoin Core itself.
