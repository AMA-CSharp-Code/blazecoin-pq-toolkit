# Node files the report relies on

Five files from the node's tree, copied here unchanged so the package is complete without it. The same files are
in the public node repository (`github.com/AMA-CSharp-Code/blazecoin-core`) from its commit `4634755` (17 November
2026), where they build. They are the benchmark behind REPORT.md section 5 and the known-answer tests and
fuzz targets of sections 9 and 11. They build only inside the node tree; nothing here compiles on its own.

Taken from the development tree at commit `0cfa378127` (2026-11-13); the public repository is a snapshot with its
own history, so look there for commit `4634755`, which contains the same files.

| File | SHA-256 | What it is |
|---|---|---|
| `src/bench/pq_verify.cpp` | `43e359aac66eac4ff5e1bfc7abd0eb5b712a322d88c11f430884086f41e13d27` | the benchmark: the eight cases named in the report's method line |
| `src/test/mldsa44_kat_tests.cpp` | `2f18ba7aff15c9612fad5d87621f2c0379816517f35f38d79b07ef67248dcdca` | the known-answer tests: 79 NIST ACVP cases for ML-DSA-44 |
| `src/test/mldsa44_acvp_data.h` | `4e33fe3bbf1f0c93ea61a06eb53478e852143ded258ff610f6bd9c58a2951f50` | the ACVP vectors those tests use (key generation 25, signature generation 24, signature verification 30) |
| `src/test/fuzz/pq_script.cpp` | `a2459b65c96d0d6b0198aed9b273ebe55c48bcdbf89d2ab83bbac437c6ffa619` | the three fuzz targets: `mldsa44`, `pq_sighash`, `pq_spend` |
| `test/pqsig/run_pq_fuzz_seeds.py` | `a881276681de16c248123be1a0591b4f65547529ed1712430fb7bdce689ef5fe` | generates a seed corpus (seeded random bytes, with structured prefixes) and runs the fuzz binary's file-input runner over it |

Check a copy here with `sha256sum <file>`. The public repository stores `pq_script.cpp` with Windows line endings, so
a raw download of that one file differs from this copy in line endings only. Licence: MIT, like the node (see the header of each file and LICENSE in this
repository).
