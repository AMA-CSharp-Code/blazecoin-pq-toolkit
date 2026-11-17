# Carrying a deployed ML-DSA-44 output type to Bitcoin: what would have to change

hyperminer (bitcointalk), admin@blazecoin.co.uk. Version 1.0, 17 November 2026. Companion to [the field report](REPORT.md).

## 1. Summary

A small proof-of-work chain forked from Bitcoin Core has enforced ML-DSA-44 signatures in consensus since
September 2026, through one new output type: a hash of the public key in the output, and the key and signature
in the spending input. The field report describes it and gives the measurements.

This note asks a narrower question: could Bitcoin do the same thing?

- **As it stands, no.** The deployed version is a hard fork, puts 3.7 KB of signature data in the non-witness
  part of the transaction, and was activated by one operator. None of that is acceptable on Bitcoin.
- **The shape can be carried as a soft fork**, by making it a new witness program. Section 4 describes that. I
  have built it as a patch against Bitcoin Core and run it on regtest, nowhere else.
- **It would not be new to Bitcoin.** A key-hash output with a post-quantum signature is roughly where BIP-360
  started in 2024, and its authors moved away from it on purpose. Section 6 sets out what that choice gained
  and what a simple key-hash type would still offer.
- **The costs can be stated.** On Bitcoin's limits a witness-placed ML-DSA-44 input is about 976 virtual bytes,
  17 times a Taproot key-path input. Section 5 has the table.
- **The wallet side is a piece of work in its own right: the Blazecoin Quantum Bridge.** On a chain whose keys
  are committed by hash, every coin is in one of three states, exposed, hash-safe or post-quantum, and migration
  needs only the old key and the new public key, so it can begin before hardware wallets sign ML-DSA. Four of its
  five jobs are shipped and used on my chain; one, receive-only custody (job 4), is a proposal. Section 8.
- **What transfers best is not the output type.** It is the signed-message design, the test vectors, and the
  list of things that broke in wallets and policy. Those apply whichever output type Bitcoin chooses.

This is a study of one option by someone who has run a version of it. It is not a proposal, and I do not
argue that Bitcoin should prefer it to its current drafts.

## 2. The deployed pattern, in brief

**Output (34 bytes):** `0x20 <32-byte key hash> OP_CHECKPQSIG`

**Spend:** two pushes in the scriptSig, `<signature: 2,420 bytes> <key blob: 1,313 bytes>`.

- The key blob is one algorithm byte followed by the ML-DSA-44 public key. The output commits to a tagged hash
  of the whole blob, so the algorithm is inside the commitment and a later scheme needs no new address format.
- Until an output is spent the chain sees only a hash.
- The signed message is a tagged hash of a BIP-143-shaped preimage, so the cost of hashing does not grow with
  the number of inputs. There is no sighash-type byte.
- Signing uses a FIPS 204 context string that is different for transactions and for signed messages.
- Signing is deterministic, from the reference implementation with the random-number path removed.
- Single key only. No multisig, no script composition.

## 3. Why it cannot be copied as it is

1. **It is a hard fork.** A node that does not know the new opcode rejects the spend. Old nodes and new nodes
   then disagree about which blocks are valid.
2. **It raises a consensus limit.** Script elements are capped at 520 bytes. The deployed version raises that
   to 5,000 for inputs of this type. An old node rejects those inputs for size alone.
3. **The bytes are in the wrong place.** On Bitcoin, signature data belongs in the witness, where it is
   counted at a quarter of its size. The deployed chain has no active witness, so it had no such choice. On
   Bitcoin the same layout would cost nearly four times what it needs to.
4. **The activation does not exist elsewhere.** One operator updated every node in a day.

## 4. The port: the same commitment as a witness program

Built as one patch against Bitcoin Core master and run on regtest only (the patch and its tests are in this
repository, under `bitcoin/`). This is the smallest change I can see that keeps the pattern and removes the four problems
above.

**Output:** a new witness version with a 32-byte program: `OP_n <32-byte key hash>`, where the hash is the same
tagged hash of `algorithm byte + public key`. 34 bytes of script, as for Taproot.

**Spend:** an empty scriptSig and a witness of exactly two items, `<signature> <key blob>`.

Why this is a soft fork: a node that does not know the witness version treats the output as spendable by
anyone and accepts the block. Upgraded nodes enforce the signature. This is how SegWit version 1 was added.

What has to be specified, and what the deployed chain suggests for each:

