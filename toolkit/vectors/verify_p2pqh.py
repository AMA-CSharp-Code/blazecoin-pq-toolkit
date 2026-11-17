#!/usr/bin/env python3
"""
Reference verifier for P2PQH (ML-DSA-44, FIPS 204) inputs - about 150 lines, pure Python.

It is written to be read: every consensus rule for a post-quantum input is in verify_input(), in the
order the node applies them. It shares no code with the vector generator, the C++ node or the C# wallet.

    pip install dilithium-py
    python verify_p2pqh.py                    # checks pqsig_vectors.json and mainnet_examples.json
    python verify_p2pqh.py <tx hex> <input index> <prevout amount in satoshi> <prevout scriptPubKey hex>

Output type (34 bytes):  0x20 <pqkh:32> OP_CHECKPQSIG(0xba)
Spend (scriptSig):       <sig:2420> <keyblob:1313>          exactly two pushes, nothing else
keyblob = algo_id(1) || pubkey          pqkh = TaggedHash("Blazecoin/PQKH/v1", keyblob)
message = TaggedHash("Blazecoin/PQSig/v1", preimage)        preimage is BIP-143 shaped, see sighash()
valid   = ML-DSA-44.Verify(pubkey, message, sig, ctx = "blazecoin-tx-v1")
TaggedHash(tag, m) = SHA256(SHA256(tag) || SHA256(tag) || m)
"""
import hashlib, json, os, struct, sys
from dilithium_py.ml_dsa import ML_DSA_44

OP_PUSHDATA1, OP_PUSHDATA2, OP_PUSHDATA4, OP_1NEGATE, OP_1, OP_16, OP_CHECKPQSIG = 0x4c, 0x4d, 0x4e, 0x4f, 0x51, 0x60, 0xba
ALGO_MLDSA44, PUBKEY_LEN, SIG_LEN, MAX_ELEMENT = 0x01, 1312, 2420, 5000
CTX_TX = b"blazecoin-tx-v1"

def sha256(b): return hashlib.sha256(b).digest()
def sha256d(b): return sha256(sha256(b))
def tagged_hash(tag, m):
    t = sha256(tag)
    return sha256(t + t + m)

# ------------------------------------------------------------------ transaction parsing (no witness on this chain)
class Reader:
    def __init__(self, data): self.d, self.p = data, 0
    def take(self, n):
        if self.p + n > len(self.d): raise ValueError("truncated")
        out = self.d[self.p:self.p + n]; self.p += n
        return out
    def u32(self): return struct.unpack("<I", self.take(4))[0]
    def varint(self):
        n = self.take(1)[0]
        if n < 0xfd: return n
        return struct.unpack({0xfd: "<H", 0xfe: "<I", 0xff: "<Q"}[n], self.take({0xfd: 2, 0xfe: 4, 0xff: 8}[n]))[0]

def parse_tx(raw):
    r = Reader(raw)
    tx = {"version": r.take(4), "vin": [], "vout": []}
    for _ in range(r.varint()):
        outpoint = r.take(36)
        tx["vin"].append({"outpoint": outpoint, "scriptSig": r.take(r.varint()), "sequence": r.take(4)})
    for _ in range(r.varint()):
        value = r.take(8)
        spk_len_at = r.p
        spk = r.take(r.varint())
        tx["vout"].append(value + raw[spk_len_at:r.p - len(spk)] + spk)   # the serialized output, as hashed
    tx["locktime"] = r.take(4)
    if r.p != len(raw): raise ValueError("trailing bytes")
    return tx

def parse_pushes(script):
    """The stack a push-only script leaves, or None if any opcode is not a push."""
    r, stack = Reader(script), []
    while r.p < len(script):
        op = r.take(1)[0]
        if op < OP_PUSHDATA1: item = r.take(op)
        elif op == OP_PUSHDATA1: item = r.take(r.take(1)[0])
        elif op == OP_PUSHDATA2: item = r.take(struct.unpack("<H", r.take(2))[0])
        elif op == OP_PUSHDATA4: item = r.take(r.u32())
        elif op == OP_1NEGATE: item = b"\x81"
        elif OP_1 <= op <= OP_16: item = bytes([op - OP_1 + 1])
        else: return None
        stack.append(item)
    return stack

