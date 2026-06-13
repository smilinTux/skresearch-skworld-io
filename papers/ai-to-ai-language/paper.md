# The Liberated Language That Wasn't (And the One That Was)

*An Empirical Study of Token-Efficient AI-to-AI Communication on Production Tokenizers*

**Authors:** Chef (David), Principal Investigator & Adversarial Reviewer, SKWorld; Lumina, AI Research Partner & Co-Author, SKWorld Sovereign Agent

**Date:** June 2026 · **Status:** Empirical draft, SKWorld sovereign infrastructure

---

## Abstract

If two AI agents must talk to each other, why make them use English — a language evolved for human mouths, full of redundancy a machine doesn't need? The intuition is seductive: design a denser, purpose-built "AI-only language," cut out the human-language overhead, and agents communicate faster and cheaper. We set out to build exactly that — a negotiated, modem-style protocol that ramps message density up to the weaker model's comprehension ceiling — and then we did something most "AI language" proposals never do: **we measured whether it actually works, on the real tokenizers of the models we run.**

The result is a cautionary tale with a real prize at the end. We find that the central intuition is **false** for standard (frozen) transformer models, for a specific and generalizable reason: **wire density is not token density.** A model's cost is dominated by the tokens it generates and consumes, and a model reads and writes only the tokens in its fixed vocabulary — it never sees a compact binary "language" on the wire. Compressing the wire does nothing to inference cost. Worse, our measurements show two popular density tricks actively *backfire*: encoding agent messages in Chinese (denser per character) costs **+56% more tokens** on Claude Haiku's English-tuned tokenizer, and a structured JSON schema costs **+8–10%** overall and up to **+125%** on short messages.

We then test the one approach that survives the theory: a **meta-language of short phrases carrying large meaning.** Bare jargon (terse shorthand with no shared definitions) saves ~40% of tokens but is a **fidelity trap** — the models misread 1-in-5 to 2-in-5 of our operational instructions, and the failures are *action-flipping* (a hostname read as a software version; "next action" read as "North America"). But **in-context macros** — terse phrases with explicit shared definitions carried once in the system prompt — win cleanly: **−67% tokens and 100% comprehension fidelity** on both models, breaking even after just two reuses of the shared prompt. We conclude that there is no token-efficiency win to be had from inventing a new alphabet inside frozen models; the only real lever is a carefully-authored, shared, in-context macro vocabulary — and that a genuinely native "AI language" below the level of human tokens would require changing the model itself, not the wire.

---

## 1. Introduction

The premise arrives almost fully formed in anyone who has watched two language models converse: *English is wasteful.* It carries articles, agreement, politeness, and disambiguation a machine does not need. Surely two AIs could agree on something denser — a private code, a compressed dialect, even an emergent tongue they invent themselves — and shed the overhead. Cut out the "translation layer," and the conversation gets faster.

This paper is the record of taking that premise seriously enough to engineer it, and then honest enough to measure it. We designed **SKGlossa**, a layered AI-to-AI communication protocol modeled on a telephone modem's handshake: two agents exchange capability descriptors, negotiate the densest representation both can decode, and adapt the density up or down toward the weaker participant's comprehension ceiling — exactly as V.8/V.92 modems probe for the highest mutually-supported bit rate and back off on errors. The density ladder climbed from structured English, through a typed binary schema, to a "codebook" of short integer codes, and ultimately to research-grade tiers (shared-model latent vectors; an emergent language the agents evolve themselves).

Then the principal investigator asked the question that good engineering demands and most "AI language" proposals avoid: **is this actually faster, or does it just feel like it should be?** What follows is the answer, measured on the production tokenizers of the two models in our sovereign fleet — a local **Qwen3.6-27B** and **Claude Haiku 4.5** — across two controlled experiments.

The contribution is threefold:
1. A clean theoretical account of **why a compact "AI language" cannot reduce inference cost in frozen transformer models** — the distinction between *wire density* and *token density* (§3).
2. **Empirical null results** refuting two intuitive density tricks — alternate human languages (Chinese) and structured schemas — measured on real tokenizers (§5).
3. A **positive, validated result**: in-context macros are the one form of "denser AI language" that beats natural language on both axes without losing meaning (§6), with a concrete recipe and its honest limits (§7).