| Question | Suggestion from the deployed version | Open on Bitcoin |
|---|---|---|
| Witness item size | Items of 2,420 and 1,313 bytes are needed; today's consensus limit on a script-path stack item is 520 bytes (and relay policy allows 80) | A new version can set its own limit. The rule should be exact lengths per algorithm, not a general raise |
| Signed message | Hash amounts and scripts once per transaction, under a domain tag | Bitcoin already has the BIP-341 message. Reusing it with a new extension flag is better than my BIP-143-shaped digest |
| Sighash modes | None: one mode, exact signature length | Bitcoin users rely on other modes. Dropping them is a real loss here |
| Domain separation | FIPS 204 context string per use | Costs nothing. I would keep it |
| Randomness | Deterministic signing only | Hedged signing is the FIPS 204 default and resists fault attacks better. Worth a real discussion |
| Algorithm agility | Algorithm byte inside the committed blob | The alternative is a new witness version per scheme. The byte is cheaper |
| Validation cost limit | I set a sigop count from the wrong benchmark and it is 28 times too high. It is charged where an output is created, so it also caps a block at 400 new post-quantum outputs and a standard transaction at 80 (the defect list, A5) | Limit by bytes, not by a per-signature count. Measure on the node before fixing any constant, and check which transaction the count is charged to |
| Relay policy | Dust, fee and size rules all assumed a 148-byte input | Every such constant needs a value for this type before activation |
| Address | Base58Check, 52 characters | Bech32m, as for any witness program |

What the regtest build chose and showed:

- Witness version 2, the BIP-341 message with extension flag 2 under its own tag, SIGHASH_DEFAULT only, the
  context string `bitcoin-pq-v1`, and a BIP-9 deployment that is always active on regtest and never active on any
  live network.
- **The version number is a placeholder.** `OP_2 <32-byte program>` is the template BIP-360 assigns to
  pay-to-Merkle-root ("P2MR (pay to Merkle root) outputs use SegWit version 2", addresses beginning `bc1z`). On Bitcoin the two could
  not coexist: a real proposal would need a different witness version or program length.
- **The soft-fork property holds in a two-node test.** A block carrying a spend with a bad signature is accepted
  by a node without the deployment and rejected by a node with it.
- **Four places in Bitcoin Core had to learn the new program besides the interpreter**, and the first unit tests
  found none of them. The two-node test found two. Relay policy refuses a spend of any undefined witness version,
  so the upgraded node would not relay its own type until that check was told the program is defined once the
  deployment is active. And the hashes the BIP-341 message needs are precomputed only for transactions that spend
  a Taproot output, so a real spend of the new program reached the signature check with no data. The second is
  not a new finding: Marscoin's P2WPQH branch needed the same change and carries a unit test for it
  (`p2wpqh_precomputation_detects_spends`, section 6). The Litecoin port and the re-test it prompted found the
  other two. `DeferringSignatureChecker`, which wraps another checker, did not pass the new check on and answered
  false for every such spend. And the list of all consensus script flags (`GetAllConsensusScriptFlags`) lacked
  the new flag, which Core's own `versionbits_tests` reports. Three of Core's existing functional tests also had
  to change: `p2p_segwit.py` and `feature_taproot.py` used version 2 with a 32-byte program as their example of
  an undefined one, and `rpc_blockchain.py` lists the deployments it expects.
- Dust for the new output is priced from its real witness: 3,057 sat, against 294 sat for P2WPKH (pay to witness public key hash) at the default
  dust rate.
- **The same type was ported on 16 November 2026 to Litecoin Core v0.21.5.8, regtest only.** The weights are
  identical: input 3,904 WU (weight units), a one-input spend 4,118 WU / 1,030 vB. Witness version 2 does not collide with MWEB (MimbleWimble Extension Blocks),
  which uses versions 8 and 9. The FIPS 204 context string is chain-specific (`litecoin-pq-v1`), so a signature
  made for one build does not verify on the other. The 0.21 codebase labels the consensus failure differently:
  `non-mandatory-script-verify-flag (PQ signature is invalid)` where Bitcoin master says
  `block-script-verify-flag-failed`. The Litecoin port note (`litecoin/README.md`) has the file-by-file
  differences, the tests and what was not verified.

## 5. What it would cost on Bitcoin's limits

The first column is arithmetic from Bitcoin's weight rules (constants read from Bitcoin Core at `a527a00`). The middle column is measured on the regtest build
of section 4: a mined one-input spend weighs 4,118 WU (1,030 vB) with a 34-byte output script, of which the
input is 3,904 WU, the figure the arithmetic gave before the build. The last column is the deployed
input, measured at 3,782 bytes, placed under Bitcoin's weight rules.

