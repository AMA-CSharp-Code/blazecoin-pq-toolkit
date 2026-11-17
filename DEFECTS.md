# Defects found after the post-quantum fork went live

hyperminer (bitcointalk), admin@blazecoin.co.uk. Version 1.0.1, 17 November 2026. Companion to the field report (REPORT.md).

Compiled 2026-11-11; last checked against the code 2026-11-17. Sources: the bug-bounty records (2026-11-06 to
11-10), the node repository (`blazecoin-core`) and the wallet repository. Commit hashes in this list are those of the project's development repositories. The public repositories
(`blazecoin-core` and `blazecoin-wallet`) are snapshots of the same trees with their own history, so a hash quoted
here will not resolve there: look up the named file or test instead. Every fix listed by 2026-11-11 was
checked against the code on that date: the commit exists and the named test is in the tree. Later entries are
dated where they appear.

Scope: defects in the post-quantum path, in the activation channel, and in the parts of a Core 28 fork that the
PQ work depends on. Left out: other findings about the light wallet's trust in its gateway, the website, the pool and
the faucet. They are real but say nothing about adding a PQ output type.

Reporters are not named here, with thanks to all of them.
No addresses or txids.

Timeline for reference: fork built 2026-09-14/15, active at block 4,250,000 on 2026-09-16 (node 2.1.0).
Bounty severities published in the node's SECURITY.md on 2026-10-20. The first outside bounty report arrived on
2026-10-25, about five and a half weeks after activation; it concerned the light wallet's proof checks (fixed in
light wallet 1.3.1) and is outside this list's scope. The reports on this list date from 2026-11-06.
Node 2.1.2 on 2026-11-06/07, node 2.1.3 on 2026-11-09/10. "V2 launch" below means the cutover of the live
services to the Core 28 node on 2026-06-18.

## Summary

| # | Defect | Part | Found by | Severity | Live for | Fixed in |
|---|---|---|---|---|---|---|
| A1 | PQ dust threshold priced with a classic input size | Node policy + all wallets | Outside report | Low | 7 weeks | Node 2.1.2, `1a8bd35588` |
| A2 | PQ public-key cache accepted any length from the wallet file | Node wallet | Outside report | Low | 7 weeks | Node 2.1.2, `1a8bd35588` |
| A3 | Change from a PQ spend went to a classic address | Desktop wallet, 3 paths | Operator, then outside report | Medium | 12 days, then 51 days | Wallet `6e41cea`, then `f6b2469` |
| A4 | Old wallets cannot add PQ keys with the wallet command | Node wallet | Known at build | Design limit | Open | Not fixed: new wallet + sweep, or an imported descriptor with a new backup |
| A5 | Sigop count of 50 overstates verify cost about 28x, and caps PQ outputs created at 80 per standard transaction and 400 per block | Consensus constant | Operator (node benchmark); the cap found in a code check, 2026-11-17 | Low: no effect on spending, a real limit on creating outputs | Open | Not fixable without a fork |
| B1 | "Stop sending" fork state trusted an unsigned server claim | Light wallet + gateway | Outside report | Medium | 7 weeks | Wallet `e3af5a7`; keys pinned `d79832d` (light wallet 1.3.8) |
| B2 | Fork wall-clock time predicted 15 hours early | Operations | Operator | None | n/a | Process: derive from recent intervals |
| C1 | A witness transaction could stop all block production (not observed on mainnet) | Node mempool + miner | Outside report | High | Since V2 launch | Node 2.1.2, `1a8bd35588` |
| C2 | Wallet issued and paid SegWit addresses nobody can spend | Node wallet | Outside reports, 3 rounds | Low to Medium | Since V2 launch | 2.1.2 and 2.1.3 (four commits) |
| C3 | Timelocks checked by the mempool but not by blocks | Consensus (by design) | Outside report | Low, by design | By design | Warning + doc, `1a8bd35588` |
| D1 | Wallet history tooling stalled on large mining wallets, then on PQ-consolidated ones | Desktop wallet | Operator | Low | First part fixed the day before activation; second part 2 weeks | Wallet `5a01793` (2026-09-15), `8e13187` (2026-09-30) |
| D2 | A wallet of thousands of small PQ outputs could not make a large payment | Desktop wallet | Operator, and a user's question | Design limit | 8 weeks | Wallet 2.0.22, `787430e` (consolidation tool) |
| E1 | "MaxSatisfactionWeight is 4x too high" | Node wallet | Outside report | Not a bug | n/a | None |

