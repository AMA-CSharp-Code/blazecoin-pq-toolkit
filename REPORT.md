# ML-DSA-44 as a native output type on a legacy-script Bitcoin Core fork: a field report

hyperminer (bitcointalk), admin@blazecoin.co.uk. Version 1.0.1, 17 November 2026.

## 1. Summary

Since 16 September 2026 a small proof-of-work chain has enforced ML-DSA-44 (FIPS 204) signatures in consensus,
through a new output type added to a fork of Bitcoin Core 28 that has no SegWit and no Taproot. From activation
at block 4,250,000 to block 4,417,513 on 11 November 2026, the period this report calls "eight weeks" throughout,
about 158,000 post-quantum inputs were verified by every node. All but 37 of them were spent by wallets I operate.

The open proposals for Bitcoin-family chains have not yet fixed both an output type and a signature scheme,
because each needs agreement among independent parties that this chain did not need. BIP-360 specifies an output
type and leaves the signature scheme for later. SHRINCS specifies a signature scheme and leaves the output type
for later. Dogecoin's draft publishes post-quantum signatures as commitments today and lists native script
validation as a second phase still to be specified. This chain has built one version of that second phase on a
legacy-script codebase and run it. Having had no such constraint, I can report what one set of choices cost and
what broke.

What this report is not:

- **Not a proposal for any other chain.** The activation was a hard fork on a network where, at the time, I ran
  the public nodes and nearly all the hash rate (my own pool's share; not measured here). That does not transfer to anyone.
- **Not evidence of adoption.** 99.98% of the post-quantum spends (158,404 of 158,441) came from wallets I
  operate, and 95% of all spends from one wallet, my pool's reward wallet, merging its own coinbase outputs. It
  is a sustained load test of the code path by one operator.
- **Not a claim about the scheme.** I chose a lattice signature for size and library support. The case for
  hash-based signatures on conservative assumptions is a fair one and I do not argue against it here.

What it contributes: (1) measured size and CPU costs of ML-DSA-44 inputs on a legacy-script node; (2) eight weeks of mainnet operation by one operator, as a load test; (3) thirteen findings (defects, design limits and one report judged not a bug), with fixes and tests where a fix exists; (4) test vectors and an independent verifier; (5) regtest implementations of the same commitment as a legacy-script soft fork (Dogecoin Core) and as a witness program (Bitcoin Core, Litecoin Core); (6) a wallet-side migration pattern, the Blazecoin Quantum Bridge, four of whose five jobs are built and in use on this chain (section 10.3; porting note, section 8).

Where to find them: the measurements are in section 5, the mainnet record in section 6, the defects in
section 7, the vectors with the verifier of about 150 lines in section 11, and a point-by-point answer to the Phase 2
questions in Dogecoin's draft, with the soft-fork variant, in section 4.

The limits of method are stated where the numbers are used and again in section 12. In short: one operator, one
build of the node on every node I know of, an untuned benchmark on one machine, and address ownership that is my
own attribution and cannot be checked from outside.

The wallet side of the migration has a name of its own, the Blazecoin Quantum Bridge: sorting an owner's coins
into exposed, hash-safe and post-quantum, and moving them across. Four of its five jobs are built and have been
used on this chain's mainnet, mostly with my own funds; receive-only custody is a proposal; none of it has been
measured for its effect on other users. Section 10.3 introduces it; the companion porting note, section 8, gives
the definition and the status of each part.

## 2. The chain and its constraints

Blazecoin is a scrypt proof-of-work chain launched in 2014, with 30-second blocks and a 1 MB block limit (the chain
parameters are in the node repository, `src/kernel/chainparams.cpp`). Its
node was rebuilt on Bitcoin Core 28 in June 2026. The constraints that shaped the design:

- **SegWit and Taproot are present in the code and never active.** There is no witness to put a signature in and
  no tapscript to host a new opcode. BIP-360 requires both and cannot be ported.
- **The 520-byte script element limit is consensus.** An ML-DSA-44 signature is 2,420 bytes and a public key is
  1,312. Neither fits in a single legacy push.
- **No witness discount.** Every byte of a signature counts in full against the block limit.
- **One operator.** A flag-height hard fork was practical here and would not be elsewhere.

A soft fork would probably also have worked here: the variant in section 4, built two months later on Dogecoin Core for regtest, uses only legacy-script mechanisms that this chain also has. The hard fork gave a two-push spend and a single rule, and it was available because one operator could activate it; it was not forced by legacy script.

### 2.1 Security assumptions and what is protected

**Attacker.** One who can recover a secp256k1 private key from its public key (Shor's algorithm), who gets at
most a quadratic speed-up on hash preimages (Grover's algorithm), and who sees the chain and the mempool. Both
algorithms are assumed known and are not cited.

**Assumed to hold.** ML-DSA-44 at NIST category 2. SHA-256 preimage and second-preimage resistance for the
32-byte key hash of the new type. The 160-bit hash of a classic pay-to-public-key-hash output, at about 2^80
quantum work, for coins whose key has never been revealed.

**Protected.** A coin in a post-quantum output, at rest (only a hash is public) and at spend time (the key the
spend reveals is an ML-DSA key).

**Protected at rest only.** A classic coin whose key has never been revealed. Its spend puts the key in the
mempool, and it stays at risk until the spend is buried deep enough not to be reorganised out.

**Not protected.**

- Any classic coin whose key is already on the chain. The type is voluntary and has no sunset (section 9).
- Proof of work and the ordering of the chain, which this change does not touch.
- Signers against fault or side-channel attack: wallets here sign deterministically, which FIPS 204 advises
  against where such attacks apply (section 9, point 8).
- Anything at all if ML-DSA-44 fails: there is no hybrid with a classic key.

**Key derivation.** Post-quantum keys come from hashing alone. The light wallet takes the first 32 bytes of HMAC-SHA512 of the BIP-39 seed under a fixed key, the node wallet a tagged SHA-256 of the wallet's master private key, and each ML-DSA
key seed is a tagged hash of that 32-byte master seed and an index. Neither input appears on the chain, and no
public key, classic or post-quantum, gives another key's seed (node: `src/wallet/walletutil.cpp`; light wallet:
`PqKeyDerivation.cs` in the wallet repository). Someone who obtained a wallet's seed or master
private key by other means would hold its post-quantum keys as well.

## 3. What was built

**Output (34 bytes):** `0x20 <32-byte key hash> OP_CHECKPQSIG`

**Spend (scriptSig):** exactly two pushes, `<signature: 2,420 bytes> <key blob: 1,313 bytes>`.

The output type is called P2PQH, pay to post-quantum key hash, in the code and the toolkit.

- The key blob is one algorithm byte followed by the public key. The output commits to
  `TaggedHash("Blazecoin/PQKH/v1", key blob)`, so the algorithm is inside the commitment. A later scheme gets a
  new algorithm byte and needs no new address format. One algorithm is active; others are reserved.
- Until it is spent, the output reveals only a hash, the same long-exposure protection BIP-360 is built around.
- `OP_CHECKPQSIG` is one opcode byte that is valid only when the output being spent matches the template above.
  It is not a redefined NOP and cannot be reached from an ordinary script.
- The element limit is raised to 5,000 bytes for inputs spending this template, and nowhere else.
- The signed message is a tagged hash of a BIP-143-shaped preimage: it commits to the amount and the script, and
  the three shared hashes are computed once per transaction. There is no sighash-type byte; the signature length
  is exact and SIGHASH_ALL is the only mode.
- Signing uses the FIPS 204 context string `blazecoin-tx-v1`, and a different one for message signing, so a
  transaction signature can never be replayed as a signed message.
- Wallets sign deterministically (FIPS 204 with rnd = 0). That is a wallet choice, not a consensus rule: a
  verifier cannot tell a hedged signature from a deterministic one, and consensus accepts any valid FIPS 204
  signature. The node vendors the pq-crystals reference C code with the random-number path removed, so no RNG (random number generator) is
  linked into consensus-adjacent code. FIPS 204 makes hedged signing the default; section 9, point 8, lists the
  deterministic choice as a weakness.
- Before the activation height the output type cannot be spent and is non-standard to create.
- Addresses are Base58Check with a two-byte prefix, 52 characters.
- The light wallet derives post-quantum keys from the seed phrase its user already backs up, and a node wallet (which is what the desktop wallet runs) created on node 2.1.0 or later derives them from its master key, so those wallets need no new backup. A node
  wallet created earlier gets no post-quantum keys in place (DEFECTS.md, A4). Its owner makes a new wallet or, as
  I did for my two pool wallets, imports a post-quantum descriptor with a fresh random seed; either way there is
  a new backup to make.

It is deliberately the smallest thing that works: single key only. There is no post-quantum multisig and no
script composition.

## 4. Dogecoin's Phase 2 questions, and what this chain did

Dogecoin's draft ("Post-Quantum Signature Commitments", libdogecoin) says its Phase 2 document must define four
things. Both chains use the same primitive: the draft's Dilithium2 path selects ML-DSA-44 in liboqs. These are my
answers as one worked example, not as advice.

| Phase 2 question | What this chain did | What it cost or showed |
|---|---|---|
| Opcode assignment | One opcode, valid only for one output template | No interaction with existing scripts. Old nodes reject the spend, so it is a hard fork |
| Script format for the verification data | Two fixed pushes; algorithm byte inside the hashed key blob | Input size is exactly 3,782 bytes, which made fee and policy rules simple |
| Evaluation and failure semantics | Fail closed before activation; a fixed order of checks, each with its own error | 11 must-fail vectors pin every error except the element-size one. No defect found in this path so far; section 7, point 1, says how little that shows |
| Activation | Flag height, hard fork | Built, announced and active within three days. See section 8 for why this does not transfer |

Four further points from running it:

- **The push limit.** The draft's Phase 1 carrier splits the key and signature into 520-byte pieces across
  several inputs, three for ML-DSA-44. A native type has to either keep chunking or raise the limit for its own
  inputs. I raised it, and that is one of the two reasons my version is a hard fork (the other is the new opcode).
- **The signed message.** The draft signs the legacy sighash. I chose a BIP-143-shaped digest instead, for two
  reasons: it commits to the amount being spent, and its shared hashes are computed once per transaction, where
  the legacy sighash re-serialises the transaction for every input. In my measurements the classic path slows
  from 57 to 64 microseconds per input at 26 inputs, while the BIP-143-shaped digest stays flat. The large
  signatures do not make the legacy cost worse: the legacy sighash blanks every scriptSig before hashing, so a
  26-input transaction would hash about 1.2 KB per input, about 30 KB in all, whether its inputs are classic or
  post-quantum (computed from the serialisation; `SerializeInput` in the node's `src/script/interpreter.cpp`).
  The saving is a few microseconds per input here and grows only with the input count; a new output type is the
  cheapest moment to leave the quadratic form behind.
- **A note on the draft's wording.** It suggests a soft fork based on OP_SUCCESSx. OP_SUCCESS exists only
  inside tapscript, and the same draft notes Dogecoin has no SegWit relay. In legacy script the soft-fork
  tools are NOP redefinition or a template deployed the way P2SH (pay to script hash) was.
- **A soft-fork variant, built.** I have since built one, on a branch of Dogecoin Core 1.14.99 for
  regtest: `OP_NOP10` redefined, the signature and key in canonical 520-byte chunks so the element limit
  stays, the redeem script behind P2SH so any wallet can pay to it, activation by height. It works for
  signatures this large: a spend is 3,792 bytes of scriptSig against this chain's 3,739, 53 bytes more per
  input (the extra chunk pushes and the P2SH redeem script), and the functional
  test shows a bad-signature block accepted before the height and rejected after it. One finding on the way:
  as Dogecoin Core stands today, a version-bits deployment cannot activate, because the miner pins the base
  version and the AuxPoW (auxiliary proof of work, that is, merged mining) header uses those bits for the chain id, so the activation has to be a height, which is how Dogecoin's consensus parameters record BIP-65 and BIP-66 today (they first activated by block-version supermajority and are now fixed heights). Marscoin's code already records the same constraint for its own AuxPoW chain
  (`src/consensus/params.h` in its repository; comparison document, section 6). The patches and their README are in the toolkit (`dogecoin/`); the design is in the comparison
  document, section 6. Not a proposal, not scheduled anywhere, not reviewed by anyone from Dogecoin.

The draft's Phase 1 also did something I skipped: it gathered mainnet measurements and built tooling with no
consensus risk before fixing a design. That is the more careful order.

## 5. What it costs

**Method.** Node benchmark, run on 11 November 2026 with Bitcoin Core's own bench harness:
`bench_blazecoin.exe -filter="MLDSA44.*|PQSigHashDigest|VerifyScriptP2P.*|VerifyTxP2P.*" -min-time=3000`. The
bench source is `src/bench/pq_verify.cpp` at node commit `93fcbc3f6f`. Build: MSVC Release x64 (Visual Studio
18). Machine: one core of an AMD EPYC 9654, with three nodes running on it at the time. No signature cache. The
harness reported an error of 0.1 to 0.6 percent on each figure. Both sides are untuned: the ML-DSA code is the
pq-crystals reference C without AVX2, and libsecp256k1 is as MSVC builds it, without its x86-64 assembly. The
ratio on a tuned build has to be measured, not assumed from these. It is one run on one machine.

The first three rows are measured. The last two are computed from them.

| | Classic P2PKH | Post-quantum input | Ratio |
|---|---|---|---|
| Input size | 148 bytes | 3,782 bytes | 25.6x |
| Verify one input (script, digest, signature) | 57.4 µs | 102.9 µs | 1.8x |
| Verify per input in a 26-input transaction | 64.3 µs | 100.9 µs | 1.6x |
| Inputs in a full 1 MB block (computed: block size over input size) | about 6,750 | 264 | |
| Signature checking for a full block of them (computed: that count times the one-input cost; not a measured block validation) | about 388 ms | about 27 ms | |

Primitives alone: key generation 81.8 µs, signing 356 µs, verification 90.1 µs, the transaction digest 4.1 µs.

What I take from it:

1. **Bytes bind long before CPU.** Per byte, ML-DSA verification is about 14 times cheaper than ECDSA on this
   build. A block full of post-quantum inputs verifies faster than a block full of classic ones because it holds
   so few. The SHRINCS draft (as of 9 November 2026) makes the same kind of claim for a hash-based scheme against Schnorr. Limits on
   validation cost for large-signature schemes are better expressed in bytes.
2. **26 inputs is the practical ceiling.** That is what fits in a standard 100 KB transaction. Consolidating
   small outputs takes many near-maximum-size transactions, in rounds (see "A consolidation run" below).
3. **I set the sigop count badly.** One post-quantum check counts as 50 legacy sigops. The measured cost is
   about 1.8 classic checks, so the count overstates it roughly 28 times (50 / 1.8). It was chosen from a
   benchmark of a different implementation and never re-measured on the node, and it is now a consensus
   constant. For spending it does no harm, because the byte limit binds first. For creating outputs it does. The
   charge is counted on the scriptPubKey of each post-quantum output a transaction creates and is multiplied by
   4, as every legacy sigop is, so each new output costs 200 against a block limit of 80,000 and a
   standard-transaction limit of 16,000. A block can therefore create at most 400 post-quantum outputs
   (80,000 / 200) and a standard transaction at most 80 (16,000 / 200), far below what the byte limits allow.

### A consolidation run

On 12 November I merged one wallet's post-quantum outputs with a wallet feature built that day. It is my own
traffic and falls after the block range counted in section 6. I include it because it is the cleanest
measurement I have of what the 26-input ceiling means in practice. The outputs merged were already
post-quantum, so the run measures what a sweep costs in transactions and block space; it is not a migration of
classic coins. The figures were read from the wallet that made the run with `toolkit/consolidation_run.py`, and they agree with
the chain: the 241 transactions are in blocks 4,420,140 to 4,420,164 (12 November 2026, 15:54 to 15:58 UTC), where
anyone with a node can count them (the same blocks also hold the 7 transactions of the early second round, 171
inputs, paying a different address).

| | |
|---|---|
| Outputs before | 6,243, all post-quantum, the largest about 2,900 coins, 1.75 million coins in all |
| Transactions in the first round | 241: 240 with 26 inputs (98,385 bytes each) and one with 3 |
| Bytes | 23,623,799 |
| Blocks | 24 consecutive blocks filled to the 1 MB limit (10 such transactions fit in a block), and part of a 25th |
| Outputs after the first round | 241 |
| Signature verification for the whole round, from the benchmark above | about 0.63 seconds on one core |

Three things follow.

1. **Consolidation is a tree with a fan-in of 26.** 6,243 outputs become 241, then 10, then 1: three rounds,
   and each round has to confirm before the next can spend its outputs. A classic wallet on this chain can merge
   about 675 inputs in one standard transaction (computed: 100,000 bytes at 148 bytes an input), so the same job is 11 transactions in two rounds.
2. **It is all bytes.** The round took 24 full blocks of space and well under a second of signature checking.
   On a chain with a fee market the cost of this would be 23.6 MB of block space; here it was nearly free,
   which is the limit stated in section 9, point 5.
3. **A wallet full of small outputs cannot make a large payment.** One transaction can spend at most the 26
   largest outputs. Earlier the same day this wallet held
   about 2.1 million coins in 6,511 outputs (the wallet's own count), the largest about 3,200 coins, and its 26 largest came to about
   49,000. A payment of 350,000 from it was refused by the wallet as too large and had to be built by hand as 12
   transactions with 293 inputs (blocks 4,418,126 to 4,418,130, 09:36 to 09:39 UTC). The amounts and counts are
   on the chain; that the wallet refused the single payment is my own record. A chain
   that adopts kilobyte signatures without a witness discount, and with a standard transaction size like this
   one's, gives every mining-payout wallet this problem, and wallets need a consolidation tool on day one.

A smaller lesson from the same day: I ran the second round before all of the first had confirmed, and it merged
only the 171 outputs that had. The tool now shows the outputs still confirming and says to wait.

## 6. What ran on mainnet

Block 4,250,000 to block 4,417,513 (16:20 UTC on 11 November 2026), counted that day from a full index of the chain (the project's
block indexer, a SQL database; the queries are in `toolkit/queries/`). The published queries carry the same
range (`Height BETWEEN 4250000 AND 4417513`), for
the outputs and for the transactions that spend them, so they reproduce these figures on any full index whenever
they are run (re-run on the production index on 17 November 2026: identical); remove the bound to count to the tip. On 17 November 2026 I re-derived the counts a second way, without the index, by reading
every block of the range from a full node over RPC (`toolkit/recount_from_node.py`). Outputs created, inputs
spent, addresses, spending transactions and their bytes, the consolidation-shape counts and the outputs funded
from classic inputs all came out the same.

| | |
|---|---|
| Post-quantum outputs created | 173,898 |
| Of which spent, each one verified by every node | 158,441 |
| Distinct post-quantum addresses | 10,946 |
| Transactions spending post-quantum inputs | 11,723, 600 MB in total |
| Share in transactions of 10 or more inputs and at most 2 outputs (a count by shape; ownership is in the next table) | 95% of spent inputs, averaging 98 KB per transaction |

Who it was. This is my own attribution, made by checking every address against every wallet I operate; nobody
outside can repeat that check from the published data.

| Owner | Addresses | Outputs | Spent |
|---|---|---|---|
| My pool's reward wallet | 64 | 155,345 | 150,452 |
| My pool's payout wallet (a new change address per payout) | 10,802 | 10,804 | 7,718 |
| My other wallets | 57 | 6,725 | 234 |
| **Not mine** | **23** | **1,063** | **37** |

The ownership check ran later the same evening than the totals above, and the chain had moved on, so its
outputs column sums to 39 more (173,937).

So wallets I operate made 158,404 of the 158,441 spends, 99.98%, and one of them, the pool's reward wallet
merging its own coinbase outputs, made 95% of all spends. Outside parties account for 0.6% of post-quantum
outputs and 0.02% of spends. Three outside miners (matched by my pool's payout records) chose to be paid to post-quantum addresses, which shows the
receive path works for someone else, and 37 outside spends are the only third-party use of the signing path.

**Migration, as distinct from mining straight to the new type.** 3,078 post-quantum outputs at 65 addresses were
funded by transactions with classic inputs only: coins moving from classic keys into post-quantum outputs (the
count of 11 November). That figure was not split by owner. Nor did I count outside classic activity in the same
blocks, so there is no denominator for outside use.

**What users were offered.** Post-quantum addresses became the default for receiving, change and sweeps in the
desktop wallet (2.0.9) and the light wallet (1.3.0) on 28 September 2026, twelve days after activation. The
node's own wallet still defaults to classic addresses, and a node wallet created before node 2.1.0 cannot add
post-quantum keys in place (DEFECTS.md, A4), so for those holders the default changed nothing.

I read two things from this. As a test of the code it is a real one, within limits: about 2,800 verifications a
day for eight weeks in near-maximum-size transactions, with no validation failure, and the 27 mainnet inputs
checked by the independent Python verifier agree with the node. Every node I know of ran my build, so this is
not a test of agreement between implementations, and the traffic was honest and almost all mine. As evidence
about voluntary migration it is weak in both directions. Outside parties made 37 post-quantum spends and
received 1,063 post-quantum outputs at 23 addresses; I have no count of what else they did on the chain in those
weeks, and this chain has few active outside users of any kind (my observation; I did not count them). The figures do not contradict BIP-361's premise
that voluntary migration is slow; they are too small to support it.

## 7. What broke

Thirteen findings to 12 November 2026: seven from outside reporters through a bug bounty, six my own. The full list
with commits and tests is in the toolkit. My thanks to the bug-bounty reporters; they are not named here.

| Finding | Where | Severity |
|---|---|---|
| Dust threshold priced a post-quantum output as if its input were 148 bytes | Relay policy, copied in every wallet | Low |
| Derived public keys read from the wallet file were not length-checked | Node wallet | Low |
| Change from a post-quantum spend went to a classic address, in three separate code paths | Desktop wallet | Medium |
| Wallets created before the fork cannot add post-quantum keys in place | Node wallet | Design limit |
| Sigop count of 50 overstates cost about 28 times, and caps output creation at 400 per block and 80 per standard transaction | Consensus constant | Low: no effect on spending; limits output creation |
| The light wallet's "stop sending after the fork" state trusted an unsigned server message | Light wallet | Medium |
| The announced fork time was 15 hours early | Operations | None |
| **A single SegWit transaction could stop all block production** (not observed on mainnet) | Unmodified base code | **High** |
| The wallet would issue and pay SegWit addresses nobody can spend | Unmodified base code | Low to Medium |
| Timelocks are enforced by the mempool but not by blocks | By design, documented | Low, by design |
| Wallet history tools stalled on wallets full of large consolidations | Desktop wallet | Low |
| A wallet holding thousands of small post-quantum outputs could not make a large payment | Desktop wallet | Design limit |
| A report that the input weight was "4x too high" | Node wallet | Not a bug |

What I would tell someone starting the same work:

1. **No defect has been found in the cryptographic path**: the ML-DSA code, the digest or the script path. That
   is weak evidence. The traffic was honest and almost all mine, every node I know of ran my build, outside
   review began five and a half weeks in, and the NIST known-answer vectors and the fuzz targets were added only
   on 13 November. Vendoring the reference implementation, deterministic signing and pinning three codebases to
   one set of vectors are the practices I would repeat; I cannot show they are why nothing was found.
2. **The defects were at the edges.** A size assumption in policy, an unchecked length where keys are stored, a
   wallet default, and a notice channel nobody had thought of as an attack surface.
3. **Search for the number 148.** Every place that assumes an input size is wrong for a 3,782-byte input. The
   dust rule was in the node and in three other programs (two wallets and a faucet), and the fix had to ship to wallets before nodes.
4. **Decide once where change goes.** A wallet that spends post-quantum coins and returns change to a classic key has silently undone the user's migration. I fixed it on one page and it was still in two other paths five
   weeks later. The Bitcoin analogue would be a P2MR (pay to Merkle root) wallet sending change to a key-path Taproot output.
5. **The worst bug was not in my code.** This chain, forked from a recent Bitcoin Core with SegWit never active,
   accepted SegWit transactions into its mempool. Upstream removed the pre-activation mempool check
   (`no-witness-yet`) in Bitcoin Core 0.17, when the witness script flags began to be enforced from genesis; the
   deployment was buried to a height later, in 0.19 (pull request 16060). The miner then builds invalid blocks for ever. One cheap
   transaction would have halted the chain. It was never used against the chain: block production never halted for this reason. Another fork of 0.17 or later
   that never activated SegWit may accept such transactions too, depending on how it left SegWit inactive. A
   codebase older than 0.17 (Dogecoin Core 1.14, for one, checked at `b38c83f`) still has the check, but it deserves a regtest test on
   any chain without SegWit.
6. **Fixes by enumeration fail.** My first fix for SegWit addresses listed the types by hand and missed one. It
   took two more reports to replace the lists with a single rule.
7. **The update channel is part of the fork.** Light wallets were told about the fork height by their server.
   That message is now required to be signed by a pinned key before it can stop a wallet from sending.
   Two keys are pinned, a primary and a spare held apart from it, so that losing one key does not leave
   installed wallets impossible to stop. The lesson is in the order: the fork activated on 16 September 2026 and the
   keys were pinned and released on 12 November 2026. The signing key belongs in the release before the fork, not
   eight weeks after.
8. **Outside review found what I had not**, including the worst one. It began about five and a half weeks after
   activation, with a first bounty report on 25 October 2026 (fixed in light wallet 1.3.1); the reports on this
   list date from 6 November 2026, seven weeks after activation. I would open the bounty before the fork next time.

## 8. Activation, and why it does not transfer

The fork was built on 14 and 15 September, the height was set on the 15th, and block 4,250,000 arrived on the
16th. Every node, both public relays, the pool, the explorer, three wallet platforms and the light-wallet
gateways were updated by one person in a day, because one person runs them.

Two things are worth passing on despite that. Activation by height meant a 15-hour error in the predicted clock
time did no harm. And the consensus change was the smaller half of the work: the same rules had to exist in the
C# light wallet, the explorer, the pool's payout system and the address-verification flow, all before the height.

Nothing about the speed carries over to a network with independent miners, exchanges and custodians, and a soft
fork is the right goal for one.

## 9. Where this design is weaker

1. It is a hard fork.
2. It depends on one lattice scheme with no hybrid. If ML-DSA-44 fails, the algorithm byte allows a replacement,
   but coins on the old algorithm would have to move again.
3. It is NIST category 2 on newer assumptions, where SHRINCS aims at category 1 on SHA-256 alone. A Bitcoin draft that chooses ML-DSA-65 sets ML-DSA-44 aside as having "a thinner security margin than is prudent for coins with decades-long lifetimes" (porting note, section 6).
4. Single key only. Nothing here helps with multisig, which custodians and exchanges need.
5. No witness discount and no fee floor on this chain, so the size cost is hidden in a way it would not be on a
   chain with fee pressure.
6. No sunset. Coins on exposed classic keys stay exposed until their owners move them, and the largest exposed
   balances here have been dormant for years (checked on 14 September 2026 and recorded in the node repository's
   `PQ_SIGNATURES.md`).
7. No independent audit. The NIST FIPS 204 known-answer vectors for ML-DSA-44 (from NIST's Automated Cryptographic Validation Protocol, ACVP; 79 cases: key generation,
   deterministic and hedged signing, and verification including NIST's modified-signature cases) are pinned in the
   unit suite, and the script path has three fuzz targets (the primitive, the digest and templates, and a whole
   signed spend with scripted mutations). Both date from 13 November 2026: for its first eight weeks the
   consensus code ran on mainnet without them. The first libFuzzer campaign (clang 17, AddressSanitizer and
   UndefinedBehaviorSanitizer, 13 November 2026) ran the primitive for 10 minutes (570,152 executions), the digest for
   10 minutes (2,714,962) and the whole spend for 15 minutes (808,500) with no finding in the node; it did find
   two defects in the harness itself (section 11). That is about 35 minutes of fuzzing and 4.09 million
   executions, not the weeks a consensus change deserves.
8. Wallets sign deterministically. FIPS 204 (section 3.4) makes hedged signing the default and says the
   deterministic variant should not be used on platforms where side-channel attacks are a concern and cannot
   otherwise be mitigated. Consensus requires neither variant, so a wallet could change this without a fork;
   none has.
9. The sigop count of 50 is a consensus constant chosen from a benchmark of a different implementation and never
   re-measured on the node. It overstates the cost about 28 times, and because it is charged on created outputs
   it caps a block at 400 new post-quantum outputs and a standard transaction at 80 (section 5, point 3).
   Changing it is another fork.
10. The consensus change was built in two days and activated on the third, with no outside review before
    activation. Section 8 reports that as a fact of the activation; it is also a weakness of the process.

## 10. For Bitcoin researchers

### 10.1 One data point, and what does not carry

The deployed form does not port to Bitcoin: different output model, different scheme family, no witness, no fee
market, no comparable activation. The commitment itself can be carried as a witness program, and the companion
porting note builds that on regtest (its section 4). Treat the deployed chain as one measured data point on four
questions that come up in the BIP-360, SHRINCS and BIP-361 discussions:

- what happens to validation cost when signatures are kilobytes (section 5: on this build bytes bind, not CPU);
- what happens to consolidation (section 5: the same merge takes 252 transactions in three rounds (241, 10, 1; I
  ran the first), nearly all at maximum size, where classic inputs take 11 in two; the transaction mix on this chain is one pool wallet's and says
  nothing about other chains' mixes);
- where the implementation defects appeared (section 7: edges and defaults; the cryptographic path has had
  little outside scrutiny);
- how fast users move when migration is voluntary (section 6: too few outside users here to say; the figures do
  not contradict the premise that it is slow).

### 10.2 Related work

The comparison document sets the proposals (BIP-360, BIP-361, SHRINCS, Dogecoin's draft) and other routes side
by side, with sources and read dates. Four systems that are deployed or built are closest to this one: an earlier split network, two new chains and a test-network witness type. I have not
made a systematic search for earlier chains that added post-quantum signatures to an existing UTXO (unspent transaction output) set; the
comparison document lists what I read.

The first, and the earliest, did part of this in a different form. Bitcoin Post-Quantum (BPQ) split from Bitcoin at height
555,000 in December 2018 as a separate network, with a copy of Bitcoin's outputs, its own proof of work and XMSS
signatures checked in consensus (about 2.5 KB each, by its whitepaper). Holders were to move their coins to new keys
themselves, and the whitepaper says elliptic-curve signatures would be disabled about a year after launch, with
unmoved coins burned. Its repository carries a checkpoint at block 600,000, and development stopped in 2019 (by its
site, whitepaper and repository; I did not connect to its network and do not know whether the cut-off happened). It is an earlier case, the only one I found, of post-quantum signatures validated on a mainnet over outputs inherited from a Bitcoin-derived chain. The difference
is that BPQ was a new network split from another chain's history, while this chain added the type to its own
continuing chain, beside its existing rules, wallets and users.

The second is a new chain. By its own README, Soqucoin started its mainnet on 13 October
2026 as a new scrypt proof-of-work chain with ML-DSA-44 signatures from its first block, merge-mined; an outside
security audit before launch is published by the auditor (Halborn, 17 February to 24 March 2026). I take that
description from its repository and have not checked the mainnet date against its chain. Of its code I read only
the signature checks: the signature is 2,420 bytes, or 2,421 with a hash-type byte, and sits in the witness with
the 1,312-byte key. The two are opposite cases with the same primitive (by its README): a new chain that is post-quantum from the
start has no classic-key outputs to migrate
and no classic spend path to retire, while this chain added the type to a UTXO set that has existed since 2014
and carries every migration question with it. Someone checking ML-DSA-44 costs in a scrypt node should measure both.

Another new chain reported field data to Bitcoin developers before this report did. KVANTA5, by its own post on Delving Bitcoin (3 July 2026, topic 2682) and its repository's README, is a SHA-256 proof-of-work chain with ML-DSA-87 as its only signature scheme from its first block, on mainnet since 1 June 2026. The post gives figures from a deliberate stress test on that mainnet: 4,000 outputs created in one transaction and spent in the next, 29,072,055 bytes for the second, about 7,268 bytes an input. I take all of that from the post and have not examined the chain or the code. Like Soqucoin it has no earlier outputs to migrate. Its figures are for the largest ML-DSA parameter set and this report's are for the smallest, so between them they bracket the cost of an input: about 7,268 bytes and 3,782.

The fourth is closer in form to the witness build of the porting note than to this chain. Marscoin's repository
(`marscoin/marscoin`, branch `feat/pq-witness-v2`, commit `8843ef7`, April 2026; integration branch
`feature/quantum-upgrade`, read at `a0fad48`, October 2026) adds `OP_2 <32-byte hash>` as witness version 2, a
key-hash output with the signature and key in the witness. Its scheme is SLH-DSA-SHA2-128s (FIPS 205), with a
32-byte key and a 7,856-byte signature. By its code and documents it is active on regtest and on a public test
network, switched off on mainnet, and not in a release. I read the code and did not connect to
the network. It differs from this chain in signature family and sizes, in being a witness program activated as
a soft fork by buried height, and in not being on a mainnet. What this report adds beside it, among the systems I read, is a post-quantum output type added to an existing Bitcoin-derived chain's UTXO set and validated in consensus
on mainnet (as BPQ did earlier on a split network, above), on a chain that kept running, with the costs, mainnet record, defects and vectors listed as contributions (1) to (4) in section 1.

Two drafts for Bitcoin itself describe the same witness form for ML-DSA-65: a draft with a Bitcoin Core patch by Echelon Labs Research (April 2026) and an address-format draft by Zaenus (November 2026), both posted to Delving Bitcoin. I found them on the day version 1.0 of this report was published; they are set out in the porting note, section 6, which also says what its regtest build does and does not add beside them.

### 10.3 Wallet-side migration: the Blazecoin Quantum Bridge

Every coin on a chain like this is in one of three states: exposed (the public key is already on the chain),
hash-safe (the key is committed only by its hash and has never been revealed) or post-quantum. A wallet that
shows an owner which coins are in which state, and moves them across, is what I call the Blazecoin Quantum
Bridge. The name means a way across on one chain, not a bridge between chains. The move from exposed to hash-safe needs no consensus change on a chain whose outputs commit to keys by hash. The sorting itself, and the advice to move exposed coins first, were drafted for Bitcoin before this report, as a four-level exposure classification with a reference implementation (duncan0k, September 2026; porting note, section 8).

The states are properties of keys as the chain shows them. A key revealed somewhere else (a signed message, a
shared extended public key, another chain with the same history) is exposed although its address has never
spent, and no scan of one chain can see that.

Applied to every unspent output on this chain at block 4,320,675 (9 October 2026, the latest height in the copy of
the index I could run it on, 23 days after activation), the rule gives:

| State | Unspent outputs | Addresses | Coins | Share of supply |
|---|---|---|---|---|
| Exposed: pay-to-public-key outputs | 613,055 | 612,431 | 53.2 million | 6.3% |
| Exposed: address already spent from, or its key also paid by a pay-to-public-key output | 914,893 | 632 | 356.7 million | 42.6% |
| Hash-safe | 397,196 | 2,597 | 320.3 million | 38.2% |
| Post-quantum | 8,825 | 1,663 | 107.5 million | 12.8% |

So 48.9% of the supply sat on keys that were already public, 38.2% was hash-safe and 12.8% was post-quantum. Three
cautions. The post-quantum share is mostly mine: the project treasury (my own
attribution; its size is not published) moved to post-quantum addresses on 28 September, as the node repository's
`PQ_SIGNATURES.md` records, and 98% of the post-quantum value is in two
addresses (a further count on the same index, not part of the published query). The exposed share is a lower
bound and the hash-safe share an upper bound, for the reason just given. And it is one index at one height; the
query is `toolkit/queries/coin_states.sql`.

The companion porting note, section 8, defines five jobs. Their status on this chain is below.
The versions and dates are on the wallet's public release pages
(`github.com/AMA-CSharp-Code/blazecoin-wallet/releases`: 2.0.3 on 12 September, 2.0.5 on 15 September, 2.0.8 on
24 September, 2.0.9 on 28 September, 2.0.22 and light wallet 1.3.8 on 12 November 2026), whose notes describe each
feature (the 400-input batch size is from the code, not the notes). The light wallet 1.3.0 date and the mainnet uses in the table are my own records.

| Job | Status | Where and when |
|---|---|---|
| 1. Triage: show which coins are in which state | Built, used on mainnet | Desktop wallet 2.0.3, 12 September 2026, as a two-state page (each funded address exposed or not, from the wallet's own spends); the third state in 2.0.5, 15 September, when it was run on a mining wallet of 65,702 transactions (my own record). Also a watch-only script for Bitcoin and Blazecoin, `toolkit/triage/pq_triage.py` |
| 2. Hygiene sweep: exposed coins to a fresh classic address | Built, used on mainnet | Desktop wallet 2.0.3, in batches of up to 400 inputs. An exposed address of my own was swept to a fresh address on mainnet on 14 September 2026 (my own record, which does not say which tool sent it) |
| 3. Migration sweep: classic coins into the post-quantum type | Built, used on mainnet | Desktop wallet 2.0.9 and light wallet 1.3.0, 28 September 2026; the treasury moved to post-quantum addresses that day |
| 4. Receive-only custody: migrate with the old key and only the new public key | Proposal | The node has the building block (a public-key-only descriptor, and a locked wallet recognises its coins) and the pool pays coinbases to a pre-generated address list without signing. There is no offline-key or hardware-wallet flow |
| 5. Import of old wallets, keeping both signing paths | Built, used on mainnet | Desktop wallet 2.0.8, built 23 September and released 24 September 2026 |

So four of the five jobs are built and have been used on this chain's mainnet, mostly with my own funds (for the
hygiene sweep, a sweep was made on mainnet but my record does not say the wallet tool sent it);
receive-only custody is a proposal; none of it has been measured for its effect on other users. Two cautions on
figures elsewhere in this report. The consolidation run of section 5 used a separate Consolidate tool (desktop
wallet 2.0.22) on outputs that were already post-quantum, so it measures what a sweep costs in transactions and
block space, not a migration of classic coins. And the only migration count I have is the one in section 6:
3,078 post-quantum outputs funded from classic inputs alone, not split by owner.

## 11. Toolkit and how to reproduce

https://github.com/AMA-CSharp-Code/blazecoin-pq-toolkit

| Item | What it gives you |
|---|---|
| `toolkit/vectors/verify_p2pqh.py` | A reference verifier in about 150 lines of Python: every consensus rule for a post-quantum input, in order. Shares no code with the node or the wallets |
| `toolkit/vectors/pqsig_vectors.json` and its generator, `generate_pqsig_vectors.py` | 3 derivations, 29 signed inputs across 3 transactions, and 40 spend cases including 11 that must fail with a named error. The generator reproduces the file byte for byte |
| `toolkit/vectors/mainnet_examples.json` | Two real transactions with every prevout, including the earliest post-quantum spend on this chain (26 inputs). All 27 inputs verify with the script above |
| `src/bench/pq_verify.cpp` (node repository) | The benchmark in section 5, for Bitcoin Core's bench harness; the command, build and commit are given there. The figures are specific to that machine and build |
| `src/test/mldsa44_acvp_data.h` and `src/test/mldsa44_kat_tests.cpp` (node repository) | NIST's FIPS 204 known-answer cases for ML-DSA-44 (ACVP, 79 cases) and the unit test that pins the vendored code and the wrapper to them, including hedged signing and NIST's modified-signature failures |
| `src/test/fuzz/pq_script.cpp` and `test/pqsig/run_pq_fuzz_seeds.py` (node repository) | Three fuzz targets for the script path (the primitive, the digest and templates, a whole signed spend with scripted mutations) and a seed-corpus runner for the file-input fuzz binary. The first campaign (section 9) found two defects in these targets, none in the node: a second fuzzed seed that padded to the same zeros as the first when the input ran dry, so the "different key" was the same key; and two input consumers in one argument list, whose evaluation order MSVC and clang choose differently, so a Linux crash input did not reproduce on Windows until they were sequenced. Both are worth knowing before writing a target of your own |
| `dogecoin/0001-*.patch`, `0002-*.patch`, `README.md` | The soft-fork variant for legacy script, built on Dogecoin Core 1.14.99 and run on regtest (section 4): opcode, chunking, P2SH form, height activation, a unit test with nine mutations and a functional test that shows the soft-fork property across the activation height; measured sizes; the version-bits finding |
| `bitcoin/0001-*.patch`, `README.md` | The porting note's section 4 built on Bitcoin Core master and run on regtest: the output as witness version 2, unit tests and a two-node soft-fork test; measured weights |
| `litecoin/0001-*.patch`, `README.md`, test scripts | The same output type ported to Litecoin Core v0.21.5.8 and run on regtest; what differs on an older codebase |
| `toolkit/triage/pq_triage.py`, `test_pq_triage.py` | The Bridge's triage job as a watch-only tool: addresses, xpub or descriptor in, exposed, hash-safe or post-quantum out, for Bitcoin and Blazecoin |
| `toolkit/recount_from_node.py` | The same counts as the queries, read block by block from any full node over RPC (read-only, standard library, about four minutes); it needs no index and no schema |
| `toolkit/queries/*.sql` | The counts in section 6, against the project's block indexer (adapt the table names to your own index; the block range of section 6 is already in them). They list the post-quantum addresses; matching those against my own wallets, the ownership table, is not something a query can publish |
| `toolkit/consolidation_run.py` | The consolidation figures in section 5, read from the wallet that made the run |
| `DEFECTS.md` | Each finding, with its fix commit and the test that pins it where there is one |

Commit hashes in this package are those of the project's development repositories. The public repositories
(`blazecoin-core` and `blazecoin-wallet`) are snapshots of the same trees with their own history, so a hash quoted
here will not resolve there: look up the named file or test instead. The benchmark, the
known-answer tests and the fuzz targets are in the public node repository from its commit `4634755` (17 November
2026), where they build. Copies are also in this package under `node-files/`, identical to those files apart from line
endings in `pq_script.cpp` (the checksums in `node-files/README.md` are of the copies here).

Items marked "node repository" are in the node's own repository, `blazecoin-core`, which the toolkit README links;
everything else is in the toolkit repository.

What a reader can redo, and what not. The sizes, the vectors, the verifier's result on the two mainnet
transactions and the three regtest builds reproduce from what is published. The benchmark needs your own
hardware and will give your own figures. The mainnet counts of section 6 need either an index of the chain (`toolkit/queries/`) or
any full node (`toolkit/recount_from_node.py`), and the consolidation run and
the hand-built payment of section 5 are on the chain at the block heights given there. The ownership table is my
own attribution, and that the wallet refused the single large payment is my own record.

For a Dogecoin build specifically: the key-generation vectors apply as they stand, since both use ML-DSA-44. The
signature vectors apply to any verifier that accepts a FIPS 204 context string. The full spend vectors do not,
because the signed message differs. The regtest branch in `dogecoin/` uses Dogecoin-specific tags and context
string on purpose, so its signatures and this chain's never verify on each other's chain.

## 12. Limits

One operator, one small chain, eight weeks. Untuned builds. No independent audit. Severities are my own bounty
verdicts. The absence of a finding in the cryptographic path is weak evidence, and the usage figures say more
about my own infrastructure than about anyone's users. Every node I know of ran my build, so nothing here tests
agreement between implementations. Which addresses are mine is my own attribution.

This report and its code were produced with the help of an AI assistant. The design, the chain and the
responsibility for every claim are mine; the toolkit lets you redo the checks.

## References

Format: author or project; title; URL; version or commit; date of the work; date read. Where a field is left
out, I do not have it verified. Dates are year-month-day.

Standards

- NIST. FIPS 204, Module-Lattice-Based Digital Signature Standard. https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.204.pdf.
  2024-08-13. Read 2026-11-16 (Table 2 for sizes; section 3.4 for hedged and deterministic signing; section 5.2 for the context string).
- NIST. FIPS 205, Stateless Hash-Based Digital Signature Standard. https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.205.pdf.
  2024-08-13. Cited only as the standard Marscoin's scheme comes from; the 32-byte key, 7,856-byte
  signature and category 1 of SLH-DSA-SHA2-128s were confirmed from its Table 2 on 2026-11-17.
- NIST. Automated Cryptographic Validation Protocol (ACVP), known-answer test cases for ML-DSA. The 79 ML-DSA-44
  cases used are in `src/test/mldsa44_acvp_data.h` in the node repository. Added 2026-11-13.

Bitcoin Improvement Proposals (deployed; cited for the mechanisms named; title, authors and date read from each file's header)

- Wuille, Todd, Maxwell, Russell. BIP-9, Version bits with timeout and delay. https://github.com/bitcoin/bips/blob/master/bip-0009.mediawiki. Deployed. Assigned 2015-10-04. Header read 2026-11-17.
- Andresen. BIP-16, Pay to Script Hash. https://github.com/bitcoin/bips/blob/master/bip-0016.mediawiki. Deployed. Assigned 2012-01-03. Header read 2026-11-17.
- Palatinus, Rusnak, Voisine, Bowe. BIP-39, Mnemonic code for generating deterministic keys. https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki. Deployed. Assigned 2013-09-10. Header read 2026-11-17. Cited for the seed phrase the light wallet derives from (section 2.1).
- Todd. BIP-65, OP_CHECKLOCKTIMEVERIFY. https://github.com/bitcoin/bips/blob/master/bip-0065.mediawiki. Deployed. Assigned 2014-10-01. Header read 2026-11-17.
- Wuille. BIP-66, Strict DER signatures. https://github.com/bitcoin/bips/blob/master/bip-0066.mediawiki. Deployed. Assigned 2015-01-10. Header read 2026-11-17.
- Lau, Wuille. BIP-143, Transaction Signature Verification for Version 0 Witness Program. https://github.com/bitcoin/bips/blob/master/bip-0143.mediawiki. Deployed. Assigned 2016-01-03. Header read 2026-11-17.
- Wuille, Nick, Towns. BIP-341, Taproot: SegWit version 1 spending rules. https://github.com/bitcoin/bips/blob/master/bip-0341.mediawiki. Deployed. Assigned 2020-01-19. Header read 2026-11-17.
- Wuille, Nick, Towns. BIP-342, Validation of Taproot Scripts. https://github.com/bitcoin/bips/blob/master/bip-0342.mediawiki. Deployed. Assigned 2020-01-19. Header read 2026-11-17. Cited for OP_SUCCESSx.

Proposals and drafts

- Hunter Beast, Ethan Heilman, Isabel Foxen Duke. BIP-360, Pay-to-Merkle-Root.
  https://github.com/bitcoin/bips/blob/master/bip-0360.mediawiki. Draft, version 0.12.1 (2026-07-24), file commit
  `e7263a4` (2026-08-03). Read 2026-11-16.
- Jameson Lopp, Christian Papathanasiou, Ian Smith, Joe Ross, Steve Vaile, Pierre-Luc Dallaire-Demers. BIP-361,
  Post Quantum Migration and Legacy Signature Sunset. https://github.com/bitcoin/bips/blob/master/bip-0361.mediawiki.
  Draft, assigned 2026-02-11, file commit `da7cc67` (2026-04-17). Read 2026-11-16.
- conduition, Heilman, Kudinov, Kurbatov, Nick, remix7531. SHRINCS: A Compact Hash-Based Signature Scheme.
  https://github.com/SHRINCS/shrincs-bip/blob/main/SHRINCS.md. Draft, no BIP number, commit `990cd1f`
  (2026-11-09). Read 2026-11-16.
- Ed Tubbs. Post-Quantum Signature Commitments (Dogecoin draft).
  https://github.com/dogecoinfoundation/libdogecoin/blob/0.1.5-dev/doc/spec/bip-post-quantum-signature-commitments.mediawiki.
  libdogecoin branch `0.1.5-dev` at `b416f55`; created 2026-02-18. Read 2026-11-16.

Code

- Bitcoin Core. https://github.com/bitcoin/bitcoin. Version 28 is the base of this chain's node; master at
  `a527a00` (2026-11-13) is the base of the witness port in `bitcoin/`.
- Dogecoin Core. https://github.com/dogecoin/dogecoin. Version 1.14.99, master at `b38c83f` (2026-11-09 UTC); the
  base of the soft-fork variant in `dogecoin/`.
- Litecoin Core. https://github.com/litecoin-project/litecoin. Release v0.21.5.8, tag commit `ec1b6489`; the base
  of the port in `litecoin/`.
- Anhao, N. Bitcoin Post-Quantum (whitepaper). https://bitcoinpq.org/download/bitcoinpq-whitepaper-english.pdf. Undated (2018).
  Project site https://bitcoinpq.org/ ; node https://github.com/bitcoinpostquantum/bitcoinpq, last commit `28a1f3c`
  (2019-10-23): `src/chainparams.cpp` (`BPQHeight = 555000`, checkpoints at 555,100 and 600,000),
  `src/script/interpreter.cpp`. Read 2026-11-17.
- pq-crystals. Dilithium reference implementation (C). Vendored into the node repository under
  `src/crypto/mldsa/` by node commit `685aac54b7` (2026-09-14) from upstream commit `d35ba3f`, with the random-number
  path removed there (`config.h` makes randomised signing a compile error and `randombytes.c` is not vendored): key
  generation takes its seed from the caller and signing is deterministic.
- Open Quantum Safe. liboqs, version 0.15.0. The library the Dogecoin draft's code uses; its use there was read
  on 2026-11-11 (comparison document, section 4, point 6).
- LLVM project. libFuzzer, as shipped with clang 17. Used for the campaign of 2026-11-13.
- Echelon Labs Research. Post-Quantum Witness Version 3 Key-Path Spending (ML-DSA-65). BIP draft, created
  2026-03-31. https://github.com/btcpqresearch/bip-pq-witness-v3, commit `7bbfb29` (2026-04-15); posted to Delving
  Bitcoin 2026-04-16, https://delvingbitcoin.org/t/2422. Draft text and post read 2026-11-17; the patch not read.
- Zaenus. Post-quantum address format draft (ML-DSA-65), version 0.2. https://github.com/Zaenus/btc-safe, commit
  `4e09003` (2026-11-13); posted to Delving Bitcoin 2026-11-13, https://delvingbitcoin.org/t/3067. Read 2026-11-17.
- KVANTA5. Empirical ML-DSA-87 data from a live SHA-256 PoW chain. Delving Bitcoin, 2026-07-03,
  https://delvingbitcoin.org/t/2682; repository https://github.com/Kvanta-Organization/Kvanta5-Core (README). Read
  2026-11-17. Described from the post and the README; the chain and the code were not examined.
- Marscoin. https://github.com/marscoin/marscoin. Branches `feat/pq-witness-v2` (commit `8843ef7`, 2026-04-19)
  and `feature/quantum-upgrade` (at `a0fad48`, 2026-10-12). Read 2026-11-16.
- Soqucoin. https://github.com/soqucoin/soqucoin. README, `doc/ECDSA_ELIMINATION.md` and part of
  `src/script/interpreter.cpp`; self-described, the rest not examined. Read 2026-11-12 and 2026-11-16.
- Halborn. Soqucoin Blockchain Node, audit page. https://www.halborn.com/audits/soqucoin/soqucoin-blockchain-node-a4f1f7.
  Audit dated 2026-02-17 to 2026-03-24. Used for the audit dates only.

This project

- Blazecoin Core (the node repository). `github.com/AMA-CSharp-Code/blazecoin-core`. `PQ_SIGNATURES.md` is the
  specification with its decision log, activation record and test record; the benchmark is at commit
  `93fcbc3f6f`. That document carries a dated correction (17 November 2026) to its sigop paragraph: its 132
  microsecond verification time is from a different (C#) implementation, where section 5 here measures the node's
  own code at 102.9, and its "1,600 post-quantum verifications per block" should read 400 outputs created per block
  (section 5, point 3). Read at public commit `4634755`.
- Blazecoin wallet (the wallet repository: desktop and light wallets). `github.com/AMA-CSharp-Code/blazecoin-wallet`.
  `BlazecoinWallet.Lite.Core/Pq/PqKeyDerivation.cs` is the derivation cited in section 2.1 (present in the public
  snapshot, checked 2026-11-17). The versions and dates cited in section 10.3 are on its public release pages
  (`github.com/AMA-CSharp-Code/blazecoin-wallet/releases`, read 2026-11-17).
- Companion documents in the toolkit repository: the porting note (`BITCOIN-PORTING-NOTE.md`), the comparison
  document (`DESIGN-COMPARISON.md`, which carries the sources for every other project named here) and the defect
  list (`DEFECTS.md`).