| | Taproot key path (today) | ML-DSA-44 in the witness (section 4) | ML-DSA-44 outside the witness (as deployed) |
|---|---|---|---|
| Input weight | 230 WU | 3,904 WU | 15,128 WU |
| Input virtual size | 57.5 vB | 976 vB | 3,782 vB |
| Against a Taproot input | 1x | 17x | 66x |
| Inputs in a standard transaction (400,000 WU) | about 1,700 | about 102 | 26 |
| Inputs in a full block (4,000,000 WU) | about 17,400 | about 1,024 | 264 |

Two things follow from the field report's measurements.

1. **Block space is the cost, not validation time.** On my untuned build a post-quantum input takes about 100
   microseconds to verify. A block holding 1,024 of them is about a tenth of a second of signature checking.
   The limit that binds is bytes. Bitcoin would be giving up roughly sixteen-seventeenths of its input capacity
   for any block made only of these.
2. **Consolidation changes shape.** On the deployed chain, merging 6,243 outputs takes three rounds (241, then
   10, then 1 transactions); the first round, which I ran, was 241 transactions and filled 24 blocks. With witness placement the first round is about 62
   transactions and the job takes two rounds in all. That is the difference the witness discount makes, and it is the strongest argument against copying the
   deployed layout.

I have no measurement of the tuned ratio (AVX2 ML-DSA against libsecp256k1 with assembly), and none of fee
behaviour, because the deployed chain has no fee pressure.

## 6. Where this sits beside Bitcoin's own drafts

As I read the public record, BIP-360 began in September 2024 as "pay to quantum resistant hash" (P2QRH): a new
output type committing to post-quantum keys, with the signature schemes named in the same document. In 2025 its
authors changed course. Version 0.8.0 (7 July 2025) made the output a Taproot script tree with the key path
removed and moved signature schemes out to opcodes or leaf versions; 0.9.0 (20 July 2025) put it on witness
version 2; 0.10.0 (17 September 2025) renamed it pay-to-tapscript-hash (P2TSH); and 0.11.0 (10 February 2026)
renamed it pay-to-Merkle-root (P2MR), its name today.

So the pattern in this note is close to where Bitcoin started, and it was left for reasons:

- **A script tree keeps multisig, timelocks and every other script feature.** A single key hash keeps none.
  Multisignature custody and Lightning channels are built from them. This is the largest weakness of the deployed pattern and I do not have
  an answer to it.
- **Separating the output type from the scheme lets each be reviewed alone.** A key-hash type forces the
  choice of scheme into the same decision.
- **One published signature draft for Bitcoin is hash-based.** SHRINCS, which shares an author with BIP-360,
  argues for hash-based signatures because they rest on older, better-studied assumptions than lattice schemes.
  BIP-360 itself names ML-DSA and SLH-DSA
  as examples and chooses neither.

What a simple key-hash type would still offer:

- **It is small to specify and to review.** One template, one check, fixed sizes. The deployed version's
  script path has had no defect found in eight weeks of use, almost all of it my own traffic, and about two and a half weeks of outside review. That is weak evidence (field report, section 7, point 1); a fixed shape is at least
  easy to test exhaustively.
- **It can sit inside the script-tree design instead of beside it.** The same check could be an opcode in a
  pay-to-Merkle-root leaf: `<key hash> OP_CHECKPQSIG`-style, with the key blob and signature in the witness.
  Then the script tree keeps its features and the commitment format, signed message, context string and test
  vectors carry over unchanged. If I were contributing to Bitcoin's work this is where I would aim, not at a
  separate output type. One constraint from the current text: since version 0.12.0 (18 June 2026) BIP-360 makes a
  depth-zero script tree anyone-can-spend and encourages trees of depth 1 or more, so such a leaf would be one of
  at least two, not the whole tree.

**Marscoin has built the same output form, with a hash-based scheme.** Marscoin's repository
(`github.com/marscoin/marscoin`, read 16 November 2026) adds `OP_2 <32-byte hash>` as witness version 2, which it calls
P2WPQH: branch `feat/pq-witness-v2`, commit `8843ef7`, 19 April 2026, merged the same day into its integration
branch `feature/quantum-upgrade` (head `a0fad48`, dated 12 October 2026). The program is
`SHA256(parameter-set id || public key)` and the witness is three items: signature payload, parameter-set id,
key. The scheme is SLH-DSA-SHA2-128s, a 32-byte key and a 7,856-byte signature. In October 2026 it moved from
round-3 SPHINCS+ to FIPS 205 (PR 61), the signed message was completed to a BIP-341-shaped one under its own tag
(PR 64), and the type got its own activation height (PR 69). By its code and documents it is active on regtest
and on a public test network, set to height 0 (off) on mainnet, and absent from the release
branch `28.x` and release 28.1.4. I read the code and documents and did not connect to the network.