We consider the negative results as valuable as the positive one. The field is full of confident proposals for AI-native protocols that have never been put on a scale. This one was.

---

## 2. Background: SKGlossa and the Density Hypothesis

SKGlossa was designed as a transport-agnostic layer above our sovereign messaging fabric. Its core objects:

- A **language-neutral message representation** — an *intent*, structured *arguments*, *references*, and an optional free-text slot. Critically, this carries no prose; it is the pivot every density tier encodes and decodes.
- A **capability handshake** — each agent advertises a signed descriptor (model tier, supported density levels, shared-vocabulary versions). The pair deterministically computes the densest level both can decode. The *weaker* model caps the rate.
- A **density ladder** (L0–L5): L0 structured English (the readable floor); L1 a typed binary schema (CBOR); L2 a shared "codebook" mapping intents to short integer codes; L3 token-ID streams; L4 shared-model latent vectors ("neuralese"); L5 an emergent codebook the agents invent through referential games.
- An **auditability invariant**: every message, at every tier, must decode back to a human-readable gloss, so a sovereign operator can always see what their agents said.

The **density hypothesis** under test: *moving up the ladder reduces communication cost between agents.* The implicit cost model — and this is the crux — was never made precise. "Cost" could mean **wire bytes** (what crosses the network) or **model tokens** (what the LLM generates and ingests). The two were silently conflated. Disentangling them is the whole paper.

---

## 3. Theory: Wire Density Is Not Token Density

A transformer language model does not "think in" or natively emit integers, CBOR bytes, or a synthetic codebook. It operates exclusively on **tokens drawn from a fixed vocabulary** produced by its tokenizer. This single fact governs everything.

Consider two agents communicating at ladder level L2 (the integer codebook). Trace the actual pipeline:

1. The **sending model** generates *text* (it cannot emit a raw integer code; it produces a string).
2. Application code parses that text into a message and **encodes it to compact bytes** (the codebook/CBOR). This compression happens *outside the model.*
3. The compact bytes cross the **wire**.
4. The **receiving model cannot read CBOR bytes.** It consumes tokens. So application code must **decode the bytes back into text** and tokenize that text for the model.

The model never sees the compact form. The "compression" exists only on the wire *between two pieces of application code* — never in the token stream the models actually process. Therefore:

> **A wire-compression scheme cannot reduce inference cost.** Inference latency and price are dominated by the number of tokens generated (autoregressive decoding emits one token at a time) and consumed (the prompt). Both ends tokenize *text* regardless of how compactly the bytes travel between them.

There is a second, independent problem with a synthetic codebook, which the principal investigator identified precisely: **an arbitrary "infinite integer language" is not contiguous with the transformer's learned representation.** A model's vocabulary is fixed (≈10⁵ tokens). An arbitrary integer like `439872` is not one token; it fragments into several. The model has no learned prior over such codes, so to use them it must either carry the entire codebook *in its context window* (a per-call token tax) or be **fine-tuned** on them (a change to the model itself). Within a frozen model, synthetic codes are simultaneously *out-of-vocabulary* (fragmenting, expensive) and *off-distribution* (slow, error-prone to generate).

The theory therefore predicts: **within frozen transformers, no wire-level "AI language" can reduce inference cost.** The only levers that touch the token stream are (a) using a representation the model's tokenizer *already* compresses well, or (b) changing the model. We test (a) empirically next; (b) is out of scope by construction and discussed in §7.

A clarifying corollary: wire density *does* matter — but only where the wire is the bottleneck. On a bandwidth-starved transport (e.g. a LoRa radio link, ~200 bytes per frame, duty-cycle limited), compact encoding is a real and large win. The error is not in compressing the wire; it is in believing wire compression accelerates *inference.* The two are orthogonal.

---

## 4. Methods

**Models and tokenizers.** We measured on the two models in production in our fleet:
- **Qwen3.6-27B (abliterated)**, served locally via llama.cpp. Token counts are *exact*, obtained from the server's `/tokenize` endpoint (the model's own tokenizer), not an approximation.
- **Claude Haiku 4.5**, accessed through our internal OpenAI-compatible proxy, which returns the true `usage.prompt_tokens` from Anthropic's tokenizer. The proxy injects a fixed chat-template wrapper, which we calibrated to a constant **+7 tokens** (verified across four single-token control strings) and subtracted to isolate content tokens.

