#!/usr/bin/env python3
"""Fetch real mainnet transactions that spend P2PQH inputs, with the prevout of every input, into
mainnet_examples.json. Needs a local Blazecoin node (cookie auth).

    python fetch_mainnet_examples.py <datadir> <rpcport> <label>=<txid>@<blockhash> [...]
"""
import base64, json, os, sys, urllib.request

datadir, port = sys.argv[1], int(sys.argv[2])
cookie = open(os.path.join(datadir, ".cookie")).read().strip()
auth = "Basic " + base64.b64encode(cookie.encode()).decode()

def rpc(method, *params):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/", json.dumps({"jsonrpc": "1.0", "id": 1, "method": method, "params": list(params)}).encode(),
                                 {"Authorization": auth, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())["result"]

out = {"_comment": "Real Blazecoin mainnet transactions spending P2PQH (ML-DSA-44) inputs, each with the amount and scriptPubKey "
                   "of every prevout. Every PQ input must verify under verify_p2pqh.py.", "examples": []}
for arg in sys.argv[3:]:
    label, rest = arg.split("=", 1)
    txid, blockhash = rest.split("@")
    tx = rpc("getrawtransaction", txid, 2, blockhash)
    header = rpc("getblockheader", blockhash)
    out["examples"].append({
        "label": label, "txid": txid, "block_height": header["height"], "block_hash": blockhash, "block_time": header["time"],
        "size": tx["size"], "tx": tx["hex"],
        "prevouts": [{"amount": round(i["prevout"]["value"] * 100_000_000), "scriptPubKey": i["prevout"]["scriptPubKey"]["hex"]} for i in tx["vin"]],
    })
    print(label, txid, "height", header["height"], "inputs", len(tx["vin"]), "size", tx["size"])
with open("mainnet_examples.json", "w", newline="\n") as f:
    json.dump(out, f, indent=1)