Counts: 13 entries (D2 added 2026-11-12). 7 came from outside reporters, 6 were my own. Of the 10
that are defects or limits in the node and protocol work, 5 are in the PQ path (A1 to A5), 2 in activation (B1,
B2), 3 in the legacy-script base (C1 to C3); D1 and D2 are wallet-side consequences of transaction size.
The one High was not in the PQ code at all.

## A. The post-quantum path

### A1. Dust threshold priced with a classic input size
- **What.** The relay rule "an output is dust if spending it costs more than it holds" assumed a 148-byte input
  for every non-witness output. An input of the new type, P2PQH (pay to post-quantum key hash), is 3,782 bytes. The node accepted PQ outputs down to 573 satoshi;
  the correct floor at the same fee rate is 11,475 satoshi.
- **Effect.** Outputs between 573 and 11,474 satoshi could be created and relayed but were uneconomic to spend.
  No loss of funds; UTXO-set litter.
- **Fix.** `src/policy/policy.cpp` prices P2PQH by its real spend (3 + 2,420 + 3 + 1,313 bytes of scriptSig).
  Test: `pqsig_dust_threshold` in `src/test/pqsig_tests.cpp`; functional section in `wallet_blazecoin_pq.py`.
- **Coupling, the real lesson.** This is a relay-policy number that every wallet copies. The light wallet, the
  desktop wallet's three send planners and the faucet all carried their own dust constant and all had to change
  (wallet `83aa1df` for the two wallets; the faucet is a separate service whose fix is not published here).
  Rollout order mattered: wallets first, node second. An old wallet on a new node would have
  had sends refused when they left 546 to 11,474 satoshi of PQ change.
- **For other chains.** Any place the code says "148" or assumes an input size is a PQ bug waiting. Search for
  the constant before activation, and count how many clients duplicate it.

### A2. PQ public-key cache accepted any length from the wallet file
- **What.** The descriptor cache stores derived ML-DSA public keys in the wallet database so they are not
  re-derived at every load. `DescriptorCache::CachePQPubKey` accepted any byte length read from disk.
- **Effect.** A corrupted or tampered wallet file could put a wrong-length key in the cache. The address derived
  from it would be unspendable. Needs write access to the wallet file, hence Low.
- **Fix.** Refuses anything but 1,312 bytes (`[[nodiscard]] bool`), expansion yields no address, and the wallet
  load reports the file as corrupt. Test: `descriptor_tests.cpp` (lengths 0, 32, 1,311, 1,313 refused).
- **For other chains.** Classic keys are validated by the curve library when parsed. A lattice public key is an
  opaque byte string to the surrounding code; every boundary that reads one has to check the length itself.

### A3. Change from a PQ spend went to a classic address
- **What.** Spending PQ coins while the node's default change type was classic put the change on an ECDSA key.
  Found three times, in three code paths:
  1. 2026-09-28, operator: a manual send from the pool-reward wallet spent a PQ coin and returned a large change
     output to a classic address. The daemon ran `changetype=legacy` and `sendtoaddress` cannot override it.
  2. 2026-11-06, outside report: the desktop wallet's vintage-send planners asked for a classic change address.
  3. Same report: the desktop auto-payout engine used `sendtoaddress` and so inherited the daemon default.
- **Effect.** No loss and no attacker. A silent downgrade: the user believes the coins are behind a PQ key and
  part of them are not. Rated Medium because it is silent.
- **Fix.** One change policy for every send path: PQ change whenever the wallet holds PQ keys, shown to the user
  at review, never a silent fallback to classic (wallet `6e41cea` 2026-09-28, `f6b2469` 2026-11-06, unified in
  `177bd5b` 2026-11-09). Tests: `SendChangeTests`.
- **For other chains.** "Where does the change go" has to be answered once, in one place, before activation. The
  first fix here covered one page; the same bug was still in two other paths five and a half weeks later (39 days).

### A4. Old wallets cannot add PQ keys with the wallet command (design limit, open)
PQ keys are derived from a wallet's master key at creation. A wallet made before the fork build has no PQ chain
and `getnewaddress "" pq` returns an error telling the user to create a new descriptor wallet. This was
chosen to avoid an in-place wallet-format upgrade. For the wallet's own commands it means migration is "new
wallet, then sweep", which costs every holder a transaction and, for a reused classic address, exposes nothing
new. There is one other route: an existing wallet can gain a PQ chain by importing a PQ descriptor that carries a
fresh random seed. Those keys do not derive from the wallet's old seed, so no earlier backup covers them and a
new backup is needed at once. My two pool wallets were given PQ chains this way on 2026-09-15, with
new backups taken. Stated as a limit, not a bug.

