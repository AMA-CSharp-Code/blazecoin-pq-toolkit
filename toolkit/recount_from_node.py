# -*- coding: utf-8 -*-
"""Recount the report's mainnet figures straight from a full node, without the block indexer.

Read-only: it calls getblockcount, getblockhash and getblock (verbosity 2) over the node's RPC and counts
  - post-quantum outputs created (the 34-byte template 0x20 <32-byte hash> 0xba) and the addresses they pay,
  - the inputs that spend them and the transactions that carry those inputs, with their total size,
  - transactions of consolidation shape (10 or more post-quantum inputs, at most 2 outputs),
  - post-quantum outputs funded from classic inputs only (coins moving from classic keys to post-quantum ones),
for blocks START to END inclusive. REPORT.md section 6 uses START 4250000 and END 4417513.

usage: python recount_from_node.py DATADIR [--port 55413] [--start 4250000] [--end 4417513]
DATADIR is the node's data directory; the script authenticates with its .cookie file, or with rpcuser and
rpcpassword from blazecoin.conf there, and prints neither. The node must not be pruned. Standard library only.
"""
import argparse
import base64
import collections
import datetime
import http.client
import json
import os
import time

ap = argparse.ArgumentParser()
ap.add_argument("datadir")
ap.add_argument("--port", type=int, default=55413)
ap.add_argument("--start", type=int, default=4250000)
ap.add_argument("--end", type=int, default=4417513)
args = ap.parse_args()


def auth_header():
    cookie = os.path.join(args.datadir, ".cookie")
    if os.path.exists(cookie):
        token = open(cookie, encoding="utf-8").read().strip()
    else:
        user = password = None
        for line in open(os.path.join(args.datadir, "blazecoin.conf"), encoding="utf-8", errors="replace"):
            line = line.strip()
            if line.startswith("rpcuser="):
                user = line.split("=", 1)[1]
            elif line.startswith("rpcpassword="):
                password = line.split("=", 1)[1]
        if not (user and password):
            raise SystemExit("no .cookie and no rpcuser/rpcpassword in blazecoin.conf")
        token = user + ":" + password
    return "Basic " + base64.b64encode(token.encode()).decode()


AUTH = auth_header()
conn = None


def rpc_batch(calls):
    """Send several calls in one request; return their results in order. Reconnects and retries on failure."""
    global conn
    body = json.dumps([{"jsonrpc": "1.0", "id": i, "method": m, "params": p} for i, (m, p) in enumerate(calls)])
    for attempt in range(5):
        try:
            if conn is None:
                conn = http.client.HTTPConnection("127.0.0.1", args.port, timeout=300)
            conn.request("POST", "/", body, {"Authorization": AUTH, "Content-Type": "application/json"})
            response = conn.getresponse()
            data = response.read()
            if response.status != 200:
                raise RuntimeError("HTTP %d" % response.status)
            results = sorted(json.loads(data), key=lambda r: r["id"])
            for r in results:
                if r.get("error"):
                    raise RuntimeError(str(r["error"]))
            return [r["result"] for r in results]
        except Exception:
            conn = None
            if attempt == 4:
                raise
            time.sleep(2 + attempt * 3)


def is_post_quantum(script_hex):
    return len(script_hex) == 68 and script_hex.startswith("20") and script_hex.endswith("ba")


if rpc_batch([("getblockcount", [])])[0] < args.end:
    raise SystemExit("the node's tip is below --end")

unspent = set()                 # (txid, n) of every post-quantum output created in the range and not yet spent
count = collections.Counter()
addresses, classic_funded_addresses = set(), set()
by_month = collections.Counter()
first_output_height = first_spend_height = None
BATCH = 40
for base in range(args.start, args.end + 1, BATCH):
    heights = list(range(base, min(base + BATCH, args.end + 1)))
    hashes = rpc_batch([("getblockhash", [h]) for h in heights])
    for height, block in zip(heights, rpc_batch([("getblock", [h, 2]) for h in hashes])):
        month = datetime.datetime.fromtimestamp(block["time"], datetime.timezone.utc).strftime("%Y-%m")
        for position, tx in enumerate(block["tx"]):
            spent_here = 0
            for vin in tx["vin"]:
                key = (vin.get("txid"), vin.get("vout"))
                if key in unspent:
                    unspent.remove(key)
                    spent_here += 1
            created = [(v["n"], v["scriptPubKey"].get("address") or v["scriptPubKey"]["hex"])
                       for v in tx["vout"] if is_post_quantum(v["scriptPubKey"]["hex"])]
            for n, address in created:
                unspent.add((tx["txid"], n))
                addresses.add(address)
            if created:
                count["post-quantum outputs created"] += len(created)
                by_month[month] += len(created)
                if first_output_height is None:
                    first_output_height = height
                if position == 0:
                    count["  of which in coinbase transactions"] += len(created)
                elif spent_here == 0:
                    count["  of which funded from classic inputs only"] += len(created)
                    classic_funded_addresses.update(a for _, a in created)
                else:
                    count["  of which funded by a transaction with post-quantum inputs"] += len(created)
            if spent_here:
                count["post-quantum inputs spent"] += spent_here
                count["transactions spending post-quantum inputs"] += 1
                count["  their total size in bytes"] += tx["size"]
                if first_spend_height is None:
                    first_spend_height = height
                if spent_here >= 10 and len(tx["vout"]) <= 2:
                    count["  of consolidation shape (10+ inputs, at most 2 outputs)"] += 1
                    count["    post-quantum inputs in those"] += spent_here
        if height == args.end:
            end_time = block["time"]

print("blocks %d to %d (end block time %s UTC)" % (args.start, args.end,
      datetime.datetime.fromtimestamp(end_time, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")))
for k, v in count.items():
    print("%-62s %d" % (k, v))
print("%-62s %d" % ("distinct post-quantum addresses", len(addresses)))
print("%-62s %d" % ("addresses funded from classic inputs only", len(classic_funded_addresses)))
print("%-62s %d" % ("post-quantum outputs still unspent at the end block", len(unspent)))
print("%-62s %s" % ("first post-quantum output at block", first_output_height))
print("%-62s %s" % ("first post-quantum spend at block", first_spend_height))
print("created by month: " + ", ".join("%s %d" % kv for kv in sorted(by_month.items())))