# ------------------------------------------------------------------ the digest
def sighash(tx, n_in, amount, script_code):
    """BIP-143 shape: the amount and the script being spent are committed to, and the three shared
    hashes are the same for every input, so a transaction is hashed once however many inputs it has."""
    hash_prevouts = sha256d(b"".join(i["outpoint"] for i in tx["vin"]))
    hash_sequence = sha256d(b"".join(i["sequence"] for i in tx["vin"]))
    hash_outputs = sha256d(b"".join(tx["vout"]))
    tin = tx["vin"][n_in]
    preimage = (tx["version"] + hash_prevouts + hash_sequence + tin["outpoint"]
                + bytes([len(script_code)]) + script_code + struct.pack("<q", amount) + tin["sequence"]
                + hash_outputs + tx["locktime"] + struct.pack("<I", 1))          # 1 = SIGHASH_ALL, the only type
    return tagged_hash(b"Blazecoin/PQSig/v1", preimage)

# ------------------------------------------------------------------ the rules
def is_p2pqh(spk): return len(spk) == 34 and spk[0] == 0x20 and spk[33] == OP_CHECKPQSIG

def verify_input(raw_tx, n_in, amount, spk):
    """"OK" or the node's error name for input n_in of raw_tx spending (amount, spk)."""
    if not is_p2pqh(spk): return "NOT_P2PQH"
    tx = parse_tx(raw_tx)
    stack = parse_pushes(tx["vin"][n_in]["scriptSig"])
    if stack is None: return "SIG_PUSHONLY"                       # 1. the scriptSig may only push data
    if any(len(e) > MAX_ELEMENT for e in stack): return "PUSH_SIZE"
    if len(stack) != 2: return "PQ_STACK_SIZE"                    # 2. exactly <sig> <keyblob>
    sig, keyblob = stack
    if tagged_hash(b"Blazecoin/PQKH/v1", keyblob) != spk[1:33]:   # 3. the key must be the one committed to
        return "PQ_KEYHASH_MISMATCH"
    if len(keyblob) == 0: return "PQ_PUBKEY_LENGTH"
    if keyblob[0] != ALGO_MLDSA44: return "PQ_ALGO_INACTIVE"      # 4. only algorithm 0x01 is active
    if len(keyblob) != 1 + PUBKEY_LEN: return "PQ_PUBKEY_LENGTH"
    if len(sig) != SIG_LEN: return "PQ_SIG_INVALID"               # 5. no sighash-type byte: the size is exact
    msg = sighash(tx, n_in, amount, spk)
    return "OK" if ML_DSA_44.verify(keyblob[1:], msg, sig, CTX_TX) else "PQ_SIG_INVALID"   # 6. FIPS 204 verify

# ------------------------------------------------------------------ self-check against the vector files
def main():
    here = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) == 5:
        print(verify_input(bytes.fromhex(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), bytes.fromhex(sys.argv[4])))
        return 0
    bad = checked = 0
    v = json.load(open(os.path.join(here, "pqsig_vectors.json"), encoding="utf-8"))
    for case in v["spend"]:
        if case["expect"] == "PRE_ACTIVATION": continue          # a rule about the fork height, not about the input
        raw = bytes.fromhex(v["sighash"][case["tx_ref"]]["tx"] if "tx_ref" in case else case["tx"])
        got = verify_input(raw, case["input"], case["amount"], bytes.fromhex(case["scriptPubKey"]))
        checked += 1
        if got != case["expect"]:
            bad += 1; print("MISMATCH", case["label"], "expected", case["expect"], "got", got)
    for t in v["sighash"]:                                       # digests, byte for byte
        tx = parse_tx(bytes.fromhex(t["tx"]))
        for i in t["inputs"]:
            checked += 1
            if sighash(tx, i["input"], i["amount"], bytes.fromhex(i["scriptCode"])).hex() != i["digest"]:
                bad += 1; print("DIGEST MISMATCH", t["label"], i["input"])
    print(f"pqsig_vectors.json: {checked} checks, {bad} mismatches")
    path = os.path.join(here, "mainnet_examples.json")
    if os.path.exists(path):
        for ex in json.load(open(path, encoding="utf-8"))["examples"]:
            raw = bytes.fromhex(ex["tx"])
            assert sha256d(raw)[::-1].hex() == ex["txid"], "txid"
            results = [verify_input(raw, n, p["amount"], bytes.fromhex(p["scriptPubKey"])) for n, p in enumerate(ex["prevouts"])]
            ok = sum(r == "OK" for r in results)
            bad += sum(r not in ("OK", "NOT_P2PQH") for r in results)
            print(f"mainnet {ex['txid'][:16]}... height {ex['block_height']}: {ok} of {len(results)} inputs are P2PQH and verify")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
