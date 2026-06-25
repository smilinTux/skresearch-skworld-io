# Built to Outlive the Algorithm: Hybrid Post-Quantum Cryptography and Crypto-Agility in a Sovereign Messaging Stack

**SKWorld Research · skpqc · skchat · skcomms · capauth**
*Draft — June 2026 · Apache-2.0 library at [github.com/smilinTux/sk_pqc](https://github.com/smilinTux/sk_pqc) · live at [skpqc.skworld.io](https://skpqc.skworld.io)*

---

## Abstract

The quantum threat to messaging is not that a quantum computer will read your messages tomorrow — it is that an adversary can **record your ciphertext today** and decrypt it years later, once a cryptographically-relevant quantum computer (CRQC) exists. For data with a long secrecy life — agent memories, private conversations, a sovereign identity root — that "harvest-now, decrypt-later" (HNDL) window is already open. This paper describes how the SKWorld stack (the `skchat`/`skcomms` messaging framework and the `capauth` identity layer) was migrated to **hybrid post-quantum cryptography**, surface by surface, behind a single design commitment: **never bet the system on one algorithm, and never overclaim what it provides.**

We make three contributions. First, a **uniform hybrid construction** — `X25519 + ML-KEM-768` combined with HKDF, secure if *either* the classical or the post-quantum leg holds — applied consistently across key exchange, group keys, at-rest wrapping, and (as a signature analogue) per-message authentication. Second, the **`sk_pqc` library**: one Dart/Flutter API delivering that hybrid KEM across web and native, so post-quantum DMs negotiate **in the browser** where no WebCrypto PQC API exists. Third, and most importantly, the **crypto-agility scaffolding**: every encrypted or signed object carries a self-describing *suite id*, every primitive sits behind a pluggable backend selected *by id*, and a four-step recipe lets the next quantum scheme — a higher NIST tier, a hash-based root, a backup KEM — plug in **without rewriting a single application call site**. The migration is governed by a **self-report engine** that structurally refuses to call any surface "quantum-resistant" unless its live suite actually is. We are explicit about what is done (confidentiality is hybrid where negotiated), what is in progress (signatures and identity are hybrid-*available*, opt-in), and what is deliberately *not* claimed (the sovereign root key is still classical; the comms tier is `-768`, not CNSA-2.0). The thesis is in the title: when the next quantum solution arrives, our infrastructure rides on top of it.

---

## 1. Introduction

Most "post-quantum" announcements answer the wrong question. They ask *"is it broken yet?"* — and since no CRQC exists in 2026, the honest answer is "no," which invites complacency. The right question is **Mosca's Inequality**: if `X` (how long your secret must stay secret) plus `Y` (how long migration takes) exceeds `Z` (years until a CRQC), you are already too late. Independent expert surveys put a CRQC in the **early-to-mid 2030s** — the 2025 Global Risk Institute survey reports a 28–49% chance within a decade. For a 10-to-20-year secret, `X + Y > Z` *today*. The urgency is real, but it is the urgency of *recording*, not of imminent decryption — and conflating the two is the first dishonesty we refuse.

This reframing has a sharp consequence for *what to migrate first*. **Confidentiality is retroactively breakable; signatures are not.** A forged future handshake cannot decrypt a past recorded session, so key-exchange and key-wrapping are the HNDL-urgent surfaces, while identity and authentication — important, but not retroactively exploitable — are a deliberate second phase. Symmetric cryptography (AES-256, SHA-2) is a third category entirely: Grover's algorithm only halves its effective strength, leaving AES-256 at ~128 bits. Touching it would be a *regression*, and we say so plainly rather than ride the marketing wave of "quantum-proof AES."

The deeper problem, though, is not any single algorithm — it is **lock-in**. Lattice cryptography is young. ML-KEM and ML-DSA are the NIST choices today; HQC was added as a backup KEM; FN-DSA (Falcon) is still draft. A system that hard-codes one scheme into its message formats and call sites will face the same painful, error-prone migration *again* when the landscape shifts. So the engineering question we actually set out to answer was not *"which post-quantum algorithm?"* but **"how do we build a stack that can change its mind?"** The answer — self-describing crypto suites, pluggable backends, hybrid-by-construction, and a self-report that cannot lie — is the subject of this paper.

---

## 2. The Threat, Precisely

### 2.1 Shor versus the primitives we shipped

Every *asymmetric* primitive the stack used is broken by Shor's algorithm on a CRQC:

| Primitive | Where it lived | Quantum status |
|---|---|---|
| **X25519 / Curve25519** (RFC 7748) | envelope key-wrap, DM wrap, ephemeral KEX, tailnet Noise | 🔴 Shor (discrete log) |
| **Ed25519** (RFC 8032) | message signatures, capauth challenge/DID, root PGP signing | 🔴 Shor (forgery — *not* HNDL) |
| **RSA-4096** (RFC 8017) | legacy identity + key-wrap | 🔴 Shor (factoring) |

### 2.2 The HNDL distinction that orders the work

The 🔴 entries split cleanly. Where a primitive protects **confidentiality**, a recording made today is a liability forever — that is HNDL, and it is urgent. Where a primitive provides **authentication**, breaking it lets an attacker forge a *future* message, but it does nothing to a *past* ciphertext. We therefore migrated in HNDL-priority order: **(1)** key exchange, **(2)** at-rest key-wrap, **(3)** long-lived identity roots, **(4)** routine signatures, **(5)** transport/media.

### 2.3 The vulnerable surfaces (an honest inventory)

A pre-migration audit enumerated eleven surfaces. The highest-leverage was the **group key**: a single static 32-byte group secret, PGP-wrapped per member. Break *one* member's classical key and you recover the AES key for the **entire group's history** — maximum HNDL leverage. Close behind: envelope/DM payload encryption (classical key-wrap of AES-256), at-rest stores and backups (prime harvest targets), and the **sovereign identity root** (a long-lived Ed25519/RSA key whose public half is *published by design* in a DID document). Each got a hybrid path; each is tracked, by name, in the self-report.

### 2.4 What we did *not* touch

AES-256-GCM, ChaCha20-Poly1305, SHA-256/384, HKDF. These are Grover-only and remain ≥128-bit secure. The plan explicitly forbids "fear-based AES messaging." The one watch-item is parameter hygiene — making sure no AES-128 sneaks into a DTLS-SRTP media profile — not the bulk cipher itself.

---

## 3. One Construction to Rule Them All

The single cryptographic primitive the project *owns* is a hybrid combiner. Everything else composes it:

```
shared_secret = HKDF-SHA256( IKM  = X25519_ss ‖ ML-KEM-768_ss,   // X25519 first
                             salt = "",                          // RFC 5869 → zeros
                             info = "<context label>",
                             L    = 32 )
```

**Concatenate-then-KDF. Never XOR. Never pure-PQ.** The derived secret is secure if *either* X25519 *or* ML-KEM-768 holds: a future quantum break of X25519 still leaves ML-KEM-768; a catastrophic lattice break still leaves classical X25519. This is the same construction shipping in TLS 1.3 as `X25519MLKEM768` and in Signal's PQXDH — deliberately, so our security argument inherits theirs.

Two rules make the construction trustworthy. First, **we never hand-roll the lattice or curve math**: ML-KEM is liboqs (`oqs`); X25519 and HKDF are pyca `cryptography` on the server and `package:cryptography` in Dart; the web ML-KEM leg is the audited `@noble/post-quantum`. The *only* original cryptographic code in the whole library is the HKDF combiner and the wire framing — and both are pinned to known-answer test vectors. Second, **a missing post-quantum backend is a loud error, never a silent downgrade**: if liboqs is absent the code raises `PqKemUnavailable` rather than quietly falling back to classical-only. You cannot accidentally ship the weaker thing.

---

## 4. Surface by Surface

### 4.1 Key exchange — `x25519-mlkem768`

The hybrid KEM (`skcomms/pqkem.py`; `sk_pqc` in Dart) pairs an ephemeral-static X25519 DH (HPKE/TLS-style) with FIPS 203 ML-KEM-768 and the combiner above. The wire contract is fixed: a **1216-byte** public key (`X25519(32) ‖ ML-KEM(1184)`), a **1120-byte** ciphertext (`eph_X25519(32) ‖ ML-KEM(1088)`), a **32-byte** shared secret. ML-KEM decapsulation uses FIPS 203 *implicit rejection* — a tampered ciphertext yields a pseudo-random secret that simply won't match, rather than an oracle-leaking error. A canonical cross-implementation vector anchors the ML-KEM leg to the **NIST ACVP FIPS 203** keyGen seed (tcId 26); every conformant backend — Dart native, Dart web, liboqs, noble, Python — must recover the same hybrid secret `f11627…21fc`.

### 4.2 Direct messages and envelopes — the `pqdm1:` scheme

One sealing construction (`skcomms/pqdm.py`) serves both the `skcomms` envelope payload and the `skchat` 1:1 DM body. It is a **PQXDH-style** handshake: a recipient publishes a signed hybrid-KEM **prekey**; a sender who sees it encapsulates, derives an AES-256 wrap key via HKDF, and AES-256-GCM-seals the body. The ~1.1 KB KEM ciphertext rides in the first message. On the wire the blob is `ct(1120) ‖ nonce(12) ‖ AES-256-GCM(body)`, stored under a self-identifying **`pqdm1:x25519-mlkem768:`** prefix.

The subtle part is **downgrade resistance**. A canonical, sorted-JSON AAD binds the *negotiated suite* and both parties into the AEAD (and is also folded into the HKDF `info`). A man-in-the-middle who strips the hybrid prekey to force a classical fallback changes the suite the sender seals under — so the recipient's AES-GCM open fails *and* the recorded suite flips to classical, where the self-report surfaces it. The lock is the AAD binding; the *detection* is the honesty engine. Hybrid is selected only when **both** sides advertise it; classical-only peers keep a byte-for-byte classical path, recorded honestly as such.

### 4.3 Group keys — a per-epoch ratchet

The marquee HNDL fix. The static `os.urandom(32)` group key is replaced by a **two-layer epoch ratchet** (`skchat/group_ratchet.py`). Once per epoch, an epoch secret is distributed to each member via the hybrid KEM (the 1.1 KB ML-KEM ciphertext is paid **once per epoch, not per message** — avoiding ~33× per-message bloat). Within an epoch, message keys are derived by a symmetric HKDF ratchet **indexed directly** — `message_key(i) = HKDF(epoch_secret, …, "/", u64(i))` — so a receiver derives key *i* without seeing 0…i-1, making it fully loss- and reorder-tolerant over an unreliable transport. Re-keying on membership change buys **forward secrecy** (a removed member cannot derive future epochs) and **post-compromise security** (a leaked epoch secret exposes only that epoch). Bound: 50 messages or 7 days.

### 4.4 At-rest — hybrid key-wrap (and a classical bug fixed in passing)

At-rest stores (`skchat/atrest_wrap.py`) now wrap a **high-entropy random** data-encryption key under hybrid X25519+ML-KEM-768, with AES-256-GCM as the bulk cipher. This shipped alongside a *classical* fix worth noting: the DEK had been HKDF-derived from the PGP **fingerprint** — low-entropy and often public. Migrating to post-quantum was the occasion to also stop deriving a key from a public value. A harvested backup is no longer retroactively decryptable; legacy stores remain readable through a versioned fallback.

### 4.5 Per-message signatures — the hybrid AND-gate

Authentication is a different problem with a dual construction. Where the KEM combiner is confidential if *either* secret survives, a hybrid **signature** (`skcomms/pqsig.py`, suite `mldsa65-ed25519-v2`) is valid **iff *both* Ed25519 *and* ML-DSA-65 verify** over the same bytes — an AND-gate. An adversary who forges one scheme still fails the other leg, so the composite is unforgeable while *either* remains secure. The `SKHS` wire format is versioned, length-prefixed, and suite-tagged (a 3383-byte composite today), and the ML-DSA signing key is generated **separately from, and never derived from, the PGP identity key**. Verification routes to the hybrid path only when an object's `sig_suite` says so and both public keys are present; classical objects are byte-for-byte unchanged. This mirrors the OpenPGP PQC composite (draft alg 30).

### 4.6 Identity challenges — additive, either-or

At the DID/challenge layer (`capauth/pqc_identity.py`), a responder produces the classical PGP signature *exactly as before* **and** attaches a hybrid composite over the same challenge bytes. Verification is *either-or* during transition (classical-only responses still verify), with a `require_hybrid` switch that blocks downgrade once a peer is known PQ-capable. Crucially, this is the *challenge-signing* layer — it does **not** migrate the root key.

### 4.7 The sovereign root — built, proven, and deliberately not yet pulled

The identity **root** is the highest-value, longest-lived secret, and the hardest to migrate — because no mainstream tool could host a post-quantum *signing* root. GnuPG's PQC support is **encryption-only** (ML-KEM); it cannot certify with ML-DSA or SLH-DSA. We therefore built a **Sequoia** backend (`capauth/crypto/sequoia_backend.py`) on `sq 1.4.0-pqc` against OpenSSL 3.6.2, behind the same `CryptoBackend` interface as the classical backends. It can issue an **ML-DSA-87 + Ed448** signing primary with an **ML-KEM-1024 + X448** encryption subkey (NIST level 5, OpenPGP v6 / RFC 9580), sign with a passphrase-protected key with no plaintext key ever on disk, and *additively* attach reversible PQC subkeys to an existing key with its primary fingerprint preserved.

And then we **stopped**. Post-quantum keys are OpenPGP v6, whose fingerprints are 64 hex characters, not 40 — so we reconciled ~36 assumption sites across the resolver, services, and integrations to accept both (additively; classical still works). We validated the full rotation-and-cross-sign ceremony **end-to-end on throwaway keys** (`pqc_ceremony_dryrun.py` — generate, cross-sign both directions, verify continuity, attach an additive subkey, all passing in an isolated keystore). But the **live sovereign root remains classical and v4.** Rotating a real root of trust is a deliberate, owner-driven ceremony, not an automated commit — and our self-report says, on every line that touches it, that the root is *still classical*. The capability is proven; the act is reserved.

### 4.8 `sk_pqc` — hybrid post-quantum in the browser

A messaging stack lives where its clients run, and ours run on the web — where, as of 2026, **no browser exposes a WebCrypto PQC API**. The `sk_pqc` library (Dart/Flutter, Apache-2.0, public) delivers the `x25519-mlkem768` hybrid KEM behind **one API with two backends**, chosen by conditional import: native via `dart:ffi` → liboqs, web via `dart:js_interop` → the audited `@noble/post-quantum`. The Flutter client ships a Dart `PqDmCodec` that is a byte-for-byte mirror of the server's `pqdm.py`, so a chat between the app and the in-house agent negotiates **hybrid post-quantum DMs in-page**, and a cross-implementation interop gate confirms Python-sealed messages open in Dart and vice-versa. The library is honest in its own README about exactly what it is: a *hybrid* KEM at the **-768 tier**, KEM-only (signatures are future work), "post-quantum," never "quantum-proof."

---

## 5. The Scaffolding: Built to Outlive the Algorithm

This is the thesis. Each surface above is valuable, but any of them could be rebuilt on a different algorithm in a year — and a stack that hard-codes its choices would pay the full migration cost *again*. We refused to. NIST's own crypto-agility guidance (CSWP 39, December 2025) names the pattern: separate **policy** (which algorithm) from **mechanism** (the call site), keep an inventory, and measure agility maturity. Our infrastructure is built so that *which algorithm* is configuration, not code.

**Every object self-describes its suite.** A single registry (`skcomms/crypto_suites.py`) maps a `suite_id` to its kind, status, primitives, and FIPS references. Its initial release added *no algorithms at all* — pure scaffolding — and its status vocabulary is deliberately four honest states (`classical` / `hybrid-pq` / `pq` / `symmetric`), never "quantum-safe." Planned suites (a level-5 KEM, an SLH-DSA root) sit in the registry **inactive** until their implementation lands, so the self-report cannot describe vaporware. On the wire, a `SignedEnvelope` carries its `sig_suite`, a group carries its `kem_suite` and `epoch`, an identity carries its `Algorithm`, a conversation carries its `negotiated_suite`. **Deserialize an object from a year ago and it still parses — and is correctly described as classical.**

**Every primitive sits behind a pluggable backend selected by id.** Identity flows through a `CryptoBackend` interface with three interchangeable implementations (PGPy, GnuPG, Sequoia) — swapping the post-quantum signing root in was a *new backend*, not a rewrite. The KEM flows through `get_kem_backend(suite_id)`, which selects *by id only*; no caller branches on a concrete class. `sk_pqc`'s web and native ML-KEM providers sit behind one Dart API the same way.

So **how does the next quantum scheme plug in?** Four steps, no application changes:

1. **Register** a new `CryptoSuite` (id, status, primitives, FIPS refs) — `active = false` until proven.
2. **Add a backend** behind the existing interface, registered *by suite id* (a new KEM backend, a new signing `CryptoBackend`, a new ML-KEM provider in `sk_pqc`).
3. **Bump a wire version** — the `pqdm` and `SKHS` formats are versioned and length-prefixed precisely so a new variant carries a new tag without breaking old parsers.
4. **Negotiate** the new suite through the prekey / `sig_suite` machinery already in place; the self-report describes it once its registry entry goes active.

The applications never change. They read the negotiated suite and route by id. When a higher NIST tier, a hash-based root, or an entirely new family becomes the right answer, that answer is a registry entry and a backend class — and the infrastructure rides on top of it. That is what "built to outlive the algorithm" means.

---

## 6. The Honesty Engine

A migration this large invites overclaiming, and overclaiming in cryptography is its own vulnerability — it tells users they are safe where they are not. So the migration is governed by a structural rule: **no external quantum-resistance claim may be made unless it maps to a line in the self-report** (`sksecurity/pqc_report.py`).

The report is **per-object, not aspirational**. A default report describes the conservative (classical) posture; a *live* report reflects the operator's actual objects. A specific group, conversation, store, envelope, or challenge is described by its *real* suite — so a silent-downgrade attempt appears as a **classical** line, not a hybrid one. The group-key surface is marked hybrid **only when every group is hybrid**; while any remains classical it reads "hybrid-pq for X/N groups." An **unknown suite id resolves as classical** — the engine has no path to call something quantum-resistant unless the registry says so *and* the suite is active.

The forbidden-claims discipline is explicit and enforced: never "quantum-proof" / "unbreakable" / "quantum-safe" (the defensible words are *quantum-resistant* / *post-quantum*); never "end-to-end quantum-resistant" while any leg is classical; never "PQC" when only signatures migrated (it does nothing for HNDL); never "CNSA-2.0 compliant" (we deliberately run the `-768` tier, not the level-5 ceiling); never imply AES-256 is "broken." Every claim must cite **surface + FIPS number + hybrid-vs-classical**. Progress is recorded in an append-only ledger — narrative plus machine-readable snapshots — so the trajectory is reconstructable from data, not memory. *A system that refuses to overclaim is itself a feature.*

---

## 7. Where This Sits

Our hybrid choice is not idiosyncratic — it is the deployed consensus, and we adopted it deliberately so our security argument inherits the field's scrutiny.

In August 2024 NIST finalized the three standards this work builds on: **FIPS 203** (ML-KEM, key encapsulation, from CRYSTALS-Kyber), **FIPS 204** (ML-DSA, signatures, from Dilithium), and **FIPS 205** (SLH-DSA, hash-based signatures, from SPHINCS+) [1, 2]. NIST's own framing is a model of calibrated language — ML-KEM is *"believed to be secure, even against adversaries who possess a quantum computer,"* not "proven" or "quantum-proof" [1] — and it names **ML-KEM-768 as the recommended default** [1], the exact parameter set in the TLS 1.3 `X25519MLKEM768` hybrid group [3] and in our `x25519-mlkem768` suite.

The two leading production messengers validate both our construction and our *scoping*. **Signal's PQXDH** (2023) upgrades the X3DH handshake by combining X25519 with a post-quantum KEM (CRYSTALS-Kyber-1024) inside a single KDF so that "any attacker must break both" — the canonical secure-if-either-holds combiner, independently formally verified at USENIX Security 2024 [4, 5]. **Apple's iMessage PQ3** (2024) goes further to "Level 3," layering a periodic post-quantum rekeying ratchet on top of an ML-KEM-1024 + P-256 initialization, in a *purely additive* hybrid "where defeating PQ3 requires defeating both," with a machine-checked TAMARIN proof from ETH Zürich at USENIX Security 2025 [6, 7, 8].

The part that matters most for us: **both protocols ship post-quantum confidentiality but keep authentication classical — on purpose, and they say so plainly.** PQXDH states that "authentication in PQXDH is not quantum-secure" because "post-quantum secure deniable mutual authentication is an open research problem" [5]; PQ3 retains ECDSA-P256 sender authentication "because these mechanisms can't be attacked retroactively with future quantum computers" [6, 7]. That is *exactly* the HNDL-ordering of Section 2 — confidentiality is urgent, authentication is a scoped Phase 2 — which means our phased posture is the industry consensus, not a shortcut. Where we differ:

- **Breadth across surfaces.** PQ3 and PQXDH harden the key agreement of a single transport; we applied the same hybrid construction across KEM, **group** keys, **at-rest** wrapping, and per-message **signatures**, each independently negotiated and independently reported.
- **A post-quantum signing root, where the tooling barely exists.** Both big messengers leave identity classical for now; we *built* (without yet pulling) a post-quantum **signing root** via Sequoia [9] — something most OpenPGP tooling cannot do at all, because GnuPG's PQC support is encryption-only and the post-quantum OpenPGP composites [10] are only now emerging.
- **Sovereign and in-browser.** This runs on self-hosted infrastructure with no platform vendor, and delivers hybrid PQC in the web client despite the absence of any browser PQC API.
- **Agility and honesty as artifacts.** The contribution is less any one algorithm than the scaffolding and the self-report — designed for the migration *after* this one, and written to match NIST's calibrated "believed secure" rather than the "quantum-proof" snake-oil the field is right to warn against [11].

The open problems we share with everyone are real. Post-quantum **group/federated** messaging is still maturing — Signal is itself extending to a post-quantum "Triple Ratchet" (SPQR) for *ongoing-message* PQ security [12], and the IETF's MLS and the Matrix community are actively working group PQC [13]. Post-quantum **transport** below the application (WireGuard's Noise, WebRTC's DTLS) lacks crypto-agility and waits on upstreams. And the OpenPGP PQC composites we use for identity ride a **pre-RFC draft** [10] whose code points can still move — which is exactly why we keep them additive and reversible.

---

## 8. Evidence

- **Cross-implementation KEM vector** anchored to NIST ACVP FIPS 203 keyGen; recovered identically by Dart (native + web), liboqs, noble, and Python.
- **Bidirectional DM interop**: Python-sealed `pqdm` opens in the Dart `PqDmCodec` and vice-versa, gated by recorded vectors.
- **Hybrid DMs live in the browser** (CDP-verified): app ↔ agent negotiate `pqdm1:x25519-mlkem768:` in-page via web ML-KEM-768.
- **Live migration**: of 422 groups, the first batch migrated hybrid with zero failures; the operator's at-rest store is hybrid-wrapped. (Most groups remain classical until their members publish prekeys — and the report says exactly that.)
- **Ceremony dry-run**: generate → rotate → cross-sign both directions → authenticate → continuity → additive subkey, all passing on throwaway keys in an isolated keystore.
- **Sizes** (the engineering reality): hybrid KEM public key 1216 B, ciphertext 1120 B; a group epoch costs ~1180 B per member *per epoch* (not per message); an ML-DSA-65 signature is 3309 B (~50× Ed25519, signing fast); the composite signature 3383 B. Post-quantum is bigger, and amortizing the KEM cost across an epoch is what makes group messaging practical.

---

## 9. What We Keep Reviewing — and Tomorrow

Crypto-agility is a *practice*, not a one-time port. The append-only ledger and the forbidden-words discipline are a standing review applied to every claim. Concretely ahead:

- **The root rotation ceremony** (owner-gated) — additive PQC subkeys first (reversible), then an optional full rotation to an `mldsa87-ed448` primary with old↔new cross-signing. The one un-exercised path is protected-key signing through the keystore on the live key.
- **The next tier, reserved.** `ML-KEM-1024 / ML-DSA-87` (level 5) is reserved for the **root** alone, where size is irrelevant and blast radius is catastrophic; the comms stay on the internet-default `-768` tier. The registry already holds the inactive placeholder — it plugs in as a backend by suite id.
- **Hash-based options.** SLH-DSA (FIPS 205) is reachable today at the liboqs layer for a maximally-conservative root signer; it is registered as an inactive suite pending a clean OpenPGP path.
- **Transport (Phase 3).** Rebuild daemon origins on OpenSSL 3.5+ so `X25519MLKEM768` negotiates to the origin; track the residual classical legs (WireGuard Noise, WebRTC DTLS) honestly until their upstreams gain agility.
- **Standards watch.** The OpenPGP PQC composites ride `draft-ietf-openpgp-pqc` (pre-RFC); code points can still move, so everything composite stays additive and reversible.

Every one of these is a registry entry and a backend away — which is the entire point.

---

## 10. Conclusion

The quantum migration is often framed as a race against a doomsday clock. We think that framing is both wrong and dangerous: wrong because the CRQC is years out, dangerous because it invites either complacency ("not broken yet") or overclaiming ("quantum-proof now"). The honest framing is HNDL plus Mosca: long-lived secrets must be protected *today*, with hybrid constructions that cannot be worse than the classical crypto they extend, and with a posture that states exactly what is and is not protected.

But the durable contribution is not the algorithm — it is the **scaffolding**. We built `skchat`/`skcomms`/`capauth` so that the choice of post-quantum scheme is a registry entry and a pluggable backend, so that every object on the wire says what protects it, and so that a self-report engine makes overclaiming structurally impossible. ML-KEM-768 and ML-DSA-65 are today's answers. When tomorrow's answer arrives — a higher tier, a hash-based root, a new family entirely — our infrastructure will ride on top of it. That is what it means to build something to outlive the algorithm.

---

## References

1. NIST, *FIPS 203: Module-Lattice-Based Key-Encapsulation Mechanism Standard* (13 Aug 2024). [csrc.nist.gov/pubs/fips/203/final](https://csrc.nist.gov/pubs/fips/203/final)
2. NIST, "NIST Releases First 3 Finalized Post-Quantum Encryption Standards" (13 Aug 2024); U.S. Federal Register, *Announcing Issuance of FIPS 203/204/205*, doc. 2024-17956 (14 Aug 2024).
3. IETF, *draft-ietf-tls-ecdhe-mlkem* (X25519MLKEM768 for TLS 1.3) and *draft-ietf-tls-hybrid-design*; analysis in IACR ePrint 2024/039.
4. Signal, "Quantum Resistance and the Signal Protocol — PQXDH" (Sept 2023). [signal.org/blog/pqxdh](https://signal.org/blog/pqxdh/)
5. Signal, *The PQXDH Key Agreement Protocol* (specification). [signal.org/docs/specifications/pqxdh](https://signal.org/docs/specifications/pqxdh/) — formally verified by Bhargavan et al., *USENIX Security 2024*.
6. Apple Security Engineering & Architecture, "iMessage with PQ3: The New State of the Art in Quantum-Secure Messaging at Scale" (Feb 2024). [security.apple.com/blog/imessage-pq3](https://security.apple.com/blog/imessage-pq3/)
7. D. Stebila, *Security Analysis of the iMessage PQ3 Protocol* (2024). [security.apple.com](https://security.apple.com/assets/files/Security_analysis_of_the_iMessage_PQ3_protocol_Stebila.pdf)
8. F. Linker, R. Sasse, D. Basin, "A Formal Analysis of Apple's iMessage PQ3 Protocol," *USENIX Security 2025* (machine-checked with the TAMARIN prover). [usenix.org](https://www.usenix.org/conference/usenixsecurity25/presentation/linker)
9. Sequoia-PGP, "Post-Quantum Cryptography" (Nov 2025). [sequoia-pgp.org/blog/2025/11/15](https://sequoia-pgp.org/blog/2025/11/15/202511-post-quantum-cryptography/)
10. IETF, *draft-ietf-openpgp-pqc — Post-Quantum Cryptography in OpenPGP* (Standards Track, pre-RFC). [datatracker.ietf.org/doc/draft-ietf-openpgp-pqc](https://datatracker.ietf.org/doc/draft-ietf-openpgp-pqc/)
11. "Quantum-Safe vs. Quantum-Resistant vs. Post-Quantum: cutting through the snake oil." [postquantum.com/quantum-snake-oil](https://postquantum.com/quantum-snake-oil/quantum-safe-quantum-resistant-post-quantum/)
12. Signal, "SPQR: Post-Quantum Ratcheting" / Triple Ratchet (2025); see also B. Schneier, "Signal's Post-Quantum Cryptographic Implementation" (Oct 2025). [signal.org/blog/spqr](https://signal.org/blog/spqr/)
13. IETF MLS (RFC 9420) and its emerging PQC ciphersuite work; Matrix.org engineering blog. [datatracker.ietf.org](https://datatracker.ietf.org/doc/rfc9420/) · [blog.matrix.org](https://blog.matrix.org/)
14. NIST, *Considerations for Achieving Cryptographic Agility* (CSWP 39, Dec 2025).

*Standards and drafts move fast: NIST has since added HQC as a backup KEM and FN-DSA (Falcon) standardization is pending; OpenPGP-PQC code points and MLS PQC ciphersuites are still evolving and should be re-checked at implementation time.*

---

## Appendix A — Canonical Identifiers

**Suite ids** — active: `x25519-mlkem768` (hybrid KEM), `mldsa65-ed25519-v2` (hybrid sig); backend-issuable: `mldsa87-ed448-v2` (root); planned/inactive: `x25519-mlkem768-v2`, `slh-dsa-shake-256-v2`; classical: `ed25519-v1`, `rsa4096-v1`, `rsa-pgp-wrap-v1`, `x25519-pgp-wrap-v1`; symmetric: `aes256-gcm-v1`.

**Wire markers** — `pqdm1:` (sealed DM scheme); `SKHS` magic, version `0x01`, suite-tag `0x01` (hybrid signature).

**Standards** — FIPS 203 (ML-KEM), 204 (ML-DSA), 205 (SLH-DSA), 197 / SP 800-38D / SP 800-108 (AES-GCM, HKDF); RFC 5869 (HKDF), 7748 (X25519), 8032 (Ed25519/Ed448), 9580 (OpenPGP v6); NIST CSWP 39 (crypto-agility); `draft-ietf-openpgp-pqc` (pre-RFC composites, code points 30/31/32–34/35/36).

**Tooling** — `sq 1.4.0-pqc.1` (sequoia-openpgp 2.2.0-pqc) on OpenSSL 3.6.2; liboqs 0.14.0; `@noble/post-quantum`; pyca `cryptography`; `package:cryptography` (Dart).

**Library** — `sk_pqc`, Apache-2.0, [github.com/smilinTux/sk_pqc](https://github.com/smilinTux/sk_pqc), live at [skpqc.skworld.io](https://skpqc.skworld.io).

---

## Appendix B — Sizes at a Glance

| Element | Bytes |
|---|---|
| Hybrid KEM public key (`X25519 ‖ ML-KEM-768`) | 1216 |
| Hybrid KEM ciphertext | 1120 |
| Hybrid shared secret (HKDF-SHA256) | 32 |
| Group epoch payload / member / epoch | 1180 |
| `pqdm` sealed-blob minimum | 1148 |
| ML-DSA-65 signature | 3309 |
| Hybrid `SKHS` composite signature | 3383 |

*Relative cost: ML-KEM-768 ciphertext ≈ 33× X25519; ML-DSA-65 signature ≈ 50× Ed25519 (signing is fast). Amortizing the KEM across an epoch, not a message, is what keeps group messaging practical.*

---

*SKWorld Research · part of the `PQC-MIGRATION` program · honesty engine: `sksecurity pqc-dashboard` · the live root is still classical, and we will tell you the day it isn't.* 🐧⚛️