### A5. Sigop count overstates verify cost, and limits how many PQ outputs can be created (open)
One `OP_CHECKPQSIG` counts as 50 legacy signature operations (`PQ_SIGOP_COST` in `src/script/script.h`). The node
benchmark (REPORT.md section 5) measured a PQ input at 1.8x the CPU of a classic input, so the count overstates
cost by about 28x. The number was chosen from a C# benchmark of a different implementation and was never
re-measured on the node. A consensus constant; changing it is a fork.

It is not harmless, and an earlier version of this entry said it was. The legacy sigop count is taken from the
scripts a transaction carries (`GetLegacySigOpCount` in `src/consensus/tx_verify.cpp`), and the opcode sits in the
output script, so the 50 is charged to the transaction that **creates** a PQ output, not to the one that spends
it. The count is then multiplied by 4, the witness scale factor, giving 200 per PQ output. Two limits follow:

- a block can create at most 400 PQ outputs: 80,000 / 200 (`MAX_BLOCK_SIGOPS_COST` in
  `src/consensus/consensus.h`, checked in `src/validation.cpp`); this is consensus;
- a standard transaction can create at most 80: 16,000 / 200 (`MAX_STANDARD_TX_SIGOPS_COST` in
  `src/policy/policy.h`); this is relay policy.

By bytes alone a block would hold about 23,000 such outputs, so here the sigop limit binds long before the byte
limit. For **spending**, the scriptSig is two pushes and carries no sigops, so the byte limit binds first.
The unit test `pqsig_sizes_and_sigops` pins where the count is charged. A payout to more
than 80 PQ addresses has to be split across transactions. The node's design document gave 1,600 PQ checks per block and now carries a correction dated 2026-11-17; that figure left out the factor of 4 and counted checks, where the limit is on outputs created.

## B. Activation and the client-update channel

### B1. The "stop sending" fork state trusted an unsigned server claim
- **What.** Light wallets show a banner before a hard fork: "update required before block N", and after N an old
  client stops sending. The fork name, height and minimum version came from the gateway's status response, and
  the Stopped state was decided from the gateway's own claimed tip.
- **Effect.** A hostile or compromised gateway could stop every light wallet from sending, or print its own text
  in the banner. No theft; a denial of service and a phishing surface on the one channel users are told to trust.
- **Fix.** `ForkAnnouncement`: strict shapes for name and version, no fork at or below the shipped checkpoint, and
  the Stopped state is reachable only for an announcement signed by a project key pinned in the client. Unsigned
  announcements show as a warning. The tip used is the wallet's own verified header tip (wallet `e3af5a7`, spec
  `PQ_SIGNATURES.md` section 7.1, node repo `81fcd64b19`).
- **Keys pinned 2026-11-12 (wallet `d79832d`).** `ForkAnnouncement.PinnedKeys` holds two keys, a primary
  and a spare; a signature by either is authentic. The private keys are offline. My side is
  `Tools/ForkAnnouncementSigner` in the wallet repo. Tests: the build pins two distinct well-formed keys, a
  stranger's signature cannot stop sends with the shipped keys, either pinned key authenticates.
- **Released 2026-11-12.** The keys are pinned in light wallet 1.3.8 (released 2026-11-12). Installed light
  wallets up to 1.3.7 pin nothing until they are updated, so for them a real fork still shows only as a warning.
- **For other chains.** The PQ activation for this chain used the unsigned version of this channel on 2026-09-16.
  Nothing went wrong, but the mechanism that tells light wallets "the rules change at N" is itself part of the
  fork's attack surface and deserves the same review as the consensus code.

### B2. Fork wall-clock time predicted 15 hours early
The fork height was announced with an estimated time. The chain had been running close to its
30-second target, at about 27 seconds a block through the evening of 15 September. Overnight most of the hash rate
went away: the last 750 blocks before the fork included two stalls, of about 4.7 and 12.2 hours, and block
4,250,000 arrived about 15 hours after the estimate (intervals measured from the block index). Nothing broke, because activation
is by height. The lesson is for announcements: quote the height, and derive any clock time from recent intervals
at the moment of writing. On a chain with few miners the estimate is only as good as the largest miner's uptime.