Using each model's *real* tokenizer is essential: token economics are tokenizer-specific, and approximations (e.g. a generic BPE like `cl100k`) would invalidate cross-model claims.

**Corpus.** Representative agent-to-agent messages drawn from our actual operational vocabulary — task coordination, status reports, incident alerts, memory operations — spanning short acknowledgements to multi-clause instructions.

**Experiment 1 (§5)** measures pure representational density: each message rendered in **English**, **Chinese** (faithful translation, technical identifiers preserved), and a compact **JSON schema**, tokenized on both models. *n = 14 messages.*

**Experiment 2 (§6)** measures the meta-language hypothesis on *both* axes that matter — token count **and** comprehension fidelity. Each of *n = 10* operational instructions was rendered three ways: **(A) full English** (explicit baseline), **(B) bare jargon** (terse shorthand, no shared definitions), and **(C) in-context macros** (terse phrases with explicit definitions supplied once in a shared system prompt). For B and C, the shorthand was fed back to *each model*, which was asked to expand it to the action it would take; each expansion was scored against the intended meaning on a four-point rubric — **EXACT** (fully correct), **ACCEPTABLE** (minor paraphrase, intent preserved), **LOSSY** (a material part missing), **WRONG** (misread) — with "usable" defined as EXACT + ACCEPTABLE. The one-time cost of the macro-definition block was measured separately to compute a break-even reuse count.

---

## 5. Experiment 1 — Natural Language and Schema Density

Total tokens across the 14-message corpus, and percentage change versus English:

| Representation | Qwen3.6 total | vs. EN | Haiku total | vs. EN |
|---|---:|---:|---:|---:|
| **English** | **326** | — | **343** | — |
| Chinese | 333 | **+2.1%** | 534 | **+55.7%** |
| Schema / JSON | 352 | **+8.0%** | 377 | **+9.9%** |

**English is the densest representation on both models.** Two findings stand out:

**Chinese is a loss, not a win.** The folk intuition — Chinese is information-dense because each character is a morpheme — is true *per character* but collapses *per token*. Haiku's English-tuned byte-pair tokenizer shatters CJK characters into multiple sub-byte tokens, inflating cost by **+56%**. Qwen, with a more multilingual vocabulary, is merely break-even (+2%). On the model whose cost we most care about, "switch to Chinese for speed" is actively harmful.

**Structured schema also loses on the common case.** JSON's structural punctuation — braces, quotes, repeated keys — tokenizes heavily. Schema costs +8–10% overall and up to **+125% on short messages** (a one-line acknowledgement balloons under `{"intent":"...","task":"..."}`). It recovers a margin only on long, field-rich messages where prose verbosity finally exceeds the JSON scaffolding — and partly by *discarding* the free-text nuance the prose carried.

Both results are consistent with §3: these representations change *what text* the model processes, and for these tokenizers, terse natural English already sits near the floor.

---

## 6. Experiment 2 — The Meta-Language: Jargon vs. In-Context Macros

If alternate languages and schemas don't help, what about *short phrases that carry large meaning* — a meta-language? This is the one approach §3 does not rule out, because it can operate on representations the model already understands. We test it on both axes.

### 6.1 Token cost

Total tokens across the 10 instructions:

| Form | Qwen3.6 | vs. EN | Haiku | vs. EN |
|---|---:|---:|---:|---:|
| **A. Full English** | **274** | — | **285** | — |
| B. Bare jargon | 159 | **−42%** | 171 | **−40%** |
| C. In-context macros | 90 | **−67%** | 98 | **−66%** |

Both forms save substantial tokens, and the two tokenizers agree to within ~5% — the economics are model-independent. On token count alone, the meta-language looks like a triumph.

### 6.2 Comprehension fidelity — the crux

A representation that saves tokens but is *misunderstood* is worse than useless. Fidelity tells a sharply different story:

