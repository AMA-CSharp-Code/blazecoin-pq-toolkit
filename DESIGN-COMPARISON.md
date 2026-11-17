# Design comparison: what carries over, what does not

hyperminer (bitcointalk), admin@blazecoin.co.uk. Version 1.0.1, 17 November 2026. Companion to the field report (REPORT.md).

Sources were read between 2026-11-11 and 2026-11-17; each entry gives its read date. External claims are taken from the
primary texts in the source list at the end; those that rest on news coverage say so.
What could not be confirmed is listed at the end.

## 1. What Dogecoin's draft is, and is not

Dogecoin's post-quantum draft is the nearest neighbour to this work. It is not a new output type, as a reader of
its title might expect. The draft says:

- Phase 1 is a commitment in an `OP_RETURN` output plus an optional
  two-transaction "carrier" that publishes the key and signature in P2SH (pay to script hash) inputs. Nothing is enforced by consensus:
  the coins are still spent by ECDSA, and the PQ signature rides along as evidence.
- Its Phase 2 is native script validation by a reserved opcode. The draft lists what Phase 2 still has to define:
  opcode assignment, script format, evaluation and failure semantics, activation. **None of it is specified yet.**
- One of its three schemes is the same primitive I use: its "Dilithium2" path is ML-DSA-44 from liboqs (4.6).

The draft leaves Phase 2 unspecified; this chain is one worked example of it, built and run on a legacy-script
codebase, with the cost and the bugs. It is one answer, not the answer, and the activation half does not transfer.

## 2. The proposals, as of 2026-11-16

