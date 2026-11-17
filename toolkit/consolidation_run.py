# -*- coding: utf-8 -*-
# Read-only: every consolidation transaction of a wallet (sends to its own addresses
# under the given label, which the wallet's Consolidate tool applies), grouped by destination address = by round.
# Reports inputs, outputs, bytes, fees, sizes and the block span, then how full each block of the first round was.
# Prints no full addresses.
#
# usage: python consolidation_run.py <path to blazecoin-cli> <datadir> <wallet name> [label]
import collections
import json
import subprocess
import sys

CLI, DATADIR, WALLET = sys.argv[1], sys.argv[2], sys.argv[3]
LABEL = sys.argv[4] if len(sys.argv) > 4 else "consolidated"
NODE = [CLI, "-datadir=" + DATADIR]
BASE = NODE + ["-rpcwallet=" + WALLET]


def rpc(*args, base=BASE):
    out = subprocess.run(base + list(args), capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit("rpc %s failed: %s" % (args[0], out.stderr.strip()[:200]))
    s = out.stdout.strip()
    return json.loads(s) if s[:1] in "[{" else s


dests = list(rpc("getaddressesbylabel", LABEL).keys())
print("consolidation addresses:", len(dests))
seen = {}
for t in rpc("listtransactions", "*", "5000", "0"):
    if t.get("category") == "send" and t.get("address") in dests:
        seen.setdefault(t["txid"], t)
print("consolidation transactions:", len(seen))

rounds = collections.defaultdict(list)
for txid, t in seen.items():
    g = rpc("gettransaction", txid, "true", "true")
    d = g["decoded"]
    rounds[t["address"]].append({
        "ins": len(d["vin"]), "outs": len(d["vout"]), "size": d["size"], "fee": -g.get("fee", 0.0),
        "height": g.get("blockheight"), "time": g.get("blocktime")})

ordered = sorted(rounds.items(), key=lambda kv: min(r["height"] or 10 ** 9 for r in kv[1]))
for n, (addr, rows) in enumerate(ordered, 1):
    hs = sorted(r["height"] for r in rows if r["height"])
    print("\nround %d: %d transactions" % (n, len(rows)))
    print("  inputs merged %d, outputs %d, bytes %d, fee %.6f" % (
        sum(r["ins"] for r in rows), sum(r["outs"] for r in rows), sum(r["size"] for r in rows),
        sum(r["fee"] for r in rows)))
    print("  inputs per transaction:", dict(sorted(collections.Counter(r["ins"] for r in rows).items())))
    print("  transaction sizes:", dict(sorted(collections.Counter(r["size"] for r in rows).items())))
    if hs:
        per = collections.Counter(hs)
        print("  blocks %d to %d, %d blocks used, at most %d of these transactions in one block" % (
            hs[0], hs[-1], len(per), max(per.values())))

if ordered:
    hs = sorted(r["height"] for r in ordered[0][1] if r["height"])
    fill = []
    for h in range(hs[0], hs[-1] + 1):
        b = json.loads(subprocess.run(NODE + ["getblock", rpc("getblockhash", str(h), base=NODE), "1"],
                                      capture_output=True, text=True).stdout)
        fill.append(b["size"])
    print("\nfirst round, block sizes: %d blocks, %d over 900,000 bytes, smallest %d, largest %d" % (
        len(fill), sum(1 for s in fill if s > 900000), min(fill), max(fill)))
