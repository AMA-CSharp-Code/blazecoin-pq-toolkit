# -*- coding: utf-8 -*-
"""Offline tests for pq_triage: published BIP vectors for the derivation and address code, and the triage logic
against recorded API answers. No network. Run: python -m unittest test_pq_triage -v"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pq_triage as t  # noqa: E402


class AddressEncodings(unittest.TestCase):
    def test_bip173_p2wpkh_and_decode(self):
        # BIP173 example: the P2WPKH of the BIP143 test key
        pk = bytes.fromhex("0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798")
        self.assertEqual(t.address_from_pubkey("bitcoin", "wpkh", pk), "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
        self.assertEqual(t.segwit_decode("BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4"), ("bc", 0, t.hash160(pk)))
        self.assertIsNone(t.segwit_decode("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t5"))  # bad checksum

    def test_bip350_bech32m_p2tr_vector(self):
        self.assertEqual(t.segwit_decode("bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0")[1], 1)
        self.assertIsNone(t.segwit_decode("bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqh2y7hd"))  # bech32 checksum on v1

    def test_classify_by_format(self):
        self.assertEqual(t.classify_address("bitcoin", "12ZEw5Hcv1hTb6YUQJ69y1V7uhcoDz92PH"), ("p2pkh", None))
        self.assertEqual(t.classify_address("bitcoin", "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"), ("p2sh", None))
        self.assertEqual(t.classify_address("bitcoin", "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"), ("v0_p2wpkh", None))
        self.assertEqual(t.classify_address("bitcoin", "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"), ("v1_p2tr", None))
        self.assertEqual(t.classify_address("bitcoin", "bc1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3qccfmv3"), ("v0_p2wsh", None))
        self.assertEqual(t.classify_address("bitcoin", "hello")[0], "unknown")
        self.assertEqual(t.classify_address("blazecoin", "BQHcY1yedCSGvq8KyXTAY4GW3wwaabje8hu72ERZrWpCYZcu8Qrn"), ("pqkh", None))


class Derivation(unittest.TestCase):
    def test_bip32_vector1_public_child(self):
        # BIP32 test vector 1: xpub at m/0H, public child 1 -> xpub at m/0H/1
        parent = "xpub68Gmy5EdvgibQVfPdqkBBCHxA5htiqg55crXYuXoQRKfDBFA1WEjWgP6LHhwBZeNK1VTsfTFUHCdrfp1bgwQ9xv5ski8PX9rL2dZXvgGDnw"
        child = "xpub6ASuArnXKPbfEwhqN6e3mwBcDTgzisQN1wXN9BJcM47sSikHjJf3UFHKkNAWbWMiGj7Wf5uMash7SyYq527Hqck2AxYysAA7xmALppuCkwQ"
        x, _ = t.Xpub.parse(parent, "bitcoin")
        c = x.child(1)
        raw = t.b58check_decode(child)
        self.assertEqual(c.key, raw[45:78])
        self.assertEqual(c.chain_code, raw[13:45])

    def test_bip84_first_address(self):
        zpub = "zpub6rFR7y4Q2AijBEqTUquhVz398htDFrtymD9xYYfG1m4wAcvPhXNfE3EfH1r1ADqtfSdVCToUG868RvUUkgDKf31mGDtKsAYz2oz2AGutZYs"
        x, scheme = t.Xpub.parse(zpub, "bitcoin")
        self.assertEqual(scheme, "wpkh")
        self.assertEqual(t.address_from_pubkey("bitcoin", "wpkh", x.derive([0, 0]).key), "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu")
        self.assertEqual(t.address_from_pubkey("bitcoin", "wpkh", x.derive([1, 0]).key), "bc1q8c6fshw2dlwun7ekn9qwf37cu2rn755upcp6el")

    def test_bip49_first_address(self):
        ypub = "ypub6Ww3ibxVfGzLrAH1PNcjyAWenMTbbAosGNB6VvmSEgytSER9azLDWCxoJwW7Ke7icmizBMXrzBx9979FfaHxHcrArf3zbeJJJUZPf663zsP"
        x, scheme = t.Xpub.parse(ypub, "bitcoin")
        self.assertEqual(scheme, "sh-wpkh")
        self.assertEqual(t.address_from_pubkey("bitcoin", "sh-wpkh", x.derive([0, 0]).key), "37VucYSaXLCAsxYyAPfbSi9eh4iEcbShgf")

    def test_bip86_first_addresses(self):
        xpub = "xpub6BgBgsespWvERF3LHQu6CnqdvfEvtMcQjYrcRzx53QJjSxarj2afYWcLteoGVky7D3UKDP9QyrLprQ3VCECoY49yfdDEHGCtMMj92pReUsQ"
        x, scheme, branches = t.parse_descriptor("tr(%s/<0;1>/*)" % xpub, "bitcoin")
        self.assertEqual(scheme, "tr")
        self.assertEqual(branches, [[0], [1]])
        self.assertEqual(t.address_from_pubkey("bitcoin", "tr", x.derive([0, 0]).key), "bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr")
        self.assertEqual(t.address_from_pubkey("bitcoin", "tr", x.derive([0, 1]).key), "bc1p4qhjn9zdvkux4e44uhx8tc55attvtyu358kutcqkudyccelu0was9fqzwh")
        self.assertEqual(t.address_from_pubkey("bitcoin", "tr", x.derive([1, 0]).key), "bc1p3qkhfews2uk44qtvauqyr2ttdsw7svhkl9nkm9s9c3x4ax5h60wqwruhk7")

    def test_bip44_pkh_descriptor_and_hardened_refused(self):
        xpub = "xpub6BgBgsespWvERF3LHQu6CnqdvfEvtMcQjYrcRzx53QJjSxarj2afYWcLteoGVky7D3UKDP9QyrLprQ3VCECoY49yfdDEHGCtMMj92pReUsQ"
        x, scheme, branches = t.parse_descriptor("pkh(%s/0/*)#abcd1234" % xpub, "bitcoin")
        self.assertEqual((scheme, branches), ("pkh", [[0]]))
        with self.assertRaises(ValueError):
            t.parse_descriptor("wpkh(%s/0'/*)" % xpub, "bitcoin")
        with self.assertRaises(ValueError):
            x.child(0x80000000)


class FakeEsplora(t.Esplora):
    def __init__(self, answers):
        super().__init__("http://fake", pause=0, fetch=lambda path: answers.get(path))


class Triage(unittest.TestCase):
    def test_states_from_recorded_answers(self):
        def addr(funded, spent, bal):
            return {"chain_stats": {"funded_txo_count": funded, "funded_txo_sum": bal, "spent_txo_count": spent, "spent_txo_sum": 0},
                    "mempool_stats": {"funded_txo_count": 0, "funded_txo_sum": 0, "spent_txo_count": 0, "spent_txo_sum": 0}}
        answers = {
            "/address/12ZEw5Hcv1hTb6YUQJ69y1V7uhcoDz92PH": addr(3, 0, 150000),            # funded, never spent
            "/address/12ZEw5Hcv1hTb6YUQJ69y1V7uhcoDz92PH/utxo": "Too many unspent outputs",
            "/address/bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4": addr(3, 2, 1000),             # has spent
            "/address/bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4/utxo": [{"value": 1000}],
            "/address/bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0": addr(1, 0, 5000),  # taproot, unspent
            "/address/bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0/utxo": [{"value": 5000}],
            "/address/3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy": addr(0, 0, 0),                        # never funded
            "/tx/0e3e2357e806b6cdb1f70b54c3a3a17b6714ee1f0e68bebb44a74b1efd512098":
                {"vout": [{"scriptpubkey_type": "p2pk", "value": 5000000000}]},
            "/tx/0e3e2357e806b6cdb1f70b54c3a3a17b6714ee1f0e68bebb44a74b1efd512098/outspend/0": {"spent": False},
        }
        be = FakeEsplora(answers)
        rows = t.triage_addresses("bitcoin", be, [
            ("12ZEw5Hcv1hTb6YUQJ69y1V7uhcoDz92PH", None),
            ("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", None),
            ("bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0", None),
            ("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", None),
            ("not-an-address", None),
        ]) + t.triage_txos(be, ["0e3e2357e806b6cdb1f70b54c3a3a17b6714ee1f0e68bebb44a74b1efd512098:0"])
        by = {r["address"]: r for r in rows}
        self.assertEqual(by["12ZEw5Hcv1hTb6YUQJ69y1V7uhcoDz92PH"]["state"], t.HASH_SAFE)
        self.assertIsNone(by["12ZEw5Hcv1hTb6YUQJ69y1V7uhcoDz92PH"]["utxos"])  # explorer refused the UTXO list
        self.assertEqual(by["bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"]["state"], t.EXPOSED)
        self.assertEqual(by["bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"]["state"], t.EXPOSED)
        self.assertEqual(by["3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"]["state"], "unused")
        self.assertEqual(by["not-an-address"]["state"], t.UNKNOWN)
        p2pk = by["0e3e2357e806b6cdb1f70b54c3a3a17b6714ee1f0e68bebb44a74b1efd512098:0"]
        self.assertEqual((p2pk["type"], p2pk["state"], p2pk["balance"]), ("p2pk", t.EXPOSED, 5000000000))
        tot = t.summarise(rows)
        self.assertEqual(tot[t.EXPOSED]["balance"], 1000 + 5000 + 5000000000)
        self.assertEqual(tot[t.HASH_SAFE]["balance"], 150000)

    def test_blazecoin_indexer_answers(self):
        answers = {
            "/address/BQHcY1yedCSGvq8KyXTAY4GW3wwaabje8hu72ERZrWpCYZcu8Qrn": {"balance": 0, "totalReceived": 10, "totalSent": 10, "txCount": 5762},
            "/address/BQHcY1yedCSGvq8KyXTAY4GW3wwaabje8hu72ERZrWpCYZcu8Qrn/utxos": [],
            "/address/B1111111111111111111111111111111111": {"balance": 500, "totalReceived": 500, "totalSent": 0, "txCount": 1},
            "/address/B1111111111111111111111111111111111/utxos": [{"amount": 500}],
        }
        be = t.Indexer("http://fake", pause=0, fetch=lambda path: answers.get(path))
        pq = t.triage_addresses("blazecoin", be, [("BQHcY1yedCSGvq8KyXTAY4GW3wwaabje8hu72ERZrWpCYZcu8Qrn", None)])[0]
        self.assertEqual(pq["state"], t.POST_QUANTUM)
        self.assertIn("balance is zero", pq["reason"])
        # a classic B... address that has never spent: hash-safe (format check only, the fake address is not valid base58check)
        self.assertEqual(t.state_for("p2pkh", False), (t.HASH_SAFE, "key committed by hash, never revealed"))
        self.assertEqual(t.state_for("p2pkh", True)[0], t.EXPOSED)

    def test_gap_limit_walk(self):
        xpub = "xpub6BgBgsespWvERF3LHQu6CnqdvfEvtMcQjYrcRzx53QJjSxarj2afYWcLteoGVky7D3UKDP9QyrLprQ3VCECoY49yfdDEHGCtMMj92pReUsQ"
        x, scheme, branches = t.parse_descriptor("tr(%s/0/*)" % xpub, "bitcoin")
        first = "bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr"
        out = t.derive_addresses(x, scheme, branches, "bitcoin", gap=3, used=lambda a: a == first)
        self.assertEqual(out[0], (first, "0/0"))
        self.assertEqual(len(out), 4)  # index 0 used, then 3 unused -> stop


def esplora_address(funded, spent, balance):
    return {"chain_stats": {"funded_txo_count": funded, "funded_txo_sum": balance, "spent_txo_count": spent, "spent_txo_sum": 0},
            "mempool_stats": {"funded_txo_count": 0, "funded_txo_sum": 0, "spent_txo_count": 0, "spent_txo_sum": 0}}


class CountingFetch:
    """A fetch function over recorded answers that counts how often each path is asked for."""

    def __init__(self, answers):
        self.answers, self.calls = answers, {}

    def __call__(self, path):
        self.calls[path] = self.calls.get(path, 0) + 1
        return self.answers.get(path)


class ChainIsOneEntry(unittest.TestCase):
    """A chain is one CHAINS entry: its unit, its explorer type and its address formats. Nothing else changes."""

    def setUp(self):
        t.CHAINS["litecoin-like"] = dict(unit="LTC", backend=t.Esplora, api="https://ltc.example/api",
                                         classify=t.classify_segwit_base58, hrp="ltc", p2pkh=0x30, p2sh=0x32,
                                         xpub_versions={})
        self.addCleanup(t.CHAINS.pop, "litecoin-like")
        self.h20 = t.hash160(b"some key")

    def test_new_chain_classifies_formats_and_builds_its_backend(self):
        p2pkh = t.b58check_encode(bytes([0x30]) + self.h20)
        p2sh = t.b58check_encode(bytes([0x32]) + self.h20)
        wpkh = t.segwit_encode("ltc", 0, self.h20)
        tr = t.segwit_encode("ltc", 1, bytes(32))
        self.assertTrue(p2pkh.startswith("L"))
        self.assertEqual(t.classify_address("litecoin-like", p2pkh), ("p2pkh", None))
        self.assertEqual(t.classify_address("litecoin-like", p2sh), ("p2sh", None))
        self.assertEqual(t.classify_address("litecoin-like", wpkh), ("v0_p2wpkh", None))
        self.assertEqual(t.classify_address("litecoin-like", tr), ("v1_p2tr", None))
        # a Bitcoin address is not an address of this chain, in either encoding
        self.assertEqual(t.classify_address("litecoin-like", "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"), ("unknown", "wrong network prefix"))
        self.assertEqual(t.classify_address("litecoin-like", "12ZEw5Hcv1hTb6YUQJ69y1V7uhcoDz92PH")[0], "unknown")
        self.assertEqual(t.fmt_amount(150000000, "litecoin-like"), "1.50000000 LTC")
        be = t.make_backend("litecoin-like")
        self.assertIsInstance(be, t.Esplora)
        self.assertEqual(be.base, "https://ltc.example/api")
        self.assertEqual(t.make_backend("litecoin-like", "http://own/api/", 0).base, "http://own/api")
        self.assertIn("litecoin-like", t.build_parser().parse_args(["--chain", "litecoin-like", "x"]).chain)

    def test_new_chain_runs_through_the_triage(self):
        addr = t.segwit_encode("ltc", 0, self.h20)
        be = t.Esplora("http://fake", pause=0, fetch=lambda p: {"/address/" + addr: esplora_address(1, 0, 700),
                                                             "/address/" + addr + "/utxo": [{"value": 700}]}.get(p))
        row = t.triage_addresses("litecoin-like", be, [(addr, None)])[0]
        self.assertEqual((row["type"], row["state"], row["balance"], row["utxos"]), ("v0_p2wpkh", t.HASH_SAFE, 700, 1))

    def test_built_in_chains_each_name_their_unit_backend_and_classifier(self):
        for name, c in t.CHAINS.items():
            self.assertTrue(issubclass(c["backend"], t.Backend), name)
            self.assertTrue(callable(c["classify"]), name)
            self.assertIn(c["unit"], ("BTC", "BLZ", "LTC"), name)
        self.assertIsInstance(t.make_backend("bitcoin"), t.Esplora)
        self.assertIsInstance(t.make_backend("blazecoin"), t.Indexer)
        self.assertEqual(t.fmt_amount(1, "bitcoin"), "0.00000001 BTC")
        self.assertEqual(t.fmt_amount(41300000000, "blazecoin"), "413.00000000 BLZ")

    def test_blazecoin_classifier(self):
        classic = t.b58check_encode(bytes([0x1A]) + self.h20)
        self.assertTrue(classic.startswith("B"))
        self.assertEqual(t.classify_address("blazecoin", classic), ("p2pkh", None))
        self.assertEqual(t.classify_address("blazecoin", t.b58check_encode(bytes([0x05]) + self.h20)), ("p2sh", None))
        # 25 was the byte this table wrongly held until 2026-11-16: no Blazecoin address has it
        self.assertEqual(t.classify_address("blazecoin", t.b58check_encode(bytes([0x19]) + self.h20)), ("unknown", "unrecognised version byte"))
        self.assertEqual(t.classify_address("blazecoin", t.b58check_encode(bytes([0x00]) + self.h20)), ("unknown", "unrecognised version byte"))
        self.assertEqual(t.classify_address("blazecoin", "nonsense"), ("unknown", "not a Blazecoin address"))
        # Blazecoin has no bech32 prefix: a witness address is simply not an address there
        self.assertEqual(t.classify_address("blazecoin", "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")[0], "unknown")


class StateRulesAreData(unittest.TestCase):
    def test_every_rule_round_trips(self):
        for stype, (unspent, spent) in t.STATE_RULES.items():
            self.assertEqual(t.state_for(stype, False), unspent, stype)
            self.assertEqual(t.state_for(stype, True), spent, stype)
            self.assertIn(unspent[0], (t.EXPOSED, t.HASH_SAFE, t.POST_QUANTUM), stype)
            self.assertEqual(t.depends_on_spend_history(stype), unspent != spent, stype)

    def test_the_rules_say_what_the_paper_says(self):
        self.assertEqual(t.state_for("pqkh", True)[0], t.POST_QUANTUM)        # post-quantum stays so after a spend
        self.assertEqual(t.state_for("p2pk", False)[0], t.EXPOSED)            # the key is the output
        self.assertEqual(t.state_for("v1_p2tr", False)[0], t.EXPOSED)
        for hashed in ("p2pkh", "v0_p2wpkh", "p2sh", "v0_p2wsh"):
            self.assertEqual(t.state_for(hashed, False)[0], t.HASH_SAFE, hashed)
            self.assertEqual(t.state_for(hashed, True)[0], t.EXPOSED, hashed)
            self.assertTrue(t.depends_on_spend_history(hashed))
        self.assertEqual(t.state_for("multisig", False), (t.UNKNOWN, "unrecognised output type"))
        self.assertFalse(t.depends_on_spend_history("multisig"))

    def test_a_new_output_type_is_one_line_of_data(self):
        t.STATE_RULES["v2_pq"] = ((t.POST_QUANTUM, "post-quantum witness program"),) * 2
        self.addCleanup(t.STATE_RULES.pop, "v2_pq")
        self.assertEqual(t.state_for("v2_pq", True), (t.POST_QUANTUM, "post-quantum witness program"))
        answers = {"/tx/aa": {"vout": [{"scriptpubkey_type": "v2_pq", "value": 9}]}, "/tx/aa/outspend/0": {"spent": False}}
        row = t.triage_txos(FakeEsplora(answers), ["aa:0"])[0]
        self.assertEqual((row["type"], row["state"], row["balance"]), ("v2_pq", t.POST_QUANTUM, 9))


class OutputLookups(unittest.TestCase):
    TXID = "5f" * 32
    PQ_ADDR = "BQHcY1yedCSGvq8KyXTAY4GW3wwaabje8hu72ERZrWpCYZcu8Qrn"

    def detail(self):
        # shaped like the Indexer's TransactionDetailDto (api/tx/{txId}/detail), camelCase as ASP.NET serialises it
        return {"txId": self.TXID, "blockHeight": 4431506, "blockHash": "00" * 32, "index": 1, "timestamp": 1794793272,
                "fee": 0, "sizeBytes": 3900, "totalInput": 1300, "totalOutput": 1300, "isCoinbase": False,
                "inputs": [{"prevTxId": "11" * 32, "prevOutputIndex": 0, "address": self.PQ_ADDR, "amount": 1300, "isCoinbase": False}],
                "outputs": [
                    {"index": 0, "address": self.PQ_ADDR, "amount": 1000, "scriptType": "pqkh", "isSpent": False, "spentByTxId": None},
                    {"index": 1, "address": "Bclassic", "amount": 200, "scriptType": "pubkeyhash", "isSpent": False, "spentByTxId": None},
                    {"index": 2, "address": "Bgone", "amount": 100, "scriptType": "pubkeyhash", "isSpent": True, "spentByTxId": "22" * 32},
                    {"index": 3, "address": "", "amount": 0, "scriptType": "nulldata", "isSpent": False, "spentByTxId": None},
                ]}

    def indexer(self, extra=None):
        answers = {"/tx/" + self.TXID + "/detail": self.detail()}
        answers.update(extra or {})
        return t.Indexer("http://fake", pause=0, fetch=lambda p: answers.get(p))

    def test_indexer_finds_an_output_that_exists(self):
        be = self.indexer()
        self.assertEqual(be.txo(self.TXID, 0), dict(type="pqkh", address=self.PQ_ADDR, value=1000, spent=False))
        self.assertEqual(be.txo(self.TXID, 1), dict(type="p2pkh", address="Bclassic", value=200, spent=False))
        self.assertTrue(be.txo(self.TXID, 2)["spent"])
        self.assertEqual(be.txo(self.TXID, 3)["type"], "nulldata")     # an unmapped type keeps the node's name
        self.assertIsNone(be.txo(self.TXID, 3)["address"])
        self.assertIsNone(be.txo(self.TXID, 9))                        # no such output index
        self.assertIsNone(be.txo("ee" * 32, 0))                        # no such transaction

    def test_indexer_outputs_through_the_triage(self):
        be = self.indexer({"/address/Bclassic": {"balance": 200, "totalReceived": 900, "totalSent": 700, "txCount": 4},
                           "/address/Bclassic/utxos": [{"amount": 200}]})
        rows = t.triage_txos(be, [self.TXID + ":0", self.TXID + ":1", self.TXID + ":2", self.TXID + ":3", self.TXID + ":9"])
        got = [(r["type"], r["state"]) for r in rows]
        self.assertEqual(got, [("pqkh", t.POST_QUANTUM),      # post-quantum output
                               ("p2pkh", t.EXPOSED),           # unspent, but its address has sent before
                               ("p2pkh", "spent"),
                               ("nulldata", t.UNKNOWN),
                               ("unknown", t.UNKNOWN)])
        self.assertEqual(rows[0]["balance"], 1000)
        self.assertEqual(rows[4]["reason"], "output not found")
        self.assertIn("address has spent before", rows[1]["reason"])

    def test_every_indexer_type_name_maps_to_a_rule(self):
        for node_name, rule_name in t.Indexer.SCRIPT_TYPES.items():
            self.assertIn(rule_name, t.STATE_RULES, node_name)

    def test_a_backend_without_output_lookup_says_so(self):
        class AddressOnly(t.Backend):
            def _address(self, addr):
                return dict(has_funded=False, has_spent=False, balance=0, utxos=0, funded=0)

        be = AddressOnly("http://fake", pause=0, fetch=lambda p: None)
        with self.assertRaises(t.LookupNotSupported):
            be.txo("aa", 0)
        row = t.triage_txos(be, ["aa:0"])[0]
        self.assertEqual(row["state"], t.UNKNOWN)
        self.assertIn("not supported", row["reason"])
        self.assertNotEqual(row["reason"], "output not found")

    def test_bad_output_reference_and_spent_output(self):
        answers = {"/tx/aa": {"vout": [{"scriptpubkey_type": "p2pkh", "scriptpubkey_address": "1x", "value": 5}]},
                   "/tx/aa/outspend/0": {"spent": True}}
        rows = t.triage_txos(FakeEsplora(answers), ["aa", "aa:x", "aa:0", "aa:7"])
        self.assertEqual([r["state"] for r in rows], [t.UNKNOWN, t.UNKNOWN, "spent", t.UNKNOWN])
        self.assertIn("txid:vout", rows[0]["reason"])
        self.assertEqual(rows[3]["reason"], "output not found")

    def test_unspent_hash_output_at_an_address_that_never_spent(self):
        answers = {"/tx/aa": {"vout": [{"scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": "bc1x", "value": 5}]},
                   "/tx/aa/outspend/0": {"spent": False},
                   "/address/bc1x": esplora_address(1, 0, 5), "/address/bc1x/utxo": [{"value": 5}]}
        self.assertEqual(t.triage_txos(FakeEsplora(answers), ["aa:0"])[0]["state"], t.HASH_SAFE)
        answers["/address/bc1x"] = esplora_address(2, 1, 5)
        self.assertEqual(t.triage_txos(FakeEsplora(answers), ["aa:0"])[0]["state"], t.EXPOSED)


class BackendAnswers(unittest.TestCase):
    def test_esplora_address_fields(self):
        be = FakeEsplora({"/address/a": esplora_address(3, 2, 1000), "/address/a/utxo": [{"value": 1000}]})
        self.assertEqual(be.address("a"), dict(has_funded=True, has_spent=True, balance=1000, utxos=1, funded=3, spent=2))
        self.assertEqual(be.address("never-seen"), dict(has_funded=False, has_spent=False, balance=0, utxos=None, funded=0, spent=0))

    def test_indexer_reports_what_it_knows_and_no_more(self):
        answers = {"/address/sent": {"balance": 0, "totalReceived": 10, "totalSent": 10, "txCount": 5762}, "/address/sent/utxos": [],
                   "/address/kept": {"balance": 500, "totalReceived": 500, "totalSent": 0, "txCount": 1}, "/address/kept/utxos": [{"amount": 500}]}
        be = t.Indexer("http://fake", pause=0, fetch=lambda p: answers.get(p))
        sent, kept, never = be.address("sent"), be.address("kept"), be.address("never")
        self.assertEqual((sent["has_funded"], sent["has_spent"], sent["funded"], sent["utxos"]), (True, True, 5762, 0))
        self.assertEqual((kept["has_funded"], kept["has_spent"], kept["balance"], kept["utxos"]), (True, False, 500, 1))
        self.assertEqual((never["has_funded"], never["has_spent"], never["balance"]), (False, False, 0))
        self.assertNotIn("spent", sent)   # the Indexer has no count of spends, so none is claimed

    def test_version_bytes_are_the_nodes_and_pinned(self):
        """Blazecoin's chainparams give PUBKEY_ADDRESS 26 and SCRIPT_ADDRESS 5. The table once held 25 and no P2SH,
        and the tests agreed with it. These strings are the all-zero hash under each version byte (nobody's
        address), pinned so the table cannot drift again; the bytes were checked against real mainnet addresses
        and the live Indexer on 2026-11-16."""
        zero = bytes(20)
        self.assertEqual(t.CHAINS["blazecoin"]["p2pkh"], 26)
        self.assertEqual(t.CHAINS["blazecoin"]["p2sh"], 5)
        self.assertEqual(t.b58check_encode(bytes([26]) + zero), "BTngbpkVTh3nGGdFdufHcG5TN7hXYuX31z")
        self.assertEqual(t.b58check_encode(bytes([5]) + zero), "31h1vYVSYuKP6AhS86fbRdMw9XHieotbST")
        self.assertEqual(t.classify_address("blazecoin", "BTngbpkVTh3nGGdFdufHcG5TN7hXYuX31z"), ("p2pkh", None))
        self.assertEqual(t.classify_address("blazecoin", "31h1vYVSYuKP6AhS86fbRdMw9XHieotbST"), ("p2sh", None))
        self.assertEqual(t.classify_address("blazecoin", "B4T5ciTCkWauSqVAcVKy88ofjcSasUkSYU")[0], "unknown")       # version byte 25
        self.assertEqual(t.classify_address("blazecoin", "BQ" + "1" * 50), ("pqkh", None))

    def test_indexer_script_hash_address_is_hash_safe_until_spent(self):
        p2sh = t.b58check_encode(bytes([5]) + t.hash160(b"a script"))
        answers = {"/address/" + p2sh: {"balance": 900, "totalReceived": 900, "totalSent": 0, "txCount": 1},
                   "/address/" + p2sh + "/utxos": [{"amount": 900}]}
        be = t.Indexer("http://fake", pause=0, fetch=lambda p: answers.get(p))
        row = t.triage_addresses("blazecoin", be, [(p2sh, None)])[0]
        self.assertEqual((row["type"], row["state"], row["balance"]), ("p2sh", t.HASH_SAFE, 900))

    def test_unspent_pay_to_public_key_outputs_under_an_address_make_it_exposed(self):
        """The shape of Blazecoin's early coinbases: the address never spent, but its one coin is a P2PK output."""
        addr = t.b58check_encode(bytes([26]) + t.hash160(b"an early coinbase key"))
        txid = "ca" * 32
        answers = {"/address/" + addr: {"balance": 41300000000, "totalReceived": 41300000000, "totalSent": 0, "txCount": 1},
                   "/address/" + addr + "/utxos": [{"txId": txid, "outputIndex": 0, "amount": 41300000000}],
                   "/tx/" + txid + "/detail": {"outputs": [{"index": 0, "address": addr, "amount": 41300000000,
                                                             "scriptType": "pubkey", "isSpent": False}]}}
        be = t.Indexer("http://fake", pause=0, fetch=lambda p: answers.get(p))
        row = t.triage_addresses("blazecoin", be, [(addr, None)])[0]
        self.assertEqual((row["type"], row["state"], row["balance"]), ("p2pkh", t.EXPOSED, 41300000000))
        self.assertIn("1 unspent pay-to-public-key output(s)", row["reason"])
        self.assertIn("413.00000000 BLZ", row["reason"])
        # the same address with an ordinary P2PKH coin stays hash-safe
        answers["/tx/" + txid + "/detail"]["outputs"][0]["scriptType"] = "pubkeyhash"
        be = t.Indexer("http://fake", pause=0, fetch=lambda p: answers.get(p))
        self.assertEqual(t.triage_addresses("blazecoin", be, [(addr, None)])[0]["state"], t.HASH_SAFE)

    def test_outputs_beyond_the_check_limit_are_reported_not_assumed_safe(self):
        addr = t.b58check_encode(bytes([26]) + t.hash160(b"an early coinbase key"))
        n = t.Indexer.MAX_OUTPUT_CHECKS + 7
        utxos = [{"txId": format(i, "064x"), "outputIndex": 0, "amount": 1} for i in range(n)]
        answers = {"/address/" + addr: {"balance": n, "totalReceived": n, "totalSent": 0, "txCount": n},
                   "/address/" + addr + "/utxos": utxos}
        asked = []

        def fetch(p):
            asked.append(p)
            if p.startswith("/tx/"):
                return {"outputs": [{"index": 0, "amount": 1, "scriptType": "pubkeyhash", "isSpent": False}]}
            return answers.get(p)
        row = t.triage_addresses("blazecoin", t.Indexer("http://fake", pause=0, fetch=fetch), [(addr, None)])[0]
        self.assertEqual(row["state"], t.HASH_SAFE)
        self.assertIn("7 of its outputs were not checked", row["reason"])
        self.assertEqual(sum(1 for p in asked if p.startswith("/tx/")), t.Indexer.MAX_OUTPUT_CHECKS)

    def test_apply_bare_key_outputs_leaves_other_backends_alone(self):
        self.assertEqual(t.apply_bare_key_outputs("bitcoin", t.HASH_SAFE, "r", {"balance": 5}), (t.HASH_SAFE, "r"))
        self.assertEqual(t.apply_bare_key_outputs("blazecoin", t.EXPOSED, "r", {"unchecked_utxos": 3}), (t.EXPOSED, "r"))

    def test_indexer_classic_address_states(self):
        classic = t.b58check_encode(bytes([0x1A]) + t.hash160(b"k"))
        answers = {"/address/" + classic: {"balance": 500, "totalReceived": 500, "totalSent": 0, "txCount": 1},
                   "/address/" + classic + "/utxos": [{"amount": 500}]}
        be = t.Indexer("http://fake", pause=0, fetch=lambda p: answers.get(p))
        row = t.triage_addresses("blazecoin", be, [(classic, "0/0")])[0]
        self.assertEqual((row["type"], row["state"], row["balance"], row["path"], row["funded"]), ("p2pkh", t.HASH_SAFE, 500, "0/0", 1))
        answers["/address/" + classic]["totalSent"] = 1
        be = t.Indexer("http://fake", pause=0, fetch=lambda p: answers.get(p))
        self.assertEqual(t.triage_addresses("blazecoin", be, [(classic, None)])[0]["state"], t.EXPOSED)

    def test_each_address_is_fetched_once_per_run(self):
        xpub = "xpub6BgBgsespWvERF3LHQu6CnqdvfEvtMcQjYrcRzx53QJjSxarj2afYWcLteoGVky7D3UKDP9QyrLprQ3VCECoY49yfdDEHGCtMMj92pReUsQ"
        first = "bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr"
        fetch = CountingFetch({"/address/" + first: esplora_address(1, 0, 5000), "/address/" + first + "/utxo": [{"value": 5000}]})
        be = t.Esplora("http://fake", pause=0, fetch=fetch)
        a = t.build_parser().parse_args(["--descriptor", "tr(%s/0/*)" % xpub, "--gap", "3", first])
        targets = t.gather_targets(a, be)                      # the gap walk asks about each derived address...
        rows = t.triage_addresses("bitcoin", be, targets)      # ...and the triage asks again
        self.assertEqual(len(targets), 5)                      # the address given directly + 4 derived (index 0 used, then 3 unused)
        self.assertEqual(rows[0]["state"], t.EXPOSED)
        self.assertEqual(len(fetch.calls), 8)                  # 4 distinct addresses x (record + utxo list)
        self.assertEqual(set(fetch.calls.values()), {1}, fetch.calls)

    def test_rows_all_have_the_same_keys(self):
        answers = {"/address/12ZEw5Hcv1hTb6YUQJ69y1V7uhcoDz92PH": esplora_address(1, 0, 10),
                   "/address/12ZEw5Hcv1hTb6YUQJ69y1V7uhcoDz92PH/utxo": [{"value": 10}],
                   "/tx/aa": {"vout": [{"scriptpubkey_type": "p2pk", "value": 5}]}, "/tx/aa/outspend/0": {"spent": False}}
        be = FakeEsplora(answers)
        rows = t.triage_addresses("bitcoin", be, [("12ZEw5Hcv1hTb6YUQJ69y1V7uhcoDz92PH", None), ("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", None), ("junk", None)]) \
            + t.triage_txos(be, ["aa:0", "bb:0", "bad"])
        keys = {"address", "path", "type", "state", "reason", "balance", "utxos", "funded"}
        for r in rows:
            self.assertEqual(set(r), keys, r)
        json.dumps(rows)   # every row is plain data
        self.assertEqual(set(t.make_row("a", "p2pkh", t.HASH_SAFE, "why")), keys)