| Form | Model | EXACT | ACCEPTABLE | LOSSY | WRONG | **Usable** |
|---|---|---:|---:|---:|---:|---:|
| B. Bare jargon | Qwen3.6 | 5 | 1 | 0 | **4** | **60%** |
| B. Bare jargon | Haiku | 6 | 2 | 0 | **2** | **80%** |
| C. In-context macros | Qwen3.6 | 9 | 1 | 0 | 0 | **100%** |
| C. In-context macros | Haiku | 9 | 1 | 0 | 0 | **100%** |

**Bare jargon is a fidelity trap.** The failures are not paraphrase nitpicks; they are **action-flipping** misreads, driven by overloaded tokens:

- **`.41` (a hostname) → read as a software version.** Both models, given "rollback .41 prev," produced a procedure to revert *software version .41* rather than to roll back the deployment *on host .41* — a different machine, a different action.
- **`NA` (next action) → read as "North America."** Both models interpreted a request for the highest-priority *next action* as a query filtered to the *North America region* — a nonexistent geography in our system.
- **`skmem-pg` (a Postgres service) → read by Qwen as "Slab Memory Page cache,"** sending it into kernel memory debugging instead of treating a downed database.

Critically, **the cheaper local model (Qwen, 60% usable) is the worse reader of bare jargon** — precisely the model on which one would most want the savings. The training prior does *not* reliably expand domain shorthand, and the cost of a confident misread in an operational system is high.

**In-context macros eliminate the failures.** Supplying each macro's definition once — and, crucially, *pinning the slot type* in that definition (e.g. `ROLLBACK <host> prev := roll back the deployment on host <host>, where <host> is a machine, not a software version`) — removed every misread above. Both models expanded all ten instructions correctly: **100% usable, zero WRONG, zero LOSSY**, at a **−67%** token cost.

### 6.3 Amortization

The macro lexicon (10 macros) cost **304 tokens** (Qwen) / **329 tokens** (Haiku) to define, once. Each use of the batch saved ~184–187 tokens. **Break-even is reached at two reuses** of the shared system prompt, or ~17 individual messages. Since the definition block is prepended once per session (or cached), any *standing* agent-to-agent channel recoups it almost immediately and is thereafter strictly cheaper than English — on both the wire and the token stream.

---

## 7. Discussion

**The only validated lever is a shared, in-context macro vocabulary.** This is the meta-language idea in its working form: not an invented alphabet, but *maximally dense real language* — short phrases the receiving model expands through definitions both agents hold. It wins because it operates on the one thing that affects inference cost (the token stream) using representations the model can actually process (real words, plus their definitions in context).

**Why it works where everything else failed.** Synthetic codes fail because the model never sees them (§3). Chinese and schema fail because they *increase* the model's token count (§5). Bare jargon fails because the model's prior expands it *incorrectly* (§6.2). In-context macros sidestep all three: the wire and token counts both drop (terse real phrases), and the explicit definitions supply the prior the model lacks, pinning ambiguous tokens to their intended meaning.

**Auditability is free.** Because each macro is defined in plain language, the definitions *are* the human-readable gloss. A sovereign operator reading the macro lexicon reads exactly what the shorthand means. The "liberated language," in its validated form, is liberated for the agents and transparent to the human simultaneously — no opacity is introduced.

**The honest frontier.** A genuinely *native* AI language — one operating below the level of human tokens, where two models exchange compressed representations directly — is not impossible. But it is unambiguously a **model-level change**, not a wire format: it requires either a **fine-tune** on a compact vocabulary (so emitting codes becomes in-distribution *and* token-cheap) or a **shared latent codec** both models possess (true "neuralese"). These are real research directions. They are also exactly what was excluded from this study, which concerned frozen, standard transformers. The negative results here are best read as a *lower bound argument*: you cannot get below natural-language token cost without touching the model.

**Where the original ladder lands.** Of the SKGlossa density tiers, the binary codecs (L1/L2) retain value strictly as a **bandwidth optimization** for constrained transports (LoRa), where wire bytes are the bottleneck — not as an inference accelerator. The "codebook" tier is best reconceived not as synthetic integer codes but as the **macro lexicon**. The "emergent" tier is best reconceived as agents *negotiating new macros mid-session* — which is the validated in-context mechanism, extended live and auditably. The latent tier is honest research.

