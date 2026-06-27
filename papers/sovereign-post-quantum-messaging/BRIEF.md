# Built to Outlive the Algorithm: Hybrid Post-Quantum Cryptography and Crypto-Agility in a Sovereign Messaging Stack

## One-Line Summary
We migrated a sovereign messaging stack (skchat/skcomms/capauth) to hybrid post-quantum crypto — surface by surface, secure-if-either-leg-holds — but the real contribution is the *scaffolding*: self-describing crypto suites + pluggable backends + a self-report that refuses to overclaim, so the next quantum algorithm plugs in without rewriting the apps.

## The Core Finding
- **The threat is harvest-now-decrypt-later, not Q-Day.** Mosca's Inequality: for 10–20-year secrets, `X(secrecy) + Y(migrate) > Z(years-to-CRQC)` *today*. So **confidentiality** (retroactively breakable) is migrated first; **signatures/identity** (forgery only, not retroactive) are a deliberate Phase 2; **symmetric** (AES-256/SHA-2) is already fine and we refuse to fear-monger it.
- **One hybrid construction, everywhere.** `HKDF-SHA256(X25519_ss ‖ ML-KEM-768_ss)` — concatenate-then-KDF, never XOR, never pure-PQ — secure if *either* leg holds. The same `x25519-mlkem768` (FIPS 203) used by TLS and Signal PQXDH. We never hand-roll the math (liboqs / noble / pyca); a missing PQ backend is a *loud error*, never a silent downgrade.
- **Surface by surface:** hybrid KEM; `pqdm1:` DM/envelope sealing with a downgrade-lock AAD; a **per-epoch group ratchet** (FS + PCS) that kills the static `os.urandom(32)` group key — the highest-leverage HNDL bug; hybrid at-rest key-wrap; an Ed25519+ML-DSA-65 **AND-gate** signature; and a Sequoia-issued **post-quantum signing root** (v6 ML-DSA-87+Ed448) for the Lumina *agent* root — **generated + cross-signed old↔new (WoT-verified)**. *Cryptographic ceremony complete; the live signing cutover is in progress (gated on PGPy→`sk_pgp`); operator root + vault re-seal sequenced after — the live identity is NOT yet migrated.*
- **Two sovereign libraries:** **`sk_pqc`** — the hybrid KEM, **now published across Python, Dart, and Rust behind one wire format** (`pip install sk-pqc` / `dart pub add sk_pqc` / `cargo add sk-pqc`; repos `sk-pqc-{py,dart,rs}`); the Dart package delivers hybrid PQC **in the browser** (where no WebCrypto PQC API exists), CDP-verified in-page DMs. Experimental & unaudited. **`sk_pgp`** (Python, PyO3→Sequoia) — the **PGPy replacement** and the *engine* that lets the Python services sign with v6/PQC keys at all (PGPy can't parse v6, gpg can't sign PQC); in-process ML-DSA-87+Ed448 generate/sign/verify proven, self-contained wheel.
- **The thesis — crypto-agility:** a `suite_id` on every object, a `CryptoBackend` ABC (PGPy/GnuPG/Sequoia-CLI/`sk_pgp`), KEM selected `by suite id`, and a 4-step recipe (register suite → add backend → bump wire version → negotiate) to adopt the next scheme **with zero app changes**. Our infra rides on top of whatever comes next.
- **Honesty as a feature:** a self-report engine (`pqc_report.py`) that *structurally cannot* mark a surface quantum-resistant unless its live suite is — unknown suites resolve classical, a downgrade shows up classical, and the root is reported classical until the day it isn't.

## Method / Evidence
- Real constructions, real sizes, real vectors: a cross-impl KEM vector anchored to **NIST ACVP FIPS 203**; bidirectional Python↔Dart DM interop; the **agent-root ceremony run on a real key** (v6 `mldsa87-ed448` generated + cross-signed old↔new, continuity verified); `sk_pgp` in-process ML-DSA-87+Ed448 gen/sign/verify; ~68 PQ pytest functions + Dart KATs.
- Honest scope: confidentiality is **hybrid where negotiated**; signatures/identity are **hybrid-available, opt-in**; the agent-root **cryptographic ceremony is complete but the live identity is NOT yet migrated** (cutover in progress, gated on PGPy→`sk_pgp`; operator root + vault re-seal after); the comms tier is deliberately **-768, not CNSA-2.0**. No "quantum-proof" claim is made anywhere.

## Conclusion
The durable win is not ML-KEM-768 or ML-DSA-65 — it is an infrastructure where the choice of post-quantum scheme is a registry entry and a pluggable backend, every object self-describes what protects it, and overclaiming is structurally impossible. Built to outlive the algorithm.

## Status
- Technical report: June 2026
- Part of the `PQC-MIGRATION` program (skchat / skcomms / capauth / sksecurity)
- Libraries: `sk_pqc` (hybrid KEM, one wire format across Python/Dart/Rust, Apache-2.0) — **published**: `pip install sk-pqc` (sk-pqc-py) · `dart pub add sk_pqc` (sk-pqc-dart) · `cargo add sk-pqc` (sk-pqc-rs) · live at skpqc.skworld.io; `sk_pgp` (Python OpenPGP-PQC, PyO3→Sequoia, Apache-2.0) · github.com/smilinTux/sk_pgp
- Published: skresearch.skworld.io
