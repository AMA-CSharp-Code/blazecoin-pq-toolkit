# Patent pledge

hyperminer, the author of this repository, and the Blazecoin project have not sought, and will not seek, patent protection on anything described in or embodied
by this repository or by Blazecoin Core (`github.com/AMA-CSharp-Code/blazecoin-core`): the P2PQH (pay to post-quantum key hash) output type,
its key blob and hash commitment, its signature digest and context binding, the activation mechanism, the wallet
behaviour described in the report, the test vectors, the verifier and the measurements. The pledge covers everything
else in this repository as well, including the soft-fork variant for legacy-script chains built on Dogecoin Core
(a redefined no-op opcode with the signature and key in canonical 520-byte chunks), the witness-program form built
on Bitcoin Core and Litecoin Core, the wallet-side migration pattern called the Blazecoin Quantum Bridge (the three
coin states, its five jobs and the triage tool), the counting queries and scripts, and the node files reproduced
here.

To the extent the author or the project holds or ever acquires any patent right that would be infringed by implementing, using, distributing or building upon anything described in or embodied by this repository or Blazecoin Core, each grants everyone an irrevocable, worldwide, royalty-free licence to do so. This pledge binds the author, the project and anyone either transfers such rights to.

The design is built on public standards and public prior work: CRYSTALS-Dilithium (2017), NIST FIPS 204
(August 2024), Bitcoin's pay-to-public-key-hash output pattern (2009) and scrypt proof of work (2011). The author and the project make no claim of invention over any of them and do not believe anything here is patentable by anyone.

This document is published as a dated record: the design and code have been public in the node repository
since September 2026 and live on the Blazecoin main chain since block 4,250,000 (16 September 2026, 20:18:58 UTC,
block `cfde5c01a0106e71f841b85be72bc66fbd2a4b78aac8abee3d039315fa19568f`).

hyperminer, personally and for the Blazecoin project. 17 November 2026