It differs from the build in section 4 in signature family and sizes: hash-based, with a 32-byte key and a
7,856-byte signature, against lattice, with 1,312 and 2,420 bytes. It signs hedged by default and accepts all
seven BIP-341 hash types, where the section 4 build signs deterministically and accepts SIGHASH_DEFAULT only,
and it activates by buried height, not a BIP-9 deployment. It has wallet support (addresses, descriptors,
seed-derived keys) and the section 4 build has none; the section 4 build has a two-node soft-fork test and I
found none there. Its tree also carries wallet-migration documents that I saw by title only and have not read.

## 7. Migration, from having done one

These points do not depend on the output type.

1. **A new type protects only the coins moved into it.** On the deployed chain, eight weeks after activation,
   outside parties had made 0.02% of post-quantum spends. Post-quantum addresses became the default for
   receiving, change and sweeps in the desktop and light wallets on 28 September 2026, twelve days after
   activation; the node's own wallet still defaults to classic addresses. On a chain with very few outside
   users, that is all the uptake there was; it is one weak data point for the premise that voluntary migration
   is slow. For Bitcoin, BIP-361 itself says over 34% of the supply is on keys that are already public, as of
   1 March 2026. Chaincode Labs' 2025 survey gives the range of published estimates as about 25% to upwards of
   50% of the supply, with about 30% (6.26 million BTC) as a more precise figure for coins immediately vulnerable. What to do about coins that never move is the subject of
   BIP-361, and nothing in this note helps with it. Its second phase (Phase B, two years after Phase A and five
   years after activation) is a restriction with a rescue path, not a plain freeze: spends with the old
   signatures would have to satisfy a quantum-safe rescue protocol, and coins whose owners never act become
   unspendable.
2. **Decide where change goes, once.** A wallet that spends post-quantum coins and returns change to a
   classic key undoes the migration silently. I fixed this in one place and found it in two more five weeks
   later.
3. **Backups made before the new keys exist do not cover them** unless the keys derive from the existing seed.
   Derive them from the seed.
4. **Search for every assumed input size.** Dust, fee estimation and coin selection all carried the classic
   size. The fix had to reach wallets before nodes.
5. **Wallets need a consolidation tool on the first day.** A wallet that receives many small payments cannot
   make a large one, because a transaction holds so few inputs. On the deployed chain a wallet holding about 2.1
   million coins in 6,511 outputs could pay about 49,000 in one transaction (my own wallet; the figures are on the
   chain, field report, section 5).
6. **The channel that tells light wallets about the change is part of the change.** It needs a signature
   check and pinned keys before activation, not after.
7. **The worst defect was in code nobody had touched.** Review the unmodified parts that the new type leans on.
8. **A conversion wallet is a piece of work in its own right.** Section 8.

## 8. The Blazecoin Quantum Bridge: migration as a conversion wallet

The staged wallet idea is a common way to think about a migration: keep the old wallet, ship a bridging one, then a
fully post-quantum one. The stages are real, but they are stages of **coins**, not of software. They hold on
any chain whose outputs commit to keys by hash, however the new type is added; the chain where this ran added
it by hard fork. There is one chain and one UTXO (unspent transaction output) set, and every coin is in one of three states:

| State | What it means | Exposure |
|---|---|---|
| **Exposed** | the public key is already on the chain: pay-to-public-key outputs, any address that has been spent from, and every Taproot output, which puts the key in the scriptPubKey by design | attackable whenever a capable machine exists |
| **Hash-safe** | the output commits to its key or script only by a hash, and the address has never been spent from: P2PKH, P2WPKH, P2SH or P2WSH | safe until spent and buried; from the moment the spend is broadcast until it is buried under enough blocks to outlast a reorganisation, the key is public |
| **Post-quantum** | the new output type | safe at rest and at spending time |

The state belongs to the key, not the coin. A key revealed in a pay-to-public-key output, on a fork chain that
shares the same keys, in a signed message or through a shared extended public key is exposed although the
address has never spent on this chain. A wallet can see the first of these and can only ask about the rest.

A "V1.5" wallet, read this way, is one that moves coins from the first state to the second today and from the
second to the third once the type exists. The first move needs no consensus change. I call the whole pattern, the three states and the wallet that carries coins across them, the
Blazecoin Quantum Bridge, after the chain where I ran the migration. The word is the everyday one, a way across:
there is one chain throughout, and nothing here is a bridge between chains. The rest of this section says
"the Bridge".

