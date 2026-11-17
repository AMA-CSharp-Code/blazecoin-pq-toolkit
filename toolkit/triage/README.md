# pq_triage: which of your coins are exposed

The first job of the Blazecoin Quantum Bridge (BITCOIN-PORTING-NOTE.md, section 8) as a watch-only tool. For Bitcoin, a more careful classification exists as a draft with its own reference implementation and test vectors: `github.com/duncan0k/pubkey-exposure-classification` (BIPs pull request 2294). It has four levels and assigns the more exposed level when the data cannot tell two apart; this script has three states and no such rule. Prefer that draft's rules where the two differ. Give it
addresses, an extended public key or a descriptor; it tells you which coins a quantum attacker could take at any
time, which are safe until you next spend them, and which are already post-quantum. One file, standard library
only, no private key anywhere near it. Works on Bitcoin (any Esplora API: blockstream.info, mempool.space or your
own) and on Blazecoin (the project's block indexer). It walks descriptors and extended public keys and covers
Blazecoin's post-quantum outputs.

```
python pq_triage.py bc1q... 3... 1...
python pq_triage.py --xpub zpub6r...                              # BIP84 account: receive + change, gap limit 20
python pq_triage.py --descriptor "tr(xpub6B.../<0;1>/*)"           # also pkh( wpkh( sh(wpkh(
python pq_triage.py --txo <txid>:<vout>                           # a specific output; the only way to see P2PK
python pq_triage.py --chain blazecoin B... BQ...
python pq_triage.py --chain blazecoin --txo <txid>:<vout>         # outputs work on Blazecoin too
python pq_triage.py --api https://mempool.space/api --json ...    # another explorer; machine-readable output
```

## The three states

| State | Meaning | Rule the tool applies |
|---|---|---|
| **exposed** | the public key is already on the chain; a quantum attacker can take the coin whenever a capable machine exists | pay-to-public-key outputs; Taproot outputs (the key is the output); any address that has ever spent (the spend put the key, or the script and its keys, on the chain) |
| **hash-safe** | the key is committed only by its hash and has never been revealed; safe until spent, and public for as long as the spending transaction waits to be mined | P2PKH, P2WPKH, P2SH or P2WSH at an address that has received and never spent |
| **post-quantum** | the output type is post-quantum | Blazecoin P2PQH, pay to post-quantum key hash (`BQ...`); Bitcoin has no such type yet |

Addresses that were never funded are counted but not listed. A coin already spent shows as `spent`.

## What to do with the answer

Move exposed coins first and at once, to a fresh address (hash-safe) today, or to a post-quantum output where
the chain has one. Leave hash-safe coins where they are until they next move anyway, and send them to a
post-quantum output then: they are not safe for ever, but they are safe until spent, and the spend is when you
have the wallet open and a fee budget. The reasoning and the measurements behind this policy are in the porting
note, section 8.

## Limits, stated plainly

- The state belongs to the key, not the coin, and the tool sees only one chain. A key is exposed wherever it has
  been revealed: by a spend of the same key on a fork chain, in a signed message, or through an extended public
  key that was shared with someone. The tool cannot see any of these, so "hash-safe" here means "not revealed on
  this chain, as far as this explorer shows". If you have used the key in one of those ways, treat it as exposed.
- "Safe until spent" means safe until spent and buried: the key is public from the moment the spend is
  broadcast, and a reorganisation can reopen the window.
- A pay-to-public-key output has no address, so on Bitcoin it cannot be found by address: give it as
  `--txo txid:vout`. For the same reason, on Bitcoin the tool cannot see a key revealed only in a
  pay-to-public-key output when asked about the matching address, because explorers do not index those outputs
  by address: such an address can read as hash-safe although its key is already public. On Blazecoin the project's block indexer files such outputs under the address of their key, so the tool looks
  up the real script type of each unspent output of an address (the first 100) and reports the address as exposed
  when any of them is pay-to-public-key, however the address itself looks. Outputs beyond the first 100 are
  reported as not checked. Blazecoin's early coinbases are of this kind.
- "Has spent" is read from the explorer's per-address counters, including the mempool. An address whose
  only spends are in blocks the explorer has not yet indexed would read as hash-safe; run your own Esplora if that
  matters to you.
- P2SH (pay to script hash) and P2WSH are judged on whether the address has spent; the script inside is not inspected. An unspent
  multisig is hash-safe here even if one of its keys has been revealed elsewhere, which the tool cannot know.
- Taproot outputs whose key path is unspendable (a NUMS (nothing up my sleeve) internal key) are not exposed in the way the table says,
  but nothing on the chain distinguishes them, so they are listed as exposed. Treat that as the conservative
  answer it is.
- Extended-key derivation covers BIP-44 (`xpub`, `pkh(`), BIP-49 (`ypub`, `sh(wpkh(`), BIP-84 (`zpub`, `wpkh(`) and
  BIP-86 (`tr(` with an `xpub`), non-hardened steps only; multi-key descriptors are not supported.
- The addresses you give are sent to the explorer you chose. That is the privacy cost of any watch-only tool.

## Adding a chain or an output type

Both are data. A chain is one entry in `CHAINS`: its unit, its explorer class (`Esplora`, `Indexer`, or your own
subclass of `Backend` with `_address` and, if it can, `txo`), its default API address and its address formats.
An output type is one line in `STATE_RULES`: its state while the address has never spent, and once it has. No
other code changes; the tests add a Litecoin-like chain and a new output type that way.

## Tests

`python test_pq_triage.py -v` (42 tests, no network): the BIP-32, BIP-49, BIP-84, BIP-86, BIP-173 and BIP-350 published
vectors for the derivation and address code; the triage logic against recorded Esplora and Indexer answers; the
state rules as a table; output lookups on both explorers; the command line end to end (table and `--json`, the
address file, the gap-limit walk) with a recorded explorer injected; and that each address is asked for once per
run.

MIT, like the rest of `toolkit/`.
