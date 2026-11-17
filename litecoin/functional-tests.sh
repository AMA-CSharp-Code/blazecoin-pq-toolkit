#!/usr/bin/env bash
# Run the new functional test and the existing ones around segwit, Taproot, MWEB, deployments and relay policy.
# Usage:  bash functional-tests.sh [tree] [plain]      (default tree: ~/ltc-pq)
#
# Litecoin 0.21's test framework needs hashlib's ripemd160, which OpenSSL 3 (Ubuntu 22.04) switches off. Unless the
# second argument is "plain", the tests run with OPENSSL_CONF pointing at openssl-legacy.cnf (beside this script),
# which loads OpenSSL's legacy provider for these processes only.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
TREE="${1:-$HOME/ltc-pq}"
MODE="${2:-legacy}"
cd "$TREE" || exit 1
if [ "$MODE" != "plain" ]; then
    export OPENSSL_CONF="$HERE/openssl-legacy.cnf"
fi
python3 test/functional/test_runner.py --jobs=8 \
    feature_pq_witness.py \
    rpc_blockchain.py \
    "feature_segwit.py --legacy-wallet" \
    feature_taproot.py \
    p2p_segwit.py \
    mweb_basic.py \
    mweb_weight.py \
    mweb_mempool.py \
    mweb_mining.py \
    feature_versionbits_warning.py \
    mempool_accept.py \
    feature_block.py \
    rpc_rawtransaction.py