**Five jobs, and what exists of each.** Status on Blazecoin mainnet as of 16 November 2026. The versions and
dates are on the wallet's public release pages (`github.com/AMA-CSharp-Code/blazecoin-wallet/releases`), whose notes
describe each feature (the 400-input batch size and the Berkeley DB version detail are from the code, not the notes); the light wallet 1.3.0 date and the mainnet uses are my own records:

| Job | Built | Where and when | Used on mainnet | Measured |
|---|---|---|---|---|
| 1. Triage | Yes | Desktop wallet 2.0.3, 12 September 2026, with two states (exposed, unexposed) per funded address, read from the wallet's own spends; three states from 2.0.5, 15 September 2026 | Yes, on my own wallets | Not across the chain, and not its effect on other users |
| 2. Hygiene sweep | Yes | The same 2.0.3 release: an exposed address's coins to a fresh classic address, in batches of up to 400 inputs | An exposed address of my own was swept to a fresh address on mainnet on 14 September 2026 (my own record, which does not say which tool sent it) | No |
| 3. Migration sweep | Yes | "Move to post-quantum" in desktop 2.0.9 and light wallet 1.3.0, 28 September 2026. A separate Consolidate tool in desktop 2.0.22, 12 November 2026 | Yes: the treasury moved behind post-quantum addresses on 28 September 2026 | Only through the Consolidate tool's 241-transaction run. That run merged outputs that were already post-quantum, so it measures what a sweep costs in transactions and block space, not a migration of classic coins. No fee-market scheduling exists |
| 4. Receive-only custody | No, not as a product | Building blocks in the node: a public-key-only descriptor, a locked wallet that recognises its coins, and coinbases paid to a pre-generated address list without signing | No | No |
| 5. Import, and both signing paths | Yes | Desktop 2.0.8, built 23 September and released 24 September 2026: Berkeley DB header normalisation from version 10 to 9 ahead of Core 28's migration; verified on a wallet file from the 2014 release line. The node signs both output types | Yes | No |

**The three states, counted.** Applied to every unspent output on Blazecoin at block 4,320,675 (9 October 2026,
the latest height in the copy of the index I could run it on, 23 days after activation), the triage rule gives:

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
bound and the hash-safe share an upper bound, because a key revealed off the chain cannot be seen. And it is one
index at one height; the query is `toolkit/queries/coin_states.sql`.

1. *Triage.* Show the owner which of their coins are in which state. I shipped this before my activation as a
   wallet page (desktop 2.0.3, 12 September 2026). That version sorted each funded address into exposed or
   unexposed by reading the keys revealed in the wallet's own spends, and named the risk; the post-quantum state
   was added in 2.0.5, three days later and still before activation. On Bitcoin,
   BitGo announced exposure scoring for its institutional custody clients on 9 July 2026 and has run a free
   public address checker since August 2026 (its own page: bitgo.com/btc-quantum-resistance-score/; dates from
   news coverage). I have not seen it in ordinary wallets. The toolkit carries the same job for Bitcoin and Blazecoin as an open watch-only script
   (`toolkit/triage/pq_triage.py`): addresses, an extended public key or a descriptor in, the three states out,
   read from any Esplora explorer for Bitcoin or from the project's indexer for Blazecoin, no key involved. Run against the block-1 coinbase
   (pay-to-public-key) it says what one would hope: exposed. It has a limit: on Bitcoin the script cannot see a
   key revealed only in a pay-to-public-key output when asked about the matching address, because explorers do
   not index those outputs by address.
