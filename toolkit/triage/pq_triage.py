#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pq_triage: which of these coins are exposed to a quantum attacker, which are safe until spent,
and which are already post-quantum.

The first job of the Blazecoin Quantum Bridge (the migration pattern in BITCOIN-PORTING-NOTE.md, section 8),
done as a watch-only tool: addresses or an extended public key in, a three-state table out, no private key
anywhere near it. Standard library only; it talks to a public Esplora API for Bitcoin (blockstream.info or
mempool.space) or to the Blazecoin Indexer for BLZ.

States (one chain, one UTXO set; a coin is in exactly one):
  exposed       the public key is already on the chain, so a quantum attacker can take the coin at any time:
                pay-to-public-key outputs, Taproot outputs (the key IS the output), and any address that has spent before
                (the spend revealed the key; for P2SH/P2WSH it revealed the script and its keys)
  hash-safe     the key is committed only by its hash and has never been revealed: an unspent P2PKH, P2WPKH,
                P2SH or P2WSH at an address that has never spent. Safe until spent; at spending time the key
                is public for as long as the transaction waits to be mined
  post-quantum  the output type is post-quantum (Blazecoin P2PQH, `BQ...`); Bitcoin has none yet

What this tool cannot see: pay-to-public-key outputs (Satoshi-era coinbases and others) have no address, so
on Bitcoin they cannot be looked up by address; they are all exposed. Give them with --txo txid:vout and the tool reads the
output type from the transaction instead.