class CommandLine(unittest.TestCase):
    ADDR = "12ZEw5Hcv1hTb6YUQJ69y1V7uhcoDz92PH"
    TAPROOT = "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"

    def answers(self):
        return {"/address/" + self.ADDR: esplora_address(2, 0, 5000), "/address/" + self.ADDR + "/utxo": [{"value": 5000}],
                "/address/" + self.TAPROOT: esplora_address(1, 0, 700), "/address/" + self.TAPROOT + "/utxo": [{"value": 700}],
                "/tx/aa": {"vout": [{"scriptpubkey_type": "p2pk", "value": 5000000000}]}, "/tx/aa/outspend/0": {"spent": False}}

    def factory(self, seen=None):
        def make(chain, api, pause):
            if seen is not None:
                seen.append((chain, api, pause))
            return t.Esplora(api or "http://fake", pause=0, fetch=lambda p: self.answers().get(p))
        return make

    def run_main(self, argv, **kw):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = t.main(argv, **kw)
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def write_file(self, text):
        import tempfile
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(text)
        f.close()
        self.addCleanup(os.remove, f.name)
        return f.name

    def test_address_file_skips_comments_and_blank_lines(self):
        path = self.write_file("# my cold wallet\n\n%s\n   \n  # indented comment\n  %s  \n" % (self.ADDR, self.TAPROOT))
        self.assertEqual(t.read_address_file(path), [self.ADDR, self.TAPROOT])
        a = t.build_parser().parse_args(["--file", path, "extra"])
        self.assertEqual(t.gather_targets(a, FakeEsplora({})), [("extra", None), (self.ADDR, None), (self.TAPROOT, None)])

    def test_plain_xpub_is_refused_with_the_way_out(self):
        xpub = "xpub6BgBgsespWvERF3LHQu6CnqdvfEvtMcQjYrcRzx53QJjSxarj2afYWcLteoGVky7D3UKDP9QyrLprQ3VCECoY49yfdDEHGCtMMj92pReUsQ"
        # On Bitcoin the xpub version bytes name the scheme (BIP44, pay-to-public-key-hash): accepted.
        a = t.build_parser().parse_args(["--xpub", xpub, "--gap", "1"])
        targets = t.gather_targets(a, FakeEsplora({}))
        self.assertEqual([p for _, p in targets], ["0/0", "1/0"])
        self.assertEqual(t.classify_address("bitcoin", targets[0][0]), ("p2pkh", None))
        # On a chain that names no scheme for those version bytes the tool cannot guess the address type: refused.
        a = t.build_parser().parse_args(["--chain", "blazecoin", "--xpub", xpub])
        with self.assertRaises(ValueError) as cm:
            t.gather_targets(a, FakeEsplora({}))
        self.assertIn("--descriptor", str(cm.exception))
        code, out, err = self.run_main(["--chain", "blazecoin", "--xpub", xpub], backend_factory=self.factory())
        self.assertEqual((code, out), (2, ""))
        self.assertIn("--descriptor", err)
        # an extended key of an unknown version is refused outright
        with self.assertRaises(ValueError):
            t.Xpub.parse(t.b58check_encode(bytes.fromhex("deadbeef") + bytes(74)), "bitcoin")

    def test_nothing_to_do_is_an_error(self):
        with self.assertRaises(ValueError):
            t.gather_targets(t.build_parser().parse_args([]), FakeEsplora({}))
        code, _, err = self.run_main([], backend_factory=self.factory())
        self.assertEqual(code, 2)
        self.assertIn("give addresses", err)
        # --txo alone is enough
        self.assertEqual(t.gather_targets(t.build_parser().parse_args(["--txo", "aa:0"]), FakeEsplora({})), [])

    def test_zpub_walks_receive_and_change(self):
        zpub = "zpub6rFR7y4Q2AijBEqTUquhVz398htDFrtymD9xYYfG1m4wAcvPhXNfE3EfH1r1ADqtfSdVCToUG868RvUUkgDKf31mGDtKsAYz2oz2AGutZYs"
        a = t.build_parser().parse_args(["--xpub", zpub, "--gap", "2"])
        targets = t.gather_targets(a, FakeEsplora({}))          # nothing ever funded: 2 per branch
        self.assertEqual([p for _, p in targets], ["0/0", "0/1", "1/0", "1/1"])
        self.assertEqual(targets[0][0], "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu")
        self.assertEqual(targets[2][0], "bc1q8c6fshw2dlwun7ekn9qwf37cu2rn755upcp6el")

    def test_main_table_output(self):
        seen = []
        code, out, err = self.run_main([self.ADDR, self.TAPROOT, "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", "--txo", "aa:0", "--pause", "0"],
                                       backend_factory=self.factory(seen))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(seen, [("bitcoin", None, 0.0)])
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("address"))
        body = [ln for ln in lines[1:] if ln.strip()]
        self.assertTrue(body[0].startswith("aa:0"))             # exposed first, largest balance first
        self.assertIn("50.00000000 BTC", body[0])
        self.assertTrue(body[1].startswith(self.TAPROOT))
        self.assertTrue(body[2].startswith(self.ADDR))
        self.assertIn("hash-safe", body[2])
        self.assertIn("exposed         2 address(es)  50.00000700 BTC", out)
        self.assertIn("hash-safe       1 address(es)  0.00005000 BTC", out)
        self.assertIn("1 address(es) never funded (not shown)", out)
        self.assertIn("Exposed coins are the ones to move first", out)
        self.assertNotIn("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", out)

    def test_main_json_output(self):
        path = self.write_file("# file\n%s\n" % self.ADDR)
        code, out, err = self.run_main(["--file", path, "--txo", "aa:0", "--json", "--api", "http://own/api"],
                                       backend_factory=self.factory())
        self.assertEqual((code, err), (0, ""))
        d = json.loads(out)
        self.assertEqual((d["chain"], d["api"]), ("bitcoin", "http://own/api"))
        self.assertEqual([(r["address"], r["state"]) for r in d["rows"]], [(self.ADDR, t.HASH_SAFE), ("aa:0", t.EXPOSED)])
        self.assertEqual(d["totals"], {t.HASH_SAFE: {"addresses": 1, "balance": 5000}, t.EXPOSED: {"addresses": 1, "balance": 5000000000}})

    def test_main_on_blazecoin_uses_the_indexer_and_its_unit(self):
        pq = "BQHcY1yedCSGvq8KyXTAY4GW3wwaabje8hu72ERZrWpCYZcu8Qrn"
        answers = {"/address/" + pq: {"balance": 41300000000, "totalReceived": 41300000000, "totalSent": 0, "txCount": 1},
                   "/address/" + pq + "/utxos": [{"amount": 41300000000}],
                   "/tx/cc/detail": {"outputs": [{"index": 0, "address": pq, "amount": 2500000000, "scriptType": "pqkh", "isSpent": False}]}}
        made = []

        def make(chain, api, pause):
            made.append(t.CHAINS[chain]["backend"])
            return t.CHAINS[chain]["backend"]("http://fake", pause=0, fetch=lambda p: answers.get(p))

        code, out, _ = self.run_main(["--chain", "blazecoin", pq, "--txo", "cc:0"], backend_factory=make)
        self.assertEqual(code, 0)
        self.assertEqual(made, [t.Indexer])
        self.assertIn("413.00000000 BLZ", out)
        self.assertIn("25.00000000 BLZ", out)
        self.assertIn("post-quantum    2 address(es)  438.00000000 BLZ", out)
        self.assertNotIn("output not found", out)

    def test_default_factory_is_make_backend(self):
        import inspect
        self.assertIs(inspect.signature(t.main).parameters["backend_factory"].default, t.make_backend)


if __name__ == "__main__":
    unittest.main()