2. *The hygiene sweep, available on Bitcoin now.* Move exposed coins to fresh hash-committed addresses. It is
   cheap and needs no new rules. My desktop wallet has shipped it since 2.0.3: the exposure page offers to sweep
   an exposed address to a fresh one, and since 2.0.9 it offers a classic destination only for exposed coins.
   What has not been measured is whether it moves other people's coins. BitGo is reported to offer this to
   institutions (named the "Fix Exposed Addresses Workflow" in coverage of BitGo's 9 July 2026 announcement); I
   have not found it in Bitcoin consumer wallets. The awkward part is the message: a Taproot-first wallet would be asking users
   to move coins back to a 2017 output type.
3. *The migration sweep, after the fork.* Move hash-safe coins into the new type. My wallets do this with
   "Move to post-quantum" (desktop 2.0.9 and light wallet 1.3.0), in batches of up to 400 classic inputs. On a
   chain with fees it has to be more: rounds, fee-aware, block-space-aware. At the sizes in section 5 (about
   976 vB per input in the witness) a wallet of many small outputs is a fee-market problem, so the tool has to
   schedule, not just batch; mine only batches, because my chain has no fee pressure. The closest measurement I
   have is from the consolidation tool of section 7, point 5, which merges outputs that are already
   post-quantum: the first round of one wallet took 241 transactions and 24 consecutive full blocks. That is
   the cost of spending post-quantum inputs in bulk, which every later move of those coins will pay, and not a
   measurement of moving classic coins in; the field report, section 5, has the figures.
4. *Split custody while hardware catches up.* Hardware support for ML-DSA signing is at best rare today; I have
   not surveyed it. The conclusion I have usually seen drawn is that migration must wait for it. It need not. The reason is an old
   one, the same that lets a watch-only wallet receive to cold keys, but I have not seen its consequence for
   post-quantum migration drawn (below). This job is a proposal: I have not built it as a product, and the
   table above lists the pieces of it that exist in the node.
5. *Import the old wallet, and keep the old signing code.* Old coins arrive as a Berkeley DB `wallet.dat`, a seed
   phrase, a descriptor, loose private keys or a hardware device, and the new wallet must take every form and
   then sign every old output type to move them. So a "fully post-quantum" wallet is a misnomer until a cut-off
   makes old outputs unspendable: the new wallet is a superset of the old one for as long as old coins can move.
   Mine imports the 2014 line's `wallet.dat` through Core 28's read-only Berkeley DB migration, which took a
   header rewrite to accept files written by a newer BDB, and it signs both output types today. One pitfall is
   specific to import: a pre-HD wallet is a bag of unrelated keys with no seed, so the post-quantum keys made for
   it are new secrets that need a new backup, and the wallet has to demand that backup before the first
   post-quantum receive. Mine meets that requirement this way: an imported wallet gets no post-quantum keys in
   place; the desktop wallet sends the user to "Create a post-quantum wallet", which takes a backup as part of
   creating it, and requires a backup acknowledgement before any move to a post-quantum address. (The node can
   also add a post-quantum chain to an existing wallet from a fresh random seed; I did that for two pool wallets
   and took new backups by hand.) Point 3 of section 7 only helps when there is a seed to derive from.

**Migration is receive-only.** To move a coin into a post-quantum output you need to sign with the *old* key
and to know the *new public* key. The new secret key is not needed until the coin is spent again, which may be
years later. So a conversion wallet can let the existing hardware device sign the old spends, derive the
post-quantum keys from a seed that stays offline, keep only the public keys online, and never hold a
post-quantum secret on a networked machine. Point 3 of section 7, derive the new keys from the existing seed,
is what makes the offline derivation a one-time act rather than a new backup. (Related, and earlier: Project
Eleven's yellowpages, from 2025, is a directory holding a proof that links an existing Bitcoin address to new
post-quantum addresses, as evidence of ownership if the old keys ever fail. By its own description it needs no
on-chain transaction; the proof is made inside a trusted execution environment and stored in the company's
database, so it rests on that enclave and that service. The point here is the on-chain version.)

This needs the device, or an offline machine holding the seed, to run ML-DSA key generation once. Typing a
hardware wallet's seed into another machine gives up what the device protects, so in practice this waits for
key-generation firmware, which I expect is a smaller step than signing firmware, or uses a separate seed with its own
backup.

**What is claimed, and what is not.** The single pieces exist elsewhere: an exposure checker (BitGo, by its own page), an
institutional hygiene sweep (BitGo, as reported in news coverage), an off-chain ownership registry (Project
Eleven), consensus proposals for the new type (BIP-360) and the sunset (BIP-361), and
post-quantum wallet work on Marscoin's development branch, which I have not read in full (section 6). A chain
that carried inherited Bitcoin outputs under post-quantum signatures also existed earlier (Bitcoin Post-Quantum,
2018 to 2019; comparison document, section 9). Its whitepaper gives the user's side in a few lines (make a new key,
enter the old keys into the wallet, move the coins) and a rule that coins not moved about a year after launch would
be burned; I have not examined its wallet software. The claim here has three parts. A definition: the Blazecoin Quantum Bridge is the wallet-side migration pattern made
of the three coin states, the five jobs and the move-exposed-first rule. A status, as of 16 November 2026, on
Blazecoin mainnet: triage, the hygiene sweep, the migration sweep and old-wallet import with both signing paths
are shipped and have been used on mainnet, mostly with my own funds (for the hygiene sweep, a sweep was made on
mainnet but my record does not say the wallet tool sent it); receive-only custody is a proposal with its
building blocks in the node; and the effect of any of it on other users has not been measured. And a search
result: I have not found these parts described together as one wallet pattern with a post-quantum output type
validating beneath it. That is a statement about my search, to my knowledge and no more, not a claim of
priority.

**Two things my chain measured that bear on the policy.**

