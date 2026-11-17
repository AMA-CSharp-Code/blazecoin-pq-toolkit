#!/usr/bin/env bash
# Run the unit-test suites the post-quantum witness port touches or could affect, one suite per line of output.
# Usage:  bash unit-tests.sh [tree]      (default tree: ~/ltc-pq)
set -u
TREE="${1:-$HOME/ltc-pq}"
BIN="$TREE/src/test/test_litecoin"
SUITES="pq_witness_tests script_tests transaction_tests sigopcount_tests txvalidation_tests txvalidationcache_tests
script_standard_tests script_p2sh_tests sighash_tests versionbits_tests multisig_tests miner_tests
validation_block_tests crypto_tests TestWeight TestPegInCoin TestPegOutCoin TestTransaction TestBlockValidator
TestMineChain TestReorg"
fail=0
for suite in $SUITES; do
    out="$("$BIN" --run_test="$suite" 2>&1)"
    code=$?
    cases="$(printf '%s\n' "$out" | grep -o 'Running [0-9]* test case[s]*' | head -1)"
    verdict="$(printf '%s\n' "$out" | grep -o 'No errors detected\|[0-9]* failure[s]* [a-z ]*detected' | head -1)"
    printf '%-28s exit=%d  %s  %s\n' "$suite" "$code" "$cases" "$verdict"
    if [ "$code" -ne 0 ]; then fail=1; printf '%s\n' "$out" | tail -15; fi
done
exit $fail