Usage
  pq_triage.py bc1q... 3... 1...                       Bitcoin addresses (default --chain bitcoin)
  pq_triage.py --xpub zpub6r...                        BIP84 account key: derives receive + change, gap limit 20
  pq_triage.py --descriptor "tr(xpub6B.../0/*)"        pkh( sh(wpkh( wpkh( tr( with /0/* or /<0;1>/*
  pq_triage.py --chain blazecoin B... BQ...            Blazecoin, via the public Indexer
  pq_triage.py --txo <txid>:<vout> ...                 specific outputs (the only way to see P2PK)
  pq_triage.py --file addresses.txt --json            one address per line; machine-readable output

Nothing is written anywhere; nothing but the addresses you give leaves your machine (they are sent to the
block explorer you choose, which is the privacy cost of any watch-only tool; run your own Esplora to avoid it).
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sys
import time
import urllib.error
import urllib.request

# ----------------------------------------------------------------------------------------------------------------
# secp256k1 (only what BIP32 public derivation and the Taproot tweak need)
# ----------------------------------------------------------------------------------------------------------------
_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
      0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)


def _inv(a: int) -> int:
    return pow(a, _P - 2, _P)


def _add(p, q):
    if p is None:
        return q
    if q is None:
        return p
    if p[0] == q[0]:
        if (p[1] + q[1]) % _P == 0:
            return None
        lam = (3 * p[0] * p[0]) * _inv(2 * p[1]) % _P
    else:
        lam = (q[1] - p[1]) * _inv(q[0] - p[0]) % _P
    x = (lam * lam - p[0] - q[0]) % _P
    return (x, (lam * (p[0] - x) - p[1]) % _P)


def _mul(k: int, p):
    r = None
    while k:
        if k & 1:
            r = _add(r, p)
        p = _add(p, p)
        k >>= 1
    return r


def _lift_x(x: int, even: bool = True):
    y2 = (pow(x, 3, _P) + 7) % _P
    y = pow(y2, (_P + 1) // 4, _P)
    if y * y % _P != y2:
        raise ValueError("not on curve")
    if (y % 2 == 0) != even:
        y = _P - y
    return (x, y)


def _decompress(b: bytes):
    if len(b) != 33 or b[0] not in (2, 3):
        raise ValueError("bad compressed point")
    return _lift_x(int.from_bytes(b[1:], "big"), even=(b[0] == 2))


def _compress(p) -> bytes:
    return bytes([2 + (p[1] & 1)]) + p[0].to_bytes(32, "big")


# ----------------------------------------------------------------------------------------------------------------
# hashes, base58, bech32
# ----------------------------------------------------------------------------------------------------------------
def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def hash160(b: bytes) -> bytes:
    return hashlib.new("ripemd160", sha256(b)).digest()


def tagged_hash(tag: str, msg: bytes) -> bytes:
    t = sha256(tag.encode())
    return sha256(t + t + msg)


_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = _B58[r] + s
    pad = len(b) - len(b.lstrip(b"\0"))
    return "1" * pad + s


def b58decode(s: str) -> bytes:
    n = 0
    for c in s:
        if c not in _B58:
            raise ValueError("bad base58 character")
        n = n * 58 + _B58.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(s) - len(s.lstrip("1"))
    return b"\0" * pad + b


def b58check_encode(payload: bytes) -> str:
    return b58encode(payload + sha256(sha256(payload))[:4])


def b58check_decode(s: str) -> bytes:
    raw = b58decode(s)
    if len(raw) < 5 or sha256(sha256(raw[:-4]))[:4] != raw[-4:]:
        raise ValueError("bad base58 checksum")
    return raw[:-4]


_BECH = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_CONST, _BECH32M_CONST = 1, 0x2BC830A3


def _bech_polymod(values):
    gen = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= gen[i] if (top >> i) & 1 else 0
    return chk


def _bech_hrp_expand(hrp):
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _convertbits(data, frombits, tobits, pad=True):
    acc, bits, ret = 0, 0, []
    maxv = (1 << tobits) - 1
    for v in data:
        acc = (acc << frombits) | v
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad and bits:
        ret.append((acc << (tobits - bits)) & maxv)
    elif not pad and (bits >= frombits or ((acc << (tobits - bits)) & maxv)):
        raise ValueError("bad padding")
    return ret


def segwit_encode(hrp: str, version: int, program: bytes) -> str:
    data = [version] + _convertbits(program, 8, 5)
    const = _BECH32_CONST if version == 0 else _BECH32M_CONST
    poly = _bech_polymod(_bech_hrp_expand(hrp) + data + [0] * 6) ^ const
    chk = [(poly >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(_BECH[d] for d in data + chk)


def segwit_decode(addr: str):
    """(hrp, version, program) or None."""
    if addr != addr.lower() and addr != addr.upper():
        return None
    addr = addr.lower()
    pos = addr.rfind("1")
    if pos < 1 or pos + 7 > len(addr) or len(addr) > 90:
        return None
    hrp, data = addr[:pos], addr[pos + 1:]
    if any(c not in _BECH for c in data):
        return None
    values = [_BECH.index(c) for c in data]
    poly = _bech_polymod(_bech_hrp_expand(hrp) + values)
    version = values[0]
    if version > 16:
        return None
    if poly != (_BECH32_CONST if version == 0 else _BECH32M_CONST):
        return None
    program = bytes(_convertbits(values[1:-6], 5, 8, pad=False))
    if version == 0 and len(program) not in (20, 32):
        return None
    if not 2 <= len(program) <= 40:
        return None
    return hrp, version, program


# ----------------------------------------------------------------------------------------------------------------
# output types and the three states
# ----------------------------------------------------------------------------------------------------------------
EXPOSED, HASH_SAFE, POST_QUANTUM, UNKNOWN = "exposed", "hash-safe", "post-quantum", "unknown"

# The whole rule of the triage, as data: output type -> (state and reason while the address has never spent,
# state and reason once it has). A new output type is one new line here and nothing else.
_KEY_SPENT = (EXPOSED, "address has spent before: the key is on the chain")
_SCRIPT_SPENT = (EXPOSED, "address has spent before: the script and its keys are on the chain")
STATE_RULES: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
    "pqkh": ((POST_QUANTUM, "post-quantum output type"),) * 2,
    "p2pk": ((EXPOSED, "pay-to-public-key: the key is the output"),) * 2,
    "v1_p2tr": ((EXPOSED, "Taproot: the key is in the output"),) * 2,
    "p2pkh": ((HASH_SAFE, "key committed by hash, never revealed"), _KEY_SPENT),
    "v0_p2wpkh": ((HASH_SAFE, "key committed by hash, never revealed"), _KEY_SPENT),
    "p2sh": ((HASH_SAFE, "script committed by hash, never revealed"), _SCRIPT_SPENT),
    "v0_p2wsh": ((HASH_SAFE, "script committed by hash, never revealed"), _SCRIPT_SPENT),
}


def state_for(script_type: str, has_spent: bool) -> tuple[str, str]:
    """The Bridge state and the reason, from the output type and whether the address has ever spent."""
    rule = STATE_RULES.get(script_type)
    if rule is None:
        return UNKNOWN, "unrecognised output type"
    return rule[1] if has_spent else rule[0]


def depends_on_spend_history(script_type: str) -> bool:
    """True for a type whose state changes once its address has spent (the hash-committed types)."""
    rule = STATE_RULES.get(script_type)
    return rule is not None and rule[0] != rule[1]


def make_row(address: str, script_type: str, state: str, reason: str | None, path: str | None = None,
             balance: int = 0, utxos: int | None = 0, funded: int = 0) -> dict:
    """One line of the result. The single place a row is built, so every row has the same keys."""
    return dict(address=address, path=path, type=script_type, state=state, reason=reason,
                balance=balance, utxos=utxos, funded=funded)


# ----------------------------------------------------------------------------------------------------------------
# BIP32 public derivation and address derivation
# ----------------------------------------------------------------------------------------------------------------
class Xpub:
    def __init__(self, key: bytes, chain_code: bytes):
        self.key, self.chain_code = key, chain_code

    @classmethod
    def parse(cls, s: str, chain: str) -> tuple["Xpub", str | None]:
        raw = b58check_decode(s)
        if len(raw) != 78:
            raise ValueError("extended key must be 78 bytes")
        scheme = CHAINS[chain]["xpub_versions"].get(raw[:4].hex())
        if scheme is None and raw[:4].hex() not in ("0488b21e", "043587cf"):
            raise ValueError("unknown extended key version %s" % raw[:4].hex())
        return cls(raw[45:78], raw[13:45]), scheme

    def child(self, i: int) -> "Xpub":
        if i >= 0x80000000:
            raise ValueError("hardened derivation needs the private key")
        I = hmac.new(self.chain_code, self.key + i.to_bytes(4, "big"), hashlib.sha512).digest()
        il = int.from_bytes(I[:32], "big")
        if il >= _N:
            raise ValueError("invalid child")
        point = _add(_mul(il, _G), _decompress(self.key))
        if point is None:
            raise ValueError("invalid child")
        return Xpub(_compress(point), I[32:])

    def derive(self, path: list[int]) -> "Xpub":
        k = self
        for i in path:
            k = k.child(i)
        return k


def address_from_pubkey(chain: str, scheme: str, pubkey: bytes) -> str:
    c = CHAINS[chain]
    if scheme == "pkh":
        return b58check_encode(bytes([c["p2pkh"]]) + hash160(pubkey))
    if scheme == "wpkh":
        return segwit_encode(c["hrp"], 0, hash160(pubkey))
    if scheme == "sh-wpkh":
        redeem = b"\x00\x14" + hash160(pubkey)
        return b58check_encode(bytes([c["p2sh"]]) + hash160(redeem))
    if scheme == "tr":
        x = pubkey[1:]
        internal = _lift_x(int.from_bytes(x, "big"), even=True)
        t = int.from_bytes(tagged_hash("TapTweak", x), "big")
        if t >= _N:
            raise ValueError("bad tweak")
        out = _add(internal, _mul(t, _G))
        return segwit_encode(c["hrp"], 1, out[0].to_bytes(32, "big"))
    raise ValueError("unknown scheme %s" % scheme)


_DESC = re.compile(r"^\s*(pkh|wpkh|sh\(wpkh|tr)\((\w+)((?:/\d+'?h?)*)/(<0;1>|\*|\d+)(?:/\*)?\)?\)?\s*$")


def parse_descriptor(desc: str, chain: str) -> tuple[Xpub, str, list[list[int]]]:
    """Minimal: pkh(KEY/0/*), wpkh(KEY/<0;1>/*), sh(wpkh(KEY/0/*)), tr(KEY/0/*). Returns (xpub, scheme, branches)."""
    m = _DESC.match(desc.replace("#", " ").split()[0] if "#" in desc else desc)
    if not m:
        raise ValueError("descriptor not supported: use pkh( wpkh( sh(wpkh( or tr( with KEY/0/* or KEY/<0;1>/*")
    fn, key, mid, last = m.groups()
    scheme = {"pkh": "pkh", "wpkh": "wpkh", "sh(wpkh": "sh-wpkh", "tr": "tr"}[fn]
    xpub, _ = Xpub.parse(key, chain)
    mid_path = [int(p.rstrip("'h")) for p in mid.split("/") if p]
    if any("'" in p or "h" in p for p in mid.split("/") if p):
        raise ValueError("hardened steps after the extended key need the private key")
    if last == "<0;1>":
        branches = [mid_path + [0], mid_path + [1]]
    elif last == "*":
        branches = [mid_path]
    else:
        branches = [mid_path + [int(last)]]
    return xpub, scheme, branches


def derive_addresses(xpub: Xpub, scheme: str, branches: list[list[int]], chain: str, gap: int, used) -> list[tuple[str, str]]:
    """Walk each branch until `gap` consecutive addresses have never been funded (used(addr) -> bool)."""
    out = []
    for br in branches:
        node = xpub.derive(br)
        unused = 0
        i = 0
        while unused < gap and i < 10000:
            addr = address_from_pubkey(chain, scheme, node.child(i).key)
            path = "/".join(str(x) for x in br + [i])
            out.append((addr, path))
            unused = 0 if used(addr) else unused + 1
            i += 1
    return out


# ----------------------------------------------------------------------------------------------------------------
# backends
# ----------------------------------------------------------------------------------------------------------------
class LookupNotSupported(Exception):
    """This backend cannot answer this kind of question (not the same as "not found")."""


class Backend:
    """What the triage needs from a block explorer, and nothing more:

      address(addr) -> dict with
          has_funded  bool  the address has ever received anything
          has_spent   bool  the address has ever spent anything (confirmed or in the mempool, where the explorer says)
          balance     int   unspent amount, in the chain's smallest unit
          utxos       int | None  number of unspent outputs; None when the explorer would not list them
          funded      int   the explorer's own activity count for the address (its meaning differs per explorer,
                            see each subclass); informational only, the triage decides on has_funded / has_spent
          bare_key_utxos, bare_key_value, unchecked_utxos   optional (see Indexer): unspent outputs listed under
                            the address that are really pay-to-public-key, and how many outputs were not looked at
      txo(txid, vout) -> dict(type, address, value, spent), or None when there is no such output.
          A backend that cannot look outputs up leaves this alone: it raises LookupNotSupported.

    Answers for an address are remembered for the life of the object, so a run asks the explorer once per address
    however many steps need it (the gap-limit walk and the triage both do).
    """

    def __init__(self, base: str, pause: float = 0.2, fetch=None):
        self.base = base.rstrip("/")
        self.pause = pause
        self._fetch = fetch or self._http
        self._addresses: dict[str, dict] = {}

    def _http(self, path: str):
        req = urllib.request.Request(self.base + path, headers={"User-Agent": "pq-triage/1.0"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    body = r.read()
                time.sleep(self.pause)
                try:
                    return json.loads(body)
                except ValueError:
                    return body.decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                if e.code == 429 and attempt < 2:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                if 400 <= e.code < 500:
                    # Esplora answers some refusals with a 4xx and a plain-text reason
                    # ("Too many unspent outputs" is a 400); hand the text back as the answer.
                    body = e.read().decode("utf-8", "replace").strip()
                    time.sleep(self.pause)
                    return body or None
                raise
        return None

    def get(self, path: str):
        return self._fetch(path)

    def address(self, addr: str) -> dict:
        if addr not in self._addresses:
            self._addresses[addr] = self._address(addr)
        return self._addresses[addr]

    def _address(self, addr: str) -> dict:
        raise NotImplementedError

    def txo(self, txid: str, vout: int) -> dict | None:
        raise LookupNotSupported("this explorer cannot look up a single output")


class Esplora(Backend):
    """An Esplora API (blockstream.info, mempool.space, or your own). `funded` and `spent` are counts of outputs."""

    def _address(self, addr: str) -> dict:
        d = self.get("/address/" + addr) or {}
        cs, ms = d.get("chain_stats", {}), d.get("mempool_stats", {})
        funded = cs.get("funded_txo_count", 0) + ms.get("funded_txo_count", 0)
        spent = cs.get("spent_txo_count", 0) + ms.get("spent_txo_count", 0)
        balance = (cs.get("funded_txo_sum", 0) - cs.get("spent_txo_sum", 0)
                   + ms.get("funded_txo_sum", 0) - ms.get("spent_txo_sum", 0))
        utxos = self.get("/address/" + addr + "/utxo")
        n_utxo = len(utxos) if isinstance(utxos, list) else None  # "Too many unspent outputs" comes back as text
        return dict(has_funded=funded > 0 or balance != 0, has_spent=spent > 0, balance=balance, utxos=n_utxo,
                    funded=funded, spent=spent)

    def txo(self, txid: str, vout: int) -> dict | None:
        tx = self.get("/tx/" + txid)
        if not isinstance(tx, dict) or vout >= len(tx.get("vout", [])):
            return None
        o = tx["vout"][vout]
        spent = self.get("/tx/%s/outspend/%d" % (txid, vout)) or {}
        return dict(type=o.get("scriptpubkey_type", "unknown"), address=o.get("scriptpubkey_address"),
                    value=o.get("value", 0), spent=bool(spent.get("spent")))


class Indexer(Backend):
    """The Blazecoin Indexer's public JSON API (/indexer/api).

    Its address record has totals, not output counts: `funded` here is the number of TRANSACTIONS that touch the
    address (txCount), and there is no count of spends at all, only whether anything was ever sent (totalSent > 0).
    That is all the triage needs, and it is reported as has_funded / has_spent without pretending to more."""

    # the node's names for output types (what the Indexer stores) -> the names used in STATE_RULES
    SCRIPT_TYPES = {
        "pqkh": "pqkh",
        "pubkey": "p2pk",
        "pubkeyhash": "p2pkh",
        "scripthash": "p2sh",
        "witness_v0_keyhash": "v0_p2wpkh",
        "witness_v0_scripthash": "v0_p2wsh",
        "witness_v1_taproot": "v1_p2tr",
    }

    # How many unspent outputs of one address are looked up individually for their real script type.
    MAX_OUTPUT_CHECKS = 100

    def _address(self, addr: str) -> dict:
        d = self.get("/address/" + addr) or {}
        utxos = self.get("/address/" + addr + "/utxos")
        tx_count = d.get("txCount", 0)
        info = dict(has_funded=tx_count > 0 or d.get("totalReceived", 0) > 0, has_spent=d.get("totalSent", 0) > 0,
                    balance=d.get("balance", 0), utxos=len(utxos) if isinstance(utxos, list) else None,
                    funded=tx_count)
        info.update(self._bare_key_outputs(utxos if isinstance(utxos, list) else []))
        return info

    def _bare_key_outputs(self, utxos: list) -> dict:
        """The Indexer files a pay-to-public-key output under the address of its key, so an address that has
        never spent can still hold coins whose key is already on the chain (Blazecoin's early coinbases are like
        this; seen on mainnet 2026-11-16). The address record does not say, so each unspent output is looked up for
        its own script type, up to MAX_OUTPUT_CHECKS; the rest are counted as unchecked rather than assumed safe."""
        count = value = 0
        for u in utxos[:self.MAX_OUTPUT_CHECKS]:
            txid, index = u.get("txId"), u.get("outputIndex")
            if not txid or index is None:
                continue
            o = self.txo(txid, index)
            if o and o["type"] == "p2pk":
                count += 1
                value += o["value"]
        return dict(bare_key_utxos=count, bare_key_value=value, unchecked_utxos=max(0, len(utxos) - self.MAX_OUTPUT_CHECKS))

    def txo(self, txid: str, vout: int) -> dict | None:
        """From /tx/{txid}/detail: outputs carry index, address, amount, scriptType, isSpent."""
        tx = self.get("/tx/" + txid + "/detail")
        if not isinstance(tx, dict):
            return None
        for o in tx.get("outputs", []):
            if o.get("index") == vout:
                raw_type = str(o.get("scriptType", "")).lower()
                return dict(type=self.SCRIPT_TYPES.get(raw_type, raw_type or "unknown"), address=o.get("address") or None,
                            value=o.get("amount", 0), spent=bool(o.get("isSpent")))
        return None


# ----------------------------------------------------------------------------------------------------------------
# chains: one entry each (address formats, unit, explorer). Adding a chain is adding an entry.
# ----------------------------------------------------------------------------------------------------------------
def classify_segwit_base58(c: dict, address: str) -> tuple[str, str | None]:
    """Bitcoin-style addresses: bech32/bech32m witness programs under the chain's prefix, then Base58Check."""
    sw = segwit_decode(address) if c.get("hrp") else None
    if sw is not None:
        hrp, ver, prog = sw
        if hrp != c["hrp"]:
            return "unknown", "wrong network prefix"
        if ver == 0 and len(prog) == 20:
            return "v0_p2wpkh", None
        if ver == 0 and len(prog) == 32:
            return "v0_p2wsh", None
        if ver == 1 and len(prog) == 32:
            return "v1_p2tr", None
        return "unknown", "future witness version"
    try:
        raw = b58check_decode(address)
    except ValueError:
        return "unknown", "not an address"
    if len(raw) == 21 and raw[0] == c["p2pkh"]:
        return "p2pkh", None
    if len(raw) == 21 and c.get("p2sh") is not None and raw[0] == c["p2sh"]:
        return "p2sh", None
    return "unknown", "unrecognised version byte"


def classify_blazecoin(c: dict, address: str) -> tuple[str, str | None]:
    """Blazecoin: post-quantum key-hash addresses (`BQ...`, 52 characters), then classic Base58Check: P2PKH
    (version byte 26, addresses start with `B`) and P2SH (version byte 5, addresses start with `3`), the values
    in the node's chainparams. Until 2026-11-16 this table had 25 for P2PKH and no P2SH, so every classic address
    came back "unknown"; the unit tests used the same wrong byte and passed. Found by running the tool against the
    live Indexer, and the tests now use real mainnet addresses."""
    if address.startswith("BQ") and len(address) == 52:
        return "pqkh", None
    try:
        raw = b58check_decode(address)
    except ValueError:
        return "unknown", "not a Blazecoin address"
    if len(raw) == 21 and raw[0] == c["p2pkh"]:
        return "p2pkh", None
    if len(raw) == 21 and c.get("p2sh") is not None and raw[0] == c["p2sh"]:
        return "p2sh", None
    return "unknown", "unrecognised version byte"


CHAINS = {
    "bitcoin": dict(unit="BTC", backend=Esplora, api="https://blockstream.info/api", classify=classify_segwit_base58,
                    hrp="bc", p2pkh=0x00, p2sh=0x05,
                    xpub_versions={"0488b21e": "pkh", "049d7cb2": "sh-wpkh", "04b24746": "wpkh"}),
    "bitcoin-testnet": dict(unit="BTC", backend=Esplora, api="https://blockstream.info/testnet/api",
                            classify=classify_segwit_base58, hrp="tb", p2pkh=0x6F, p2sh=0xC4,
                            xpub_versions={"043587cf": "pkh", "044a5262": "sh-wpkh", "045f1cf6": "wpkh"}),
    "blazecoin": dict(unit="BLZ", backend=Indexer, api="https://blazecoin.co.uk/indexer/api", classify=classify_blazecoin,
                      hrp=None, p2pkh=0x1A, p2sh=0x05, xpub_versions={}),
}


def classify_address(chain: str, address: str) -> tuple[str, str | None]:
    """(script type, note) for an address string, from its format alone."""
    c = CHAINS[chain]
    return c["classify"](c, address)


def make_backend(chain: str, api: str | None = None, pause: float = 0.2) -> Backend:
    """The chain's own kind of explorer, at `api` or at the chain's public default."""
    c = CHAINS[chain]
    return c["backend"](api or c["api"], pause)


def fmt_amount(sat: int, chain: str) -> str:
    return "%.8f %s" % (sat / 1e8, CHAINS[chain]["unit"])


# ----------------------------------------------------------------------------------------------------------------
# the triage
# ----------------------------------------------------------------------------------------------------------------
def triage_addresses(chain: str, backend, addresses: list[tuple[str, str | None]]) -> list[dict]:
    rows = []
    for addr, path in addresses:
        stype, note = classify_address(chain, addr)
        if stype == "unknown":
            rows.append(make_row(addr, stype, UNKNOWN, note, path))
            continue
        info = backend.address(addr)
        if not info["has_funded"] and info["balance"] == 0:
            rows.append(make_row(addr, stype, "unused", "never funded", path))
            continue
        state, reason = state_for(stype, info["has_spent"])
        state, reason = apply_bare_key_outputs(chain, state, reason, info)
        if info["balance"] == 0:
            reason += "; balance is zero (nothing to move)"
        rows.append(make_row(addr, stype, state, reason, path, info["balance"], info["utxos"], info["funded"]))
    return rows


def apply_bare_key_outputs(chain: str, state: str, reason: str, info: dict) -> tuple[str, str]:
    """An address is EXPOSED, whatever its own type and history say, when unspent pay-to-public-key outputs are
    listed under it; and a hash-safe verdict is qualified when some of its outputs could not be checked."""
    if info.get("bare_key_utxos"):
        return EXPOSED, "%d unspent pay-to-public-key output(s) under this address (%s): the key is on the chain" % (
            info["bare_key_utxos"], fmt_amount(info["bare_key_value"], chain))
    if info.get("unchecked_utxos") and state == HASH_SAFE:
        reason += "; %d of its outputs were not checked for pay-to-public-key" % info["unchecked_utxos"]
    return state, reason


def triage_txos(backend, txos: list[str]) -> list[dict]:
    rows = []
    for ref in txos:
        txid, _, vout = ref.partition(":")
        if not vout.isdigit():
            rows.append(make_row(ref, "unknown", UNKNOWN, "not an output reference: use txid:vout"))
            continue
        try:
            o = backend.txo(txid, int(vout))
        except LookupNotSupported:
            rows.append(make_row(ref, "unknown", UNKNOWN, "looking up a single output is not supported on this chain's explorer"))
            continue
        if o is None:
            rows.append(make_row(ref, "unknown", UNKNOWN, "output not found"))
            continue
        if o["spent"]:
            rows.append(make_row(ref, o["type"], "spent", "already spent", funded=1))
            continue
        has_spent = False
        if depends_on_spend_history(o["type"]) and o["address"]:
            # the output's own address may have spent elsewhere
            has_spent = backend.address(o["address"])["has_spent"]
        state, reason = state_for(o["type"], has_spent)
        rows.append(make_row(ref, o["type"], state, reason, balance=o["value"], utxos=1, funded=1))
    return rows


def summarise(rows: list[dict]) -> dict:
    tot = {}
    for r in rows:
        t = tot.setdefault(r["state"], dict(addresses=0, balance=0))
        t["addresses"] += 1
        t["balance"] += r["balance"] or 0
    return tot


def print_table(rows: list[dict], chain: str) -> None:
    order = {EXPOSED: 0, HASH_SAFE: 1, POST_QUANTUM: 2, "spent": 3, "unused": 4, UNKNOWN: 5}
    rows = sorted(rows, key=lambda r: (order.get(r["state"], 9), -(r["balance"] or 0)))
    w = max([len(r["address"]) for r in rows] + [7])
    print("%-*s  %-10s  %-12s  %18s  %s" % (w, "address", "type", "state", "balance", "why"))
    for r in rows:
        if r["state"] == "unused":
            continue
        print("%-*s  %-10s  %-12s  %18s  %s" % (w, r["address"], r["type"], r["state"], fmt_amount(r["balance"] or 0, chain), r["reason"]))
    unused = sum(1 for r in rows if r["state"] == "unused")
    tot = summarise(rows)
    print()
    for state in (EXPOSED, HASH_SAFE, POST_QUANTUM):
        t = tot.get(state)
        if t:
            print("%-12s  %3d address(es)  %s" % (state, t["addresses"], fmt_amount(t["balance"], chain)))
    if unused:
        print("%-12s  %3d address(es) never funded (not shown)" % ("unused", unused))
    if tot.get(EXPOSED, {}).get("balance", 0):
        print("\nExposed coins are the ones to move first and at once. Hash-safe coins are safe until spent;"
              "\nsend them to a post-quantum output when they next move anyway.")


# ----------------------------------------------------------------------------------------------------------------
# command line
# ----------------------------------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("addresses", nargs="*", help="addresses to triage")
    ap.add_argument("--chain", choices=sorted(CHAINS), default="bitcoin")
    ap.add_argument("--api", help="Esplora or Indexer base URL (default: the chain's public one)")
    ap.add_argument("--xpub", help="extended public key (xpub/ypub/zpub, or tpub/upub/vpub on testnet): receive and change branches")
    ap.add_argument("--descriptor", help="pkh(KEY/0/*), wpkh(KEY/<0;1>/*), sh(wpkh(KEY/0/*)), tr(KEY/0/*)")
    ap.add_argument("--gap", type=int, default=20, help="gap limit for derived addresses (default 20)")
    ap.add_argument("--txo", action="append", default=[], help="txid:vout of a specific output (the only way to see P2PK)")
    ap.add_argument("--file", help="file with one address per line")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--pause", type=float, default=0.2, help="seconds between API requests")
    return ap


def read_address_file(path: str) -> list[str]:
    """One address per line; blank lines and lines starting with # are skipped."""
    with open(path, encoding="utf-8") as f:
        lines = [line.strip() for line in f]
    return [line for line in lines if line and not line.startswith("#")]


def gather_targets(a, backend) -> list[tuple[str, str | None]]:
    """Every address the arguments name: given directly, read from --file, or derived from --xpub / --descriptor
    (walking each branch to the gap limit, asking the backend which addresses were ever funded).
    Raises ValueError with the message to show when the arguments cannot be used."""
    targets: list[tuple[str, str | None]] = [(x, None) for x in a.addresses]
    if a.file:
        targets += [(x, None) for x in read_address_file(a.file)]

    def used(addr: str) -> bool:
        return backend.address(addr)["has_funded"]

    if a.xpub:
        xpub, scheme = Xpub.parse(a.xpub, a.chain)
        if scheme is None:
            raise ValueError("a plain xpub does not say which address type it is for: use --descriptor")
        targets += derive_addresses(xpub, scheme, [[0], [1]], a.chain, a.gap, used)
    if a.descriptor:
        xpub, scheme, branches = parse_descriptor(a.descriptor, a.chain)
        targets += derive_addresses(xpub, scheme, branches, a.chain, a.gap, used)
    if not targets and not a.txo:
        raise ValueError("give addresses, --file, --xpub, --descriptor or --txo")
    return targets


def main(argv=None, backend_factory=make_backend) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    backend = backend_factory(a.chain, a.api, a.pause)
    try:
        targets = gather_targets(a, backend)
    except ValueError as e:
        ap.error(str(e))

    rows = triage_addresses(a.chain, backend, targets) + triage_txos(backend, a.txo)
    if a.json:
        print(json.dumps(dict(chain=a.chain, api=backend.base, rows=rows, totals=summarise(rows)), indent=2))
    else:
        print_table(rows, a.chain)
    return 0


if __name__ == "__main__":
    sys.exit(main())