- Outside parties made 0.02% of post-quantum spends in eight weeks (field report, section 6), with the new type
  the default for receiving, change and sweeps in the desktop and light wallets from 28 September 2026, twelve
  days after activation (the node's own wallet still defaults to classic addresses). On this chain, availability
  alone moved almost no outside coins; the chain is too small to say more. The tool that says "these coins are
  exposed; move them" shipped in my desktop wallet on 12 September 2026. What has not been done is measuring its
  effect on users other than me, and that is the obvious experiment.
- The sweep is the expensive part, and on Bitcoin it is seventeen times as expensive per input as today's
  cheapest spend.

My opinion from those two measurements, and it is an opinion: a wallet should move exposed coins first and at
once, leave hash-safe coins where they are until they next move anyway, and send them to the new type then.
Spending is when the wallet already has the user's attention and a fee budget. The argument against is a
strong one: a hash-safe coin is safe only until it is spent, and once a capable attacker exists it cannot be
spent safely at all, because the spend reveals the key before it is buried. An owner who waits for the next
natural spend is betting that it comes before such an attacker does. Someone who weighs that risk more heavily
should move hash-safe coins early and pay the block space.

**What this does not reach.** A coin whose owner is gone has no one to sign the old spend. Section 7, point 1,
and BIP-361 are about those coins; no wallet is.

## 9. Activation

I have nothing to offer here. My activation was a flag height on a network I operate. Bitcoin's would need a
soft-fork deployment with miner signalling, years of review, and agreement that the field report cannot
supply. The one transferable point is small: activate by height, not by date. My predicted date was 15 hours
out and it did not matter.

## 10. Limits

- Section 4 is a regtest build. It has not been run on a test network or reviewed by anyone.
- Section 5's witness column comes from that regtest build: one transaction shape, no fee market. Its Taproot
  column is arithmetic.
- Everything measured comes from one operator, one small chain and eight weeks.
- I have not compared ML-DSA with the hash-based schemes, and I make
  no claim that it is the better choice for Bitcoin.
- Witness version 2 with a 32-byte program is BIP-360's template; the section 4 build uses it as a placeholder.
- A key-hash type without script composition is weaker than pay-to-Merkle-root for most real users.
- The Bridge of section 8 should carry to any UTXO chain whose outputs commit to keys by hash; I have run it only
  on Blazecoin, and the triage script on Bitcoin. It
  does not carry to account chains or to chains whose outputs carry public keys; those need different treatment
  and are out of scope.
- Of the Bridge's five jobs, four are shipped and one (receive-only custody) is a proposal. None has been
  measured for its effect on users other than me.
- The BIP-360 history in section 6 rests on the BIP's changelog alone; no discussion thread is cited for it.

## 11. What I would do next, if this is worth pursuing

1. Take the section 4 build from regtest to a test network, and publish its vectors.
2. Build the same check as a leaf opcode on a pay-to-Merkle-root test branch, and compare the two.
3. Measure tuned verification on Linux, both schemes with their assembly paths.
4. Ask the BIP-360 authors whether measurements from a deployed key-hash type are any use to them before
   doing any of it.
5. Measure the three-state triage of section 8 (`toolkit/triage/`, the one piece that needs no soft fork) on
   users other than me: it is in my desktop wallet already, and I have not measured whether telling people which
   coins are exposed moves more coins than making a new type the default did.

## References

- The field report this note accompanies: [REPORT.md](REPORT.md).
- NIST. FIPS 204, Module-Lattice-Based Digital Signature Standard. https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.204.pdf.
  2024-08-13. Read 2026-11-17 (Table 2 and section 3.4).
- NIST. FIPS 205, Stateless Hash-Based Digital Signature Standard. https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.205.pdf.
  2024-08-13. Read 2026-11-17 (Table 2).
- Wuille, Todd, Maxwell, Russell. BIP-9, Version bits with timeout and delay. https://github.com/bitcoin/bips/blob/master/bip-0009.mediawiki. Deployed. Assigned 2015-10-04. Header read 2026-11-17.
- Lombrozo, Lau, Wuille. BIP-141, Segregated Witness (Consensus layer). https://github.com/bitcoin/bips/blob/master/bip-0141.mediawiki. Deployed. Assigned 2015-12-21. Header read 2026-11-17.
- Lau, Wuille. BIP-143, Transaction Signature Verification for Version 0 Witness Program. https://github.com/bitcoin/bips/blob/master/bip-0143.mediawiki. Deployed. Assigned 2016-01-03. Header read 2026-11-17.
- Wuille, Nick, Towns. BIP-341, Taproot: SegWit version 1 spending rules. https://github.com/bitcoin/bips/blob/master/bip-0341.mediawiki. Deployed. Assigned 2020-01-19. Header read 2026-11-17.
- Wuille, Nick, Towns. BIP-342, Validation of Taproot Scripts. https://github.com/bitcoin/bips/blob/master/bip-0342.mediawiki. Deployed. Assigned 2020-01-19. Header read 2026-11-17.
- Wuille. BIP-350, Bech32m format for v1+ witness addresses. https://github.com/bitcoin/bips/blob/master/bip-0350.mediawiki. Deployed. Assigned 2020-12-16. Header read 2026-11-17.
- Hunter Beast, Ethan Heilman, Isabel Foxen Duke. BIP-360, Pay-to-Merkle-Root.
  https://github.com/bitcoin/bips/blob/master/bip-0360.mediawiki. Draft, version 0.12.1 (2026-07-24), file commit
  `e7263a4` (2026-08-03), and its changelog for the earlier pay-to-quantum-resistant-hash revisions; the
  history in section 6 is taken from that changelog. Read 2026-11-16.
- Jameson Lopp, Christian Papathanasiou, Ian Smith, Joe Ross, Steve Vaile, Pierre-Luc Dallaire-Demers. BIP-361,
  Post Quantum Migration and Legacy Signature Sunset. https://github.com/bitcoin/bips/blob/master/bip-0361.mediawiki.
  Draft, file commit `da7cc67` (2026-04-17). Read 2026-11-16 and 2026-11-17.
- conduition, Heilman, Kudinov, Kurbatov, Nick, remix7531. SHRINCS: A Compact Hash-Based Signature Scheme.
  https://github.com/SHRINCS/shrincs-bip/blob/main/SHRINCS.md. Draft, no BIP number, commit `990cd1f` (2026-11-09).
  Read 2026-11-17.
- Marscoin, `github.com/marscoin/marscoin`, branches `feat/pq-witness-v2` (commit `8843ef7`) and
  `feature/quantum-upgrade` (head `a0fad48`, 2026-10-12): `src/script/interpreter.cpp`, `src/consensus/params.h`,
  `doc/quantum-p2wpqh-sighash-v1.md`, `doc/quantum-signatures-sphincs-v1.md`. Read 2026-11-16.
- The Litecoin port note (`litecoin/README.md`).
- The comparison document (`DESIGN-COMPARISON.md`) and the defect list (`DEFECTS.md`), in the same repository.
- Bitcoin Core. https://github.com/bitcoin/bitcoin. Master at commit `a527a00`, 2026-11-13 (the base of the
  section 4 patch; the constants of section 5 were read from it on 2026-11-17).