## C. The legacy-script base (SegWit code present, never active)

These are not PQ defects. They are in this list because a chain that adds a PQ output type by hard fork to a
fork of a recent Bitcoin Core, with SegWit never activated, has all of them, and because the worst defect found
in eight weeks was here and not in the new cryptography.

### C1. A witness transaction could stop all block production (High)
- **What.** SegWit is never active on this chain, so a block containing witness data is invalid. The mempool
  only checked that a witness transaction was standard, never that witnesses were allowed. Upstream Core removed
  its `no-witness-yet` check in Bitcoin Core 0.17 (commit `fa7a6cf1b3`, "policy: Treat segwit as always
  active"), when the witness script flags began to be enforced from genesis; burying the deployment came later,
  in 0.19 (pull request 16060). A standard P2WPKH (pay to witness public key hash) or Taproot key-path spend was
  accepted, the block assembler included it, and every block template then failed validation.
- **Effect.** One cheap transaction halts mining on every node that holds it, and it survives a restart through
  the saved mempool. Not observed on mainnet before the fix: block production never halted for this reason.
- **Fix.** The mempool refuses any transaction with a witness while SegWit is inactive for the next block, before
  standardness, so a saved mempool drops it on reload. The miner skips witness transactions as a second guard.
  Test: `feature_blazecoin_no_witness.py`, which fails on the unfixed build at the admission assert.
- **For other chains.** May apply to a fork of Core 0.17 or later that never activated SegWit. An older base (for
  example a 0.14-era codebase) still carries the upstream check. Worth one regtest test either way.

### C2. The wallet issued and paid SegWit addresses nobody can spend
- **What.** With SegWit inactive, a bech32, bech32m or wrapped-SegWit output can be created and mined but never
  spent. The node wallet would still make such addresses on request, pay them, and send change to them if
  configured to.
- **How it went.** Three rounds. 2.1.2 refused bech32 and bech32m. Two days later a second reporter showed that
  wrapped SegWit (`p2sh-segwit`) was still issued: the first fix had listed the types by hand and missed one. A
  third found `sendall` and explicit change addresses bypassed the rule. 2.1.3 replaced the hand-written checks
  with one list of witness output types and one rule that every outgoing script passes through.
- **Fix.** Node `1a8bd35588`, `8a2e2ffb88`, `1b595c4fb7`, `787e87c3aa`. The mempool also refuses transactions that
  create a witness output.
- **For other chains.** When a fix is "refuse type X", ask what enumerates the types. The second and third
  reports were the cost of not asking.

### C3. Timelocks are enforced by the mempool but not by blocks (Low, by design)
CLTV, CSV and BIP-68 are never active in consensus here, as documented, because the chain's history predates
them. The mempool still applies them as policy. A miner can therefore include a transaction the mempool would
hold back. Activating them is a soft fork, not a fix. The wallet now warns when a descriptor with a timelock is
imported, and the consequences are documented. Relevant to anyone designing PQ migration schemes that rely on
timelocks (commit-then-reveal, delayed recovery): check that the timelock opcodes are consensus on the target
chain first.

## D. Operational

### D1. Wallet history tooling stalled on large mining wallets, then on PQ-consolidated ones
The pool-reward wallet receives one output per block and, since the fork, consolidates nightly in 26-input,
98 KB transactions. Two desktop-wallet features that walk a wallet's history failed on such wallets, at two
different times.

- The exposure scan paged the transaction list quadratically (about five minutes on a 65,702-transaction
  wallet). This was found while preparing the fork and fixed on 2026-09-15, the day before activation (wallet
  `5a01793`). It is a wallet-size defect and owes nothing to PQ transactions; it is listed because the fork
  preparation is what ran the scan on a wallet that large.
- The provenance trace ran out of memory following consolidated inputs. This one did appear after activation,
  on wallets full of PQ consolidations, and was fixed on 2026-09-30 (wallet `8e13187`).

The cause in both is transaction count, size and input count, not the signature scheme, but PQ made large
consolidations the normal case.

### D2. A wallet of thousands of small PQ outputs could not make a large payment
One standard transaction (100,000 bytes) holds 26 PQ inputs, so a wallet can pay at most the sum of its 26
largest outputs in one transaction. A mining-reward wallet that had 6,511 PQ outputs when
the payment below was refused (largest about 3,200) held about 2.1 million but could pay about 49,000 at once; the desktop wallet refused a 350,000 payment ("inputs
size exceeds the maximum weight") and it was built by hand as 12 transactions with chosen inputs. A user asked
the same week how to consolidate a mining wallet. Fix: a Consolidate tool on the wallet's Send page (wallet
2.0.22, `787430e`; planner tests `ConsolidationTests`): it counts the outputs, plans batches by bytes (26 PQ or
400 classic inputs per transaction, never one-input batches, never PQ coins to a classic address), shows the plan
and broadcasts to a fresh address in the same wallet. First run on mainnet 2026-11-12, later the same day, on the 1.75 million left in 6,243 outputs: 6,243 outputs to 241 in
241 transactions (240 of 98,385 bytes), 23,623,799 bytes, 24 consecutive full blocks and part of a 25th (measured by
`toolkit/consolidation_run.py`). A second round started early merged only the 171 outputs that had confirmed; the
tool now shows outputs still confirming. The first outside user merged their wallet in 9 transactions. The limit
itself is not fixable without a larger standard transaction size or a witness discount.

Source of the figures: the consolidation run (6,243 outputs, 241 transactions, the byte and block counts) was
measured from the node's wallet by the toolkit script, and its transactions are on the chain in blocks 4,420,140
to 4,420,164. The 350,000 payment is on the chain too: 12 transactions with 293 inputs in blocks 4,418,126 to
4,418,130, earlier on 2026-11-12, and the payment's inputs and the run's inputs, net of the payment's
change and of outputs received in between, give the wallet's contents before it (about 2.1 million; the 26 largest about 49,000). That the wallet refused the single payment, and the
outside user's 9 transactions, are my own records.

## E. Reported, not a bug

### E1. "MaxSatisfactionWeight is 4x too high"
A reporter read the PQ input's satisfaction weight as four times its size. Weight units are four per byte for
non-witness data; classic P2PKH (pay to public key hash) reports the same way, and the test suite pins the PQ input at 3,782 bytes
(15,128 weight units as the code reports it).
Listed because reviewers new to a non-SegWit chain will raise it again.

## What the list says

1. No defect was found in the ML-DSA-44 code, the digest or the script path. That is weak evidence: the traffic
   was honest and almost all my own, every known node ran one build, and the known-answer vectors and
   fuzz targets date only from 2026-11-13. Vendoring the reference implementation, deterministic signing and
   shared test vectors are practices I would repeat; this list cannot show they are why nothing was
   found.
2. The defects were at the edges: a size assumption in policy (A1), an unchecked length at a storage boundary
   (A2), a default in the wallet (A3) and an unauthenticated notice channel (B1).
3. The most serious defect was in the unmodified base, in a rule upstream had removed (C1).
4. Outside review found what internal testing had not: 7 of 13 entries, including the High. The first outside
   bounty report of any kind came about five and a half weeks after activation (2026-10-25, outside this list);
   the fork had been live for seven weeks when the first report on this list arrived.
5. Two fixes were incomplete the first time (A3, C2). In both, the first fix handled the reported path and the
   lasting fix replaced several copies of a rule with one.
6. Size is the recurring theme: dust, fees, change, history tooling and block capacity all moved because an input
   went from 148 to 3,782 bytes.

## Limits of this list
- One operator, one small chain, eight weeks. Absence of a finding is weak evidence.
- No independent audit. The NIST ACVP (Automated Cryptographic Validation Protocol) known-answer vectors are pinned (`src/test/mldsa44_kat_tests.cpp`, 79 ML-DSA-44
  cases) and the PQ script path has three fuzz targets (`src/test/fuzz/pq_script.cpp`), both since 2026-11-13 (copies of
  both files are in this repository under `node-files/`);
  the first libFuzzer campaign (2026-11-13: 10 + 10 + 15 minutes, 4.1 million executions, ASan (AddressSanitizer) + UBSan (UndefinedBehaviorSanitizer)) found
  nothing in the node and two defects in the harness (`PQ_SIGNATURES.md` section 15). Minutes, not weeks.
- Severities are the bounty verdicts, set by me.
- "Live for" is in whole weeks, counted from activation (2026-09-16) to the fixing release where that applies.
  A3 gives the days to each of its two reports, C1 and C2 predate the fork ("Since V2 launch", the node cutover
  of 2026-06-18), and the first half of D1 was fixed the day before activation.
- The figures in B2 are my measurements. In D2 the run and the payment are on the chain; that the
  wallet refused the payment, and the outside user's 9 transactions, are my records.