| | What it specifies | Status | Signature scheme | How it deploys |
|---|---|---|---|---|
| **BIP-360** P2MR (v0.12.1) | An output type: Taproot's script tree with the key path removed. No PQ signature. | Draft | None. "A separate proposal" later | Soft fork, SegWit v2, requires BIPs 340 to 342 |
| **BIP-361** migration and sunset | A timetable: stop sends to quantum-vulnerable addresses, later restrict ECDSA/Schnorr spends | Draft, informational | "TBD post-quantum signature BIP" | Soft fork, phased over years |
| **SHRINCS** draft | A signature scheme only: stateful hash-based path with a stateless fallback | Draft, no BIP number, security proof marked TODO | Hash-based, SHA-256 only, NIST category 1 | Needs a separate output-type and consensus proposal |
| **Dogecoin** PQ signature commitments | Phase 1: `OP_RETURN` commitment + optional P2SH carrier. Phase 2: reserved opcode, unspecified | Draft; Phase 1 tooling merged in libdogecoin, used on mainnet (the draft's own Mainnet Examples section) | Falcon-512, Dilithium2, Raccoon-G-44 | Phase 1 no consensus change; Phase 2 a soft fork |
| **This chain** P2PQH (pay to post-quantum key hash) | Output type, opcode, digest, policy, wallet, addresses | Live on mainnet since block 4,250,000 (2026-09-16) | ML-DSA-44 (FIPS 204 final), category 2 | Flag-height hard fork |
| **Litecoin** | No proposal found (searched 2026-11-11) | | | |
| **Soqucoin** | A new chain: scrypt PoW, merge-mined (AuxPoW), ML-DSA-44 for all transaction signatures, a batch-attestation opcode | By its README: mainnet since 2026-10-13, testnet from 2025-12. Outside audit before launch (Halborn's published report: 2026-02-17 to 2026-03-24) | ML-DSA-44 | New genesis: no fork of an existing chain, no classic-key outputs to migrate |

Soqucoin is described from its own repository (README read 2026-11-12 and again 2026-11-16, with
`doc/ECDSA_ELIMINATION.md` and part of `src/script/interpreter.cpp` on the second date). Its mainnet date is the
project's statement; I did not check it against the chain. It is the opposite case to this chain with the same
primitive: post-quantum from block 1 on a new UTXO (unspent transaction output) set, against a type added to a UTXO set that dates from 2014.
It has no classic-key outputs, no classic spend path to retire and no activation on a live network to carry
out. It is a second place to measure ML-DSA-44 in a scrypt node. Its code uses witness programs: the signature is
2,420 bytes, or 2,421 with a hash-type byte, and sits in the witness with the 1,312-byte key (1,313 with a
prefix byte). I did not determine whether its vendored code is FIPS 204 final or round-3 Dilithium2, and I did
not examine how it limits input counts.

## 3. Side by side

| Question | BIP-360 (+ a future PQ opcode) | SHRINCS draft | Dogecoin draft, Phase 1 | This chain |
|---|---|---|---|---|
| What the output commits to | 32-byte Merkle root of a script tree | n/a (48-byte public key) | Nothing new: a normal P2PKH output | 32-byte tagged hash of `algo_id + public key` |
| Where the signature goes | Witness (discounted 4x) | Witness, presumably | P2SH scriptSig of a second transaction, in 520-byte chunks | scriptSig, one 2,420-byte push (push limit raised to 5,000 for this input type only) |
| Consensus checks the PQ signature | Not until a PQ opcode exists | Not until an output type exists | **No** | **Yes** |
| Protects against a quantum attacker | Long exposure only, until a PQ opcode | Yes, once deployed | No: spend authority is still ECDSA | Yes, for coins on the new type |
| Key + signature bytes per spend | 135-byte witness with a Schnorr leaf (BIP-360's own figure, for a depth-1 tree) | Key + signature: 596 minimum (48 + 548), up to 4,667 on the stateful path (48 + 4,619), 5,825 stateless (48 + 5,777) (draft as of 2026-11-09; still changing) | Dilithium2: 3,732, on top of the normal spend, across two transactions (~5 KB reveal) | 3,733, total input 3,782 |
| Message that is signed | BIP-342 common signature message | Scheme only: a variable-length message and a context string of up to 255 bytes | The legacy sighash of the base transaction | BIP-143-shaped digest under a tagged hash, FIPS 204 context string |
| Script features with PQ | Full tapscript | n/a | None | None: single key only. No PQ multisig, no PQ timelocks |
| Second scheme / agility | New tapscript opcodes (OP_SUCCESSx) or new leaf versions | A scheme only, with no field for choosing between algorithms | Three scheme tags | Algorithm-ID byte inside the hashed key blob; IDs reserved, one active |
| Hybrid with a classic key | Possible in a leaf | No dedicated hybrid; the draft says to combine by concatenation if wanted | Effectively yes: ECDSA still authorises | No, by decision |
| Signer state | None | **Stateful path must never reuse a counter** | None | None (deterministic signing) |
| Old coins | Voluntary | n/a | Unchanged | Voluntary, no sunset |
| Activation | Soft fork | n/a | None needed | Hard fork at a height, one operator |

## 4. For Dogecoin: what carries over

Their draft's own list of Phase 2 open items, with what this chain did. Each is a data point with the test or
measurement that backs it.

1. **Opcode assignment.** I used one opcode byte, `0xba`, valid only when the output being spent matches the
   new 34-byte template. It is not a redefined NOP and is never reachable from an ordinary script. A note on
   the draft's wording. It suggests a soft fork based on OP_SUCCESSx. OP_SUCCESS exists only inside tapscript, and
   the same draft says Dogecoin has no SegWit witness relay. In legacy script the soft-fork tools are NOP
   redefinition or a P2SH-style template that old nodes read as a bare hash check. I took neither route (see 5.1
   and section 6).
2. **Script format.** Output: `0x20 <32-byte hash> OP_CHECKPQSIG`. Spend: exactly two pushes, signature then key
   blob, nothing else. The key blob starts with an algorithm byte, and the hash commits to it, so a later scheme
   needs no new address format. The fixed shape made the size exact (3,782 bytes) and policy simple.
3. **The 520-byte push limit.** Their carrier chunks the material into 520-byte pieces across several inputs
   because of this limit (three inputs for Dilithium2). I raised the element limit to 5,000 bytes for inputs
   spending the new template only. That change is one of the two reasons this chain's type is a hard fork; the other is
   the new opcode, which old nodes reject (section 6).
4. **Evaluation and failure semantics.** Fail closed before activation (the output type is unspendable, and
   non-standard to create). A fixed order of checks with a distinct error for each: push-only, element size, stack
   size, key-hash mismatch, algorithm not active, key length, signature. No sighash-type byte: the signature size
   is exact and `SIGHASH_ALL` is the only mode. The reference verifier in `toolkit/vectors/` is that list in about
   150 lines of Python; the spend vectors pin each error except the element-size one.
5. **The signed message.** Their Phase 1 signs the legacy sighash. I chose a BIP-143-shaped digest: it commits
   to the amount, and the shared hashes are computed once per transaction. Measured consequence (report, section 5): the
   classic path gets slower per input as inputs are added (57 to 64 microseconds at 26 inputs) while the PQ path
   stays flat. The saving is small at 26 inputs and does not depend on
   signature size, because the legacy sighash blanks scriptSigs before hashing; the stronger reason is the amount
   commitment.
6. **Same primitive, different wrapping.** Checked in their source (`src/pqc_dilithium.c`, liboqs 0.15.0): the
   "Dilithium2" path asks liboqs for `ML-DSA-44` first and falls back to round-3 Dilithium2 only if that is absent.
   So both chains use FIPS 204 ML-DSA-44. The differences are around it: they call the plain sign and verify
   functions (empty context string, the library's default signing), and sign the legacy sighash; I use the context
   string `blazecoin-tx-v1`, deterministic signing with no RNG (random number generator) linked into the node, and my own digest. Two differences
   worth noting: a context string is free domain separation between transaction signatures and message signatures, and
   deterministic signing removes the RNG from consensus-adjacent code. Wallets on this chain sign
   deterministically; consensus accepts any valid FIPS 204 signature, hedged or deterministic. FIPS 204
   section 3.4 warns against the deterministic variant where side-channel or fault attacks are a concern, and
   the report lists that as a weakness. Practical upshot: my key-generation vectors
   apply to their build as they stand, and my signature vectors apply to any verifier that can take a context
   string. My full spend vectors do not, because the digest differs.
7. **Cost on a non-SegWit chain.** No witness discount exists, so every byte is full price. Measured here:
   1.8x the CPU of a classic input and 25.6x the bytes; 264 PQ inputs fill a 1 MB block and verify in about 27 ms;
   26 inputs is the standard-transaction ceiling; the byte limit, not CPU, is what binds. Their fee guidance for a
   Dilithium2 reveal (about 5 KB) is consistent with my measured sizes.
8. **The edges that broke** (report, section 7; DEFECTS.md): dust priced for a 148-byte input, an unchecked key length at the wallet
   storage boundary, change silently returning to a classic key, and SegWit-era code paths that are dangerous on
   a chain without SegWit. Dogecoin Core is a different vintage of the codebase, so each needs checking there, not
   assuming; the witness-transaction halt in particular depends on a check that older bases still have.
9. **What Phase 1 buys that I skipped.** Their approach gave them mainnet measurements and tooling with zero
   consensus risk before committing to a design. I went straight to consensus.

## 5. For Dogecoin: what does not carry over

1. **Activation.** One operator ran every node I know of and nearly all the hash rate (my own pool's share; not measured here), so a flag-height hard fork was built,
   announced and activated in three days. Dogecoin has independent miners, merged mining, exchanges and custodians.
   Nothing about this chain's rollout speed transfers, and their draft's soft-fork goal is the right one for their network.
   A soft-fork variant of a template like this chain's is possible on legacy script; section 6 describes one, built and
   run on a Dogecoin Core regtest branch, with the patches in `dogecoin/`.
2. **Scheme choice.** I have no data on Falcon-512 or Raccoon-G. Falcon's signature is about a quarter the size
   of ML-DSA-44's, which matters more on a chain with real fee pressure.
3. **Scale.** About 158,000 PQ spends in eight weeks, 99.98% of them my own, 95% one wallet's consolidation (report, section 6). It
   is a load test of the code path, not evidence about users, fees or relay under contention.
4. **Script.** This chain's type is single-key. It says nothing about PQ multisig, which exchanges and custodians need.

## 6. A soft-fork variant for Dogecoin: built and run on regtest

This chain's type needed a hard fork for two reasons: it uses a new opcode, which old nodes reject, and the 520-byte
element limit stops a 2,420-byte signature being pushed, so I raised it. Legacy script has its own soft-fork
tools, and they are enough to avoid both: a redefined no-op in place of the new opcode, and chunks that stay
under the limit.

**The mechanism.** Redefine one of the unused no-op opcodes (`OP_NOP4` to `OP_NOP10`; CLTV took `OP_NOP2` and CSV
`OP_NOP3` the same way). The branch uses `OP_NOP10`, called `OP_CHECKPQSIGVERIFY` in the patch. An old node executes it as a no-op; an upgraded node gives it meaning and fails the
script when the meaning is not met. Rules only get tighter, so it is a soft fork.

**The 520-byte limit, without raising it.** Push the material in canonical chunks: the signature as four pushes of
520 bytes and one of 340 (2,420 in all), the key blob as two of 520 and one of 273 (1,313: algorithm byte plus the
1,312-byte key). The opcode reassembles them. The chunk sizes must be fixed by the rule, not left to the spender:
the signature sits in the scriptSig, so the txid covers it, and a third party who could re-split the same bytes
into different pushes could change a transaction's id without changing its validity. Fixed sizes remove that.

**The scripts.**

- Output: `<32-byte key hash> OP_NOPn` (34 bytes, the same shape as this chain's with the new opcode in place of `0xba`).
- Or, wrapped in P2SH: redeem script = those 34 bytes, output = ordinary `OP_HASH160 <20> OP_EQUAL`. Then the
  destination is an existing-format Dogecoin P2SH address, and every wallet, exchange and tipping bot on the
  network could pay to it without upgrading. I had to invent an address format and ship it in
  every wallet first; Dogecoin would not.
- Spend: `<sig chunk 1..5> <key chunk 1..3>`, plus the redeem-script push in the P2SH form. Eight or nine pushes,
  about 3,760 bytes (3,792 in the P2SH form). Under the 10,000-byte script size limit, under the 201-operation limit (pushes do not count),
  far under the 1,000-item stack limit.

**What the upgraded node does at the opcode.** Require exactly eight items beneath the hash, with the canonical
sizes; concatenate the key chunks and check that the hash of the key blob equals the committed hash; concatenate
the signature chunks; compute the message as a digest the opcode itself defines (a BIP-143-shaped one
that commits to the amount and is computed once per transaction, as this chain's is: a new opcode defines its own
message, which also retires the quadratic legacy sighash for these inputs); verify ML-DSA-44 under a chain
context string; fail the script on any mismatch; otherwise consume everything and leave true.

**What the old node does.** Pushes the hash, treats the opcode as a no-op, and finds a 32-byte non-zero item on
top of the stack, which is true. So to an old node every such output is spendable by anyone. That is the normal
condition of a soft-forked output type before the network upgrades: pre-0.13.1 Bitcoin nodes saw SegWit outputs
the same way (BIP-141). The usual protections apply and cost nothing: upgraded nodes treat the type as non-standard to
create until activation (old nodes already treat any spend using an upgradable NOP as non-standard:
`SCRIPT_VERIFY_DISCOURAGE_UPGRADABLE_NOPS` is in the standard flags), and nobody
should receive to it before activation is locked in.

**Policy, not consensus.** The 1,650-byte standard scriptSig limit (this and the script limits above are read from
Dogecoin Core at `b38c83f`) and the standard output templates are
relay policy. Upgraded nodes raise the one and admit the other for this template, as I did; no consensus rule
is loosened.

**Activation, and a finding.** As Dogecoin Core stands today, version bits cannot activate a deployment there, and
the reason is worth knowing: the miner never signals (`ComputeBlockVersion` is commented out in `miner.cpp`; blocks carry base
version 4), and the AuxPoW (auxiliary proof of work, that is, merged mining) header packs the merge-mining chain id into the bits BIP-9 reads, so a deployment never gets past `started`. That is consistent with SegWit being marked disabled in Dogecoin's chain parameters and with the CSV
deployment window (May 2016 to May 2017) expiring without activating. Marscoin's code records the same constraint
for its own AuxPoW chain (`src/consensus/params.h`, section 9). The branch
therefore activates the way Dogecoin's consensus parameters now record its own soft forks (BIP-65 and BIP-66, which
first activated by block-version supermajority): a height in the consensus parameters,
1,500 on regtest, never on mainnet and testnet. A real deployment is a coordination problem rather than a
signalling one: Dogecoin has taken merge-mined (AuxPoW) blocks since block 371,337 (its chain
parameters) and shares scrypt with Litecoin, so the pools that merge-mine the two would have to take part.

**Where it is worse than the deployed type.** An extra 53 bytes per input (scriptSig 3,792 against 3,739;
input 3,835 against 3,782): 18 of push overhead and the 35-byte redeem-script push; the anyone-can-spend view on un-upgraded nodes during the transition;
a nine-push spend that is less tidy to specify and test than this chain's two-push one. The P2SH form has a further cost:
wrapping the 32-byte key hash behind P2SH's HASH160 reduces the output's commitment to 160 bits, about 2^80 work
for a quantum preimage search by Grover's algorithm; BIP-360 keeps a 32-byte program for its outputs and gives
the margin as its reason ("128 bits of collision resistance and 256 bits of preimage resistance"). The bare
34-byte output form keeps the 32-byte commitment. A larger scheme later (ML-DSA-65,
3,309-byte signatures) means seven signature chunks, not a new limit. **Where it is better:** no hard fork, no new
address format, no wallet upgrade to pay into it.

**What it leaves exactly where it was.** Coins that never move, multisig, and the choice of scheme. Falcon-512
would be four chunks in total (666-byte signature in the padded format, 897-byte key; Dogecoin's draft uses the
variable-length encoding and lists about 690 bytes), with a signature about a quarter the size; I have no data on it.

**Built and measured (2026-11-13).** The branch adds the opcode, the chunk reassembly, the digest, the policy
exception and the height, vendors the same ML-DSA-44 reference implementation this chain's node uses, and carries two
tests. The unit test (three cases, inside Dogecoin's own suite, which still passes whole) checks the honest
spend under the new rules, its truth under the old ones, and nine mutations each failing with the expected error.
The regtest functional test builds and signs the spend in Python with an independent ML-DSA implementation, so
the node is the only thing under test, and shows the soft-fork property directly: before the activation
height a block carrying a spend with a bad signature is accepted by consensus and a good one relays and mines;
after the height the bad-signature block is rejected by `ConnectBlock` and the good spend still goes through;
then the mutations and the policy limit at the mempool door. Measured on Dogecoin Core's code: scriptSig 3,792 bytes; a
one-input, one-output spend 3,879 bytes against a 226-byte classic transaction made by the wallet, which has one input and two outputs (a payment and its change): 17.2 times, between transactions of different shape. About
850 lines added outside the vendored reference directory (`git diff --stat` against the base commit). Not done: wallet support, relay tests, any live-network
schedule, review by anyone from Dogecoin.

## 7. For Bitcoin researchers: one data point, and its limits

**Does not carry over**
- The output type as deployed. P2MR (pay to Merkle root) lives in SegWit v2 with tapscript; this chain's lives in legacy script because this
  chain has neither. The deployed form does not port; the porting note carries the commitment as a witness
  program (its section 4) and discusses it as a P2MR leaf (its section 6).
- The scheme. The SHRINCS draft argues for hash-based signatures on the grounds that coins sit unspent for a long
  time and SHA-256 is already trusted. I chose a lattice scheme for size and library support. That rests on a
  less conservative assumption, and the draft's reasoning against it is fair.
- The economics. Bitcoin's witness discount and fee market change every size argument. This chain has no fee pressure.
- The activation. See 5.1.

**May be useful as evidence**
- **Bytes bind before CPU.** Per byte, ML-DSA verification is about 14x cheaper than ECDSA on my build. The
  SHRINCS draft (as of 2026-11-09) makes the same kind of claim for a hash-based scheme against Schnorr. One
  measurement and one draft's claim point the same way: validation
  cost limits should be thought of in bytes.
- **Large inputs change the shape of consolidation.** With a 26-input ceiling, one wallet's routine merge became
  hundreds of near-maximum-size transactions. That this was 95% of PQ traffic reflects who used the chain, not
  the signature size. Wallet history tools broke on those transactions.
- **Edge defects generalise in kind, not in detail.** The change-address downgrade (DEFECTS.md, A3) has a direct
  P2MR analogue: a wallet that receives to P2MR but sends change to a key-path Taproot output. The dust and fee
  constants are the same class of bug wherever an input size is assumed.
- **State.** I avoided signer state entirely. SHRINCS's compact path needs it, and its draft spends several
  sections on managing it. My wallet-side defects were all in defaults and storage boundaries without any state
  to manage, which suggests where a stateful scheme's bugs would cluster.
- **Voluntary migration (relevant to BIP-361).** PQ addresses have been usable here for eight weeks.
  They became the default for receiving, change and sweeps in the desktop and light wallets on 2026-09-28, twelve days after
  activation; the node's own wallet still defaults to classic addresses; and holders of wallets created before
  the fork could not migrate in place (DEFECTS.md, A4). Outside my own wallets, 23 addresses received PQ outputs
  and 37 PQ spends were made (report, section 6), on a chain with very few active outside users at all (my observation; not counted). The
  figures do not contradict BIP-361's premise that voluntary migration is slow; they are too small to support it.
- **The notification channel** (DEFECTS.md, B1): whatever tells light wallets that the rules change at a height is
  part of the fork's attack surface.

## 8. Where this design is weaker, stated plainly

1. It is a hard fork, acceptable only because one operator ran the network.
2. It relies on one lattice scheme with no hybrid. If ML-DSA-44 falls, the algorithm byte lets a new scheme be
   added, but coins already on the old scheme would have to move again.
3. NIST category 2 on newer (lattice) assumptions, where SHRINCS aims at category 1 on SHA-256 alone.
4. Single key only: no PQ multisig, no PQ scripts.
5. No witness discount and no fee floor, so the size cost is hidden here in a way it would not be elsewhere.
6. No sunset: exposed classic coins stay exposed until their owners move them. The five largest exposed balances
   have been dormant since between 2016 and 2018 and are not mine (checked on 2026-09-14 and recorded in the node repository's
   `PQ_SIGNATURES.md`).
7. No formal audit. NIST known-answer vectors pinned and three fuzz targets with a first short campaign (about 35
   minutes, 2026-11-13); no sustained fuzzing yet.

The report, section 9, has the full list of ten, including deterministic signing, the sigop constant and the
speed of the build.

## 9. Related work: other routes that avoid a hard fork

Others have worked on the same problem. The table is drawn from the primary texts; a row that rests on news
coverage says so.

| Work | Fork | State | What it protects | Weak point |
|---|---|---|---|---|
| QSB, "Quantum-Safe Bitcoin Transactions Without Softforks" (Avihu Mordechai Levy, StarkWare, paper dated 2026-04-09) | None: a hash-based one-time signature (Lamport/HORS) over a transaction digest, built in today's Bitcoin Script | One transaction mined on Bitcoin mainnet (StarkWare's post of 2026-08-26 gives the txid) | The coins that use it, transaction by transaction | Must fit the legacy script limits of 201 opcodes and 10,000 bytes; needs off-chain GPU work the paper estimates at a few hundred dollars; non-standard, so it is submitted directly to a miner; the paper calls itself "a last-resort measure" and says protocol-level changes are still needed |
| Taproot script path, then disable the key path (Matt Corallo, bitcoin-dev, Dec 2024); security argued in Tim Ruffing, "The Post-Quantum Security of Bitcoin's Taproot as a Commitment Scheme" (IACR ePrint 2025/1307) | Two soft forks: add PQ signatures to script, later switch off Schnorr/ECDSA | Proof plus a plan | Taproot coins once the key path is disabled | Protection arrives only with the second soft fork, which disables key-path spends |
| Commit, delay, reveal ("Fawkescoin" variant, Tadge Dryja, bitcoin-dev, May 2025; pre-emptive variant, Leo Wandersleb, June 2025; BIP-360 traces the idea to a 2018 bitcoin-dev post, "Re: Transition to post-quantum") | Soft fork | Mailing-list proposals | Only coins whose public key was never revealed | Emergency measure; front-running and delay length argued over |
| BIP-360 (P2MR) and BIP-361 (sunset) | Soft forks | Drafts | New outputs; then old signatures retired | Not yet activated; the sunset restricts spends under the old signatures to a rescue protocol, and coins whose owners never act become unspendable |
| Witness version 3 key-path spending, ML-DSA-65 (Echelon Labs Research; BIP draft dated 2026-03-31, `btcpqresearch/bip-pq-witness-v3` commit `7bbfb29`; Delving Bitcoin topic 2422, 2026-04-16) | Soft fork (BIP-9) | Draft with a Bitcoin Core patch and functional tests (I read the draft and the post, not the patch) | New coins sent to the new output; migration is left to other proposals | Single key only; about 5,600 WU a spend by its own figure; reference code depends on liboqs; no second implementation, by its own list of gaps |
| Post-quantum address format, ML-DSA-65 (Zaenus, `Zaenus/btc-safe` commit `4e09003`; Delving Bitcoin topic 3067, 2026-11-13, revised to 0.2 the same day) | Soft fork | Draft with an off-chain reference implementation and test vectors | New coins sent to the new output | Single key only; 5,433 WU an input by its own table; Bitcoin Core benchmarks still to do, by its author |
| Marscoin P2WPQH (`marscoin/marscoin`, branch `feat/pq-witness-v2`, commit `8843ef7`, April 2026; FIPS 205 and a completed signed message in October 2026, PRs 61 and 64) | Soft fork by buried height | Development branch; regtest and its "marsqnet" test network; not in a release; height 0 (off) on mainnet | Coins moved to the new witness-version-2 key-hash type, with SLH-DSA-SHA2-128s | A 7,856-byte signature; single key; test network only |
| Wallet-side tools on Bitcoin: BitGo exposure checker (announced for institutional clients 2026-07-09, public August 2026) with a "Fix Exposed Addresses" workflow for custody clients (BitGo's own checker page for the public tool; dates and the workflow from news coverage of its 2026-07-09 announcement) | None | Public checker live (BitGo's page, read 2026-11-17); the institutional tools as reported | Exposed coins, by moving them to fresh addresses | Hygiene only (hash-safe, not post-quantum); no PQ output exists on Bitcoin yet |
| Exposure classification for existing outputs (duncan0k; Delving Bitcoin topic 2866, 2026-09-03; `duncan0k/pubkey-exposure-classification`; BIPs pull request 2294, "BIP362", opened 2026-09-18) | None | Draft, reference implementation in Python and test vectors; pull request open on 2026-11-17 | Tells an owner which outputs are exposed at rest, exposed on spend, not exposed or undetermined, with a minimum action for each | A classification and advice, not a migration; needs a destination output type to exist |
| Project Eleven yellowpages (2025) | None: an off-chain directory holding a proof that links a Bitcoin address to new post-quantum addresses, with no on-chain transaction | Client live; the proof-service repository is marked archived | Evidence of ownership if old keys fail | The proof is made inside a trusted execution environment (AWS Nitro Enclave) and stored in the company's database, so it rests on that enclave and that service; a proof, not a move |

**How this work sits beside them.** It is not a rival design. Its subject is a post-quantum output type added to
an existing Bitcoin-derived chain's UTXO set and validated in consensus on mainnet. What it contributes is:
(1) measured size and CPU costs of ML-DSA-44 inputs on a legacy-script node; (2) eight weeks of mainnet
operation by one operator, as a load test; (3) thirteen findings (defects, design limits and one report judged not a bug), with fixes and tests where a fix exists; (4) test vectors and an
independent verifier; (5) regtest implementations of the same commitment as a legacy-script soft fork (Dogecoin
Core) and as a witness program (Bitcoin Core, Litecoin Core); (6) a wallet-side migration pattern, the Blazecoin
Quantum Bridge, four of whose five jobs are built and in use on this chain (porting note, section 8).

**What others already have.** Other chains validate post-quantum signatures in consensus: QRL since June 2018,
with XMSS (by the project's own account), Soqucoin since October 2026 (by its README) and KVANTA5 since June 2026 with ML-DSA-87 (by its post on Delving Bitcoin of 2026-07-03, which also gives mainnet stress-test figures), all as new chains with no earlier outputs. An earlier chain did carry an existing UTXO set to post-quantum signatures: Bitcoin
Post-Quantum (BPQ) split from Bitcoin by hard fork at height 555,000 in December 2018, as a separate network
with its own proof of work (Equihash), kept Bitcoin's outputs up to that height and added XMSS signatures to its
script rules. That is from its site and repository, whose checkpoints run to block 600,000 and whose last commit
is dated October 2019, and from its whitepaper: XMSS with the parameters of RFC 8391, signatures of about 2.5 KB,
holders to move their coins to new keys themselves, and elliptic-curve signatures to be disabled about a year after
launch with unmoved coins burned. I did not connect to its network, and its block explorer did not answer on
2026-11-17, so I do not know whether that cut-off was carried out.
It differs from this chain in being a new network that copied another chain's outputs at a snapshot, where this
chain added the type to its own continuing chain, and in its scheme (stateful, hash-based). For the size of the
exposed-key problem on Bitcoin, and for the vocabulary of long-range and short-range attacks, the Chaincode Labs
report (Milton and Shikhelman, May 2025) is the reference: it cites estimates from about 25% to upwards of 50%
of supply, and a more precise 6.26 million BTC (about 30%). The
witness form itself is not new either: Marscoin's branch has had it since April 2026, on regtest and a test
network (table above). A soft fork that verifies native ML-DSA on a legacy-script chain by NOP redefinition and
canonical 520-byte chunks is, to my knowledge, not described elsewhere. The nearest neighbours in what I read:
Dogecoin's Phase 1 carrier uses 520-byte chunks without a consensus check, and Soqucoin's
`OP_CHECKDILITHIUMKEYHASH` (0xb6, formerly `OP_NOP7`) checks an ML-DSA-44 key against a committed 32-byte hash
inside a witness script, not in legacy script.

**Where other designs are better.** The Taproot route and BIP-360's current direction keep script flexibility
that a single-key type does not. The SHRINCS draft's compact path aims at much smaller signatures than
ML-DSA-44's, at the price of signer state (section 7).

What each row of the table rests on: the QSB row is from the paper itself: the construction, the two script
limits, the cost estimate, the non-standard relay status and its own "last-resort" description; the post date,
author and mined transaction are from StarkWare's two posts. The Corallo, Ruffing, Dryja and Wandersleb rows are
from the linked posts. The BitGo row rests on BitGo's checker page for the public tool and on news coverage for
the dates and the institutional workflow; the Block article of 2026-07-09 describes the institutional tools as
due "in the coming weeks". The Project Eleven row rests on the project's own
repositories (its FAQ text and proof-service README, read 2026-11-17).

## Sources

One list. Each entry: author or project. Title. URL. Version or commit. Date of the work. Date read.

Standards and libraries
- NIST. FIPS 204, Module-Lattice-Based Digital Signature Standard. https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.204.pdf. Final. 2024-08-13. Read 2026-11-16 and 2026-11-17.
- NIST. FIPS 205, Stateless Hash-Based Digital Signature Standard. https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.205.pdf. Final. 2024-08-13. Read 2026-11-17 (Table 2: SLH-DSA-SHA2-128s, category 1, public key 32 bytes, signature 7,856 bytes).
- Fouque, Hoffstein, Kirchner, Lyubashevsky, Pornin, Prest, Ricosset, Seiler, Whyte, Zhang. Falcon: Fast-Fourier
  Lattice-based Compact Signatures over NTRU. https://falcon-sign.info/falcon.pdf. Specification v1.2. 2020-10-01. The
  897-byte key and 666-byte padded signature quoted here were confirmed on 2026-11-17 from liboqs 0.15.0
  (`src/sig/falcon/sig_falcon.h`: public key 897, padded signature 666, unpadded maximum 752), not from a fresh reading
  of the specification.
- Open Quantum Safe. liboqs. https://github.com/open-quantum-safe/liboqs/releases/tag/0.15.0. Version 0.15.0. 2025-11-14. Headers read 2026-11-16.
- Todd. BIP-65, OP_CHECKLOCKTIMEVERIFY. https://github.com/bitcoin/bips/blob/master/bip-0065.mediawiki. Deployed. Assigned 2014-10-01. Header read 2026-11-17.
- BtcDrak, Friedenbach, Lombrozo. BIP-112, CHECKSEQUENCEVERIFY. https://github.com/bitcoin/bips/blob/master/bip-0112.mediawiki. Deployed. Assigned 2015-08-10. Header read 2026-11-17.
- Lau, Wuille. BIP-143, Transaction Signature Verification for Version 0 Witness Program. https://github.com/bitcoin/bips/blob/master/bip-0143.mediawiki. Deployed. Assigned 2016-01-03. Header read 2026-11-17.
- Wuille, Todd, Maxwell, Russell. BIP-9, Version bits with timeout and delay. https://github.com/bitcoin/bips/blob/master/bip-0009.mediawiki. Deployed. Assigned 2015-10-04. Header read 2026-11-17.
- Andresen. BIP-16, Pay to Script Hash. https://github.com/bitcoin/bips/blob/master/bip-0016.mediawiki. Deployed. Assigned 2012-01-03. Header read 2026-11-17.
- Wuille. BIP-66, Strict DER signatures. https://github.com/bitcoin/bips/blob/master/bip-0066.mediawiki. Deployed. Assigned 2015-01-10. Header read 2026-11-17.
- Wuille, Nick, Ruffing. BIP-340, Schnorr Signatures for secp256k1. https://github.com/bitcoin/bips/blob/master/bip-0340.mediawiki. Deployed. Assigned 2020-01-19. Header read 2026-11-17. Cited only as one of the BIPs that BIP-360 requires.
- Wuille, Nick, Towns. BIP-341, Taproot: SegWit version 1 spending rules. https://github.com/bitcoin/bips/blob/master/bip-0341.mediawiki. Deployed. Assigned 2020-01-19. Header read 2026-11-17.
- Wuille, Nick, Towns. BIP-342, Validation of Taproot Scripts. https://github.com/bitcoin/bips/blob/master/bip-0342.mediawiki. Deployed. Assigned 2020-01-19. Header read 2026-11-17.

Related work (section 9)
- Levy (StarkWare). Quantum-Safe Bitcoin Transactions Without Softforks. https://github.com/avihu28/Quantum-Safe-Bitcoin-Transactions (the paper is `paper/QSB.pdf` there). Paper dated 2026-04-09. Read 2026-11-16.
- StarkWare. Quantum-safe Bitcoin transactions without softforks (post). https://starkware.co/blog/quantum-safe-bitcoin-transactions-without-softforks/. 2026. Read 2026-11-13.
- StarkWare. The first quantum-safe Bitcoin transaction has been mined (post). https://starkware.co/blog/the-first-quantum-safe-bitcoin-transaction-has-been-mined/. 2026-08-26. Read 2026-11-13.
- Corallo. Trivial QC signatures with clean upgrade path (bitcoin-dev). https://groups.google.com/g/bitcoindev/c/8O857bRSVV8. 2024-12. Re-read 2026-11-16.
- Ruffing. The Post-Quantum Security of Bitcoin's Taproot as a Commitment Scheme. IACR ePrint 2025/1307; announcement thread https://mirror.b10c.me/lists/bitcoindev/bee6b897379b9ae0c3d48f53d40a6d70fe7915f0.camel@real-or-random.org. 2025. Re-read 2026-11-16.
- Dryja. Post-Quantum commit / reveal Fawkescoin variant as a soft fork (bitcoin-dev). https://groups.google.com/g/bitcoindev/c/LpWOcXMcvk8. 2025-05. Re-read 2026-11-16.
- Wandersleb. Pre-emptive variant of commit, delay, reveal (bitcoin-dev post; described, not its title). https://groups.google.com/g/bitcoindev/c/oa4nDmlLzN4. 2025-06. Re-read 2026-11-16.
- Echelon Labs Research. Post-Quantum Witness Version 3 Key-Path Spending (ML-DSA-65). BIP draft, created
  2026-03-31. https://github.com/btcpqresearch/bip-pq-witness-v3, commit `7bbfb29` (2026-04-15); posted to Delving
  Bitcoin 2026-04-16, https://delvingbitcoin.org/t/2422. Draft text and post read 2026-11-17; the patch not read.
- Zaenus. Post-quantum address format draft (ML-DSA-65), version 0.2. https://github.com/Zaenus/btc-safe, commit
  `4e09003` (2026-11-13); posted to Delving Bitcoin 2026-11-13, https://delvingbitcoin.org/t/3067. Read 2026-11-17.
- KVANTA5. Empirical ML-DSA-87 data from a live SHA-256 PoW chain. Delving Bitcoin, 2026-07-03,
  https://delvingbitcoin.org/t/2682; repository https://github.com/Kvanta-Organization/Kvanta5-Core (README). Read
  2026-11-17. Described from the post and the README; the chain and the code were not examined.
- duncan0k. Standardizing an exposure classification for existing outputs. Delving Bitcoin, 2026-09-03,
  https://delvingbitcoin.org/t/2866; https://github.com/duncan0k/pubkey-exposure-classification; BIPs pull request
  2294, "BIP362: Output Public Key Exposure Classification", opened 2026-09-18. Opening post and the reply of
  2026-09-11 read 2026-11-17; the draft text and the code not read.
- Delving Bitcoin. "PQC output type discussion", topic 2749, opened by sipa 2026-07-27, 39 posts to 2026-10-02,
  https://delvingbitcoin.org/t/2749; "Proposing a P2QRH BIP towards a quantum resistant soft fork", topic 956,
  2024-06-08; reply by conduition in topic 2422, 2026-06-01; "BIP 360 (P2MR) implemented in Bitcoin Core on
  regtest", topic 2751, 2026-07-28. Read 2026-11-17 (topic 2749 through a summary of every post with quotations;
  the passages quoted were checked against the forum).
- Marscoin. Marscoin Core. https://github.com/marscoin/marscoin. Branch `feat/pq-witness-v2` at commit `8843ef7` (2026-04-19, merged by PR 46) and branch `feature/quantum-upgrade` at `a0fad48` (2026-10-12): `src/script/interpreter.cpp`, `src/consensus/params.h`, `src/kernel/chainparams.cpp`, `doc/quantum-p2wpqh-sighash-v1.md`, `doc/quantum-signatures-sphincs-v1.md`, `doc/quantum-work-orders.md`. Read 2026-11-16.
- BitGo. BTC quantum resistance score (the public checker). https://www.bitgo.com/btc-quantum-resistance-score/. Undated page. Read 2026-11-17.
- Bitcoin Magazine. News article on BitGo's quantum risk controls (names the "Fix Exposed Addresses Workflow"; headline not recorded here). https://bitcoinmagazine.com/news/bitgo-adds-quantum-risk-controls-bitcoin. 2026-07-09. Read 2026-11-17.
- The Paypers. BitGo launches public Bitcoin quantum risk checker (news). https://thepaypers.com/crypto-web3-and-cbdc/news/bitgo-launches-public-bitcoin-quantum-risk-checker. 2026-08-14. Read 2026-11-13 and 2026-11-17.
- The Block. BitGo introduces quantum protection for institutional Bitcoin wallets (news). https://www.theblock.co/post/407661/bitgo-quantum-protection-institutional-bitcoin-wallets. 2026-07-09. Read 2026-11-13 and 2026-11-17.
- Project Eleven. yellowpages. First-party sources read 2026-11-17: the client repository
  https://github.com/p-11/yellowpages-client (commit `4b6cef3e`, 2026-03-19; its FAQ page `src/app/faqs/page.tsx`) and
  the proof service https://github.com/p-11/yellowpages-proof-service (commit `0485a71f`, 2026-03-19; README, marked
  archived). The announcement posts https://www.projecteleven.com/blog/hello-yellowpages and
  https://www.projecteleven.com/blog/the-trust-model-of-yellowpages-v1 were read on 2026-11-13 and refuse automated
  fetches.
- Anhao, N. Bitcoin Post-Quantum (whitepaper). https://bitcoinpq.org/download/bitcoinpq-whitepaper-english.pdf. Undated (2018).
  Project site https://bitcoinpq.org/ ; node https://github.com/bitcoinpostquantum/bitcoinpq, last commit `28a1f3c`
  (2019-10-23): `src/chainparams.cpp` (`BPQHeight = 555000`, checkpoints at 555,100 and 600,000),
  `src/script/interpreter.cpp`. Read 2026-11-17.
- Milton, Shikhelman (Chaincode Labs). Bitcoin and Quantum Computing: Current Status and Future Directions. https://chaincode.com/bitcoin-post-quantum.pdf. 2025-05. Read 2026-11-17.
- QRL. Project site and anniversary post. https://www.theqrl.org/ , https://www.theqrl.org/blog/celebrating-8-years/. Mainnet 2018-06. Read 2026-11-17.

Proposals and chains (sections 1 to 7)
- Beast, Heilman, Duke. BIP-360, Pay-to-Merkle-Root (P2MR). https://github.com/bitcoin/bips/blob/master/bip-0360.mediawiki. Version 0.12.1 (2026-07-24), status Draft, file commit `e7263a4`. 2026-08-03. Read 2026-11-11, 2026-11-16 and 2026-11-17.
- Lopp, Papathanasiou, Smith, Ross, Vaile, Dallaire-Demers. BIP-361, Post Quantum Migration and Legacy Signature Sunset. https://github.com/bitcoin/bips/blob/master/bip-0361.mediawiki. Assigned 2026-02-11, status Draft, file commit `da7cc67`. 2026-04-17. Read 2026-11-11, 2026-11-16 and 2026-11-17.
- conduition, Heilman, Kudinov, Kurbatov, Nick, remix7531. SHRINCS: A Compact Hash-Based Signature Scheme (draft, no BIP number). https://github.com/SHRINCS/shrincs-bip/blob/main/SHRINCS.md. File commit `990cd1f`. 2026-11-09. Read 2026-11-11, 2026-11-16 and 2026-11-17.
- Tubbs (libdogecoin). Post-Quantum Signature Commitments (draft). https://github.com/dogecoinfoundation/libdogecoin/blob/0.1.5-dev/doc/spec/bip-post-quantum-signature-commitments.mediawiki. Branch `0.1.5-dev`, file commit `b416f55`, merged by pull requests 288 (2026-04-07) and 294 (2026-05-21); also `src/pqc_dilithium.c` and `depends/packages/liboqs.mk` on the same branch, read for 4.6. Created 2026-02-18. Read 2026-11-11, 2026-11-16 and 2026-11-17.
- Bitcoin Core. https://github.com/bitcoin/bitcoin. Master at `a527a00`. 2026-11-13. The base of the witness build in `bitcoin/`.
- Dogecoin. Dogecoin Core. https://github.com/dogecoin/dogecoin. Version 1.14.99, master at `b38c83f`: `src/miner.cpp`, `src/chainparams.cpp`, `src/primitives/pureheader.h`. 2026-11-09 UTC (2026-11-08 in American time zones). Read 2026-11-13 and 2026-11-17.
- Litecoin. Litecoin Core. https://github.com/litecoin-project/litecoin. Release v0.21.5.8, tag commit `ec1b6489`: `src/script/script.h` (MWEB witness versions 8 and 9), `src/chainparams.cpp`. Released 2026-09-12. Read 2026-11-16 and 2026-11-17.
- This chain. `PQ_SIGNATURES.md` in the node repository; REPORT.md and DEFECTS.md in this repository.
- Soqucoin (self-described). Soqucoin Core. https://github.com/soqucoin/soqucoin (README, `doc/ECDSA_ELIMINATION.md`, `src/script/interpreter.cpp`, `src/script/script.h`). Branch `main`. Mainnet 2026-10-13 by its README. Read 2026-11-12, 2026-11-16 and 2026-11-17.
- Halborn. Soqucoin Blockchain Node (audit report). https://www.halborn.com/audits/soqucoin/soqucoin-blockchain-node-a4f1f7. Engagement 2026-02-17 to 2026-03-24. Read 2026-11-16 and 2026-11-17.

Notes on what was read. ML-DSA-44 sizes are from liboqs 0.15.0 headers and from the FIPS 204 text itself (Table 2: private key 2,560, public key 1,312, signature 2,420 bytes; ML-DSA-65 signature 3,309). Also from FIPS 204: section 3.4, "By default, this standard specifies the signing algorithm to use both types of randomness. This is referred to as the 'hedged' variant", and that the deterministic variant "should not be used on platforms where side-channel attacks are a concern and where they cannot be otherwise mitigated"; the context string "has a maximum length of 255 bytes. By default, the context is the empty string".

Left out: the publication date and Liquid testing of SHRINCS, which appear only in news coverage and not in the
draft itself. No Litecoin proposal was found; that is an absence of search results, not proof of absence.