- Litecoin Core. https://github.com/litecoin-project/litecoin. v0.21.5.8, tag commit `ec1b6489`, released
  2026-09-12 (the base of the Litecoin port).
- BitGo. Bitcoin quantum resistance score (public address checker). https://www.bitgo.com/btc-quantum-resistance-score/.
  Dates and the institutional workflow are from news coverage:
  https://bitcoinmagazine.com/news/bitgo-adds-quantum-risk-controls-bitcoin and
  https://thepaypers.com/crypto-web3-and-cbdc/news/bitgo-launches-public-bitcoin-quantum-risk-checker.
  Read 2026-11-17.
- Project Eleven. yellowpages. First-party sources read 2026-11-17: the client repository
  https://github.com/p-11/yellowpages-client (commit `4b6cef3e`, 2026-03-19; its FAQ page `src/app/faqs/page.tsx`) and
  the proof service https://github.com/p-11/yellowpages-proof-service (commit `0485a71f`, 2026-03-19; README, marked
  archived). The announcement posts https://www.projecteleven.com/blog/hello-yellowpages and
  https://www.projecteleven.com/blog/the-trust-model-of-yellowpages-v1 were read on 2026-11-13 and refuse automated
  fetches.
- Blockstream. Esplora, the block explorer API the triage script reads, as served by blockstream.info and
  mempool.space.
- Milton, A. and Shikhelman, C. (Chaincode Labs). Bitcoin and Quantum Computing: Current Status and Future
  Directions. https://chaincode.com/bitcoin-post-quantum.pdf. 2025-05. Read 2026-11-17.
- Anhao, N. Bitcoin Post-Quantum (whitepaper). https://bitcoinpq.org/download/bitcoinpq-whitepaper-english.pdf. Undated (2018).
  Project site https://bitcoinpq.org/ ; node https://github.com/bitcoinpostquantum/bitcoinpq, last commit `28a1f3c`
  (2019-10-23): `src/chainparams.cpp` (`BPQHeight = 555000`, checkpoints at 555,100 and 600,000),
  `src/script/interpreter.cpp`. Read 2026-11-17.