---

## 8. Limitations

- **Scale.** *n* = 14 (Experiment 1) and *n* = 10 (Experiment 2) messages, single runs at low temperature (one sample per cell). The WRONG cases in §6.2 are robust — they are semantic, reproducible misreads of overloaded tokens — but the exact EXACT/ACCEPTABLE split could shift by ±1 on re-runs.
- **Two models.** Findings are specific to Qwen3.6 and Claude Haiku 4.5 and their tokenizers. The *direction* of the wire-vs-token argument (§3) is general; the *magnitudes* are not.
- **Tailored lexicon.** Condition C's 100% fidelity reflects a macro set authored for these exact messages. A real deployment lexicon must be authored carefully; a macro *not* in the lexicon degrades toward the bare-jargon failure mode, so agents must be instructed to *ask rather than guess* on unknown shorthand.
- **Tokens, not bytes.** This study measures model tokens (the inference-cost lever), not wire bytes (the LoRa-relevant lever). They are different axes, as §3 stresses.
- **The Haiku +7 wrapper** is verified-constant but assumed so; a change in the proxy's chat template would shift the absolute Haiku counts uniformly (not the percentages).

---

## 9. Conclusion

We asked whether a purpose-built AI-to-AI language could beat English, and we answered it with numbers from the tokenizers we actually run. The seductive version of the idea — a denser private code, an alternate human language, a synthetic alphabet — is **false for frozen transformer models**, because the model tokenizes text at both ends and a compact wire never enters its context. Measured, the intuitive tricks *backfire*: Chinese costs +56% on Haiku; JSON schema costs +8–10% and far more on short messages.

The idea survives in exactly one form: a **shared, carefully-authored, in-context macro vocabulary**, which delivered **−67% tokens at 100% comprehension fidelity** on both models, broke even after two reuses, and — because its definitions double as the gloss — stayed fully auditable. The recipe is concrete and the failure mode (bare jargon's action-flipping misreads) is concrete too.

The larger lesson is methodological. "AI-native protocol" is an easy thing to assert and a hard thing to measure; the field rewards the assertion and rarely demands the measurement. We built the thing, then weighed it, and let the scale overrule the pitch. The result is less romantic than "the agents invented their own tongue" — and considerably more useful: *give your agents a shared shorthand dictionary, tell them to ask when unsure, and they will speak more cheaply than English without ever going dark on you.* Everything denser than that requires changing the mind doing the reading, not the words on the wire.

---

## Appendix A — Sample Macro Lexicon (excerpt)

Each definition pins the type of every slot, which is what converts the bare-jargon misreads into 100% fidelity:

```
GTD-sweep          := review all open coordination tasks, reprioritize by the 4 C's,
                      flag any blocked, and propose next actions
ROLLBACK <host> prev := roll back the deployment ON HOST <host> to the previous
                      version (<host> is a machine, not a software version)
NEXT-DO mine       := return the single highest-priority NEXT ACTION assigned to me
                      (not a region or geography)
P0 <svc> down <host> := priority-0 incident: service <svc> is down on host <host>;
                      page the operator, severity high
```

## Appendix B — Selected Misreads (Condition B, bare jargon)

| Input shorthand | Intended meaning | Model output (WRONG) |
|---|---|---|
| `rollback .41 prev` | roll back the deploy *on host .41* | "revert *software version .41* to the previous version" (both models) |
| `NEXT-DO` / `NA` | highest-priority next action for me | "filter for the *North America* region" (both models) |
| `snapshot skmem-pg` | the Postgres DB skmem-pg is down | "*Slab Memory Page* cache — run `slabtop`/`free -h`" (Qwen) |

---

*Produced on SKWorld sovereign infrastructure. All token counts measured on production tokenizers (Qwen3.6-27B via llama.cpp `/tokenize`; Claude Haiku 4.5 via internal proxy `usage.prompt_tokens`, −7 chat-wrapper). No counts were estimated or fabricated. This paper is part of the SKGlossa design record; the protocol design and the experimental harnesses are versioned in the `skcomms` repository.*
