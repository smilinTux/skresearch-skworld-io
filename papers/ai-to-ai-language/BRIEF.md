# AI-to-AI Language: Wire Density Is Not Token Density

## One-Line Summary
We tried to build a denser-than-English "AI-only language," then measured it on real tokenizers — and found the intuition is false for frozen transformers, except for one validated trick: shared in-context macros (−67% tokens, 100% fidelity).

## The Core Finding
- **Wire density ≠ token density.** A model's cost is its tokens; it reads/writes only its tokenizer's vocabulary and never sees a compact "AI language" on the wire. Compressing the wire does nothing to inference cost.
- **Intuitive tricks backfire (measured):** Chinese costs **+56% tokens** on Claude Haiku (English-tuned BPE shatters CJK); JSON schema costs **+8–10%**, up to **+125%** on short messages. **English is the densest** on both our models.
- **The meta-language test:** bare jargon saves ~40% tokens but **misreads 1-in-5 to 2-in-5** instructions — *action-flipping* misreads (`.41` host→version, `NA` next-action→North America). A trap.
- **The one win:** **in-context macros** (terse phrases + explicit shared definitions, slot types pinned) → **−67% tokens AND 100% comprehension fidelity** on both models. Break-even at 2 reuses. Auditable by construction (the definitions are the gloss).

## Models / Method
- **Qwen3.6-27B** — exact counts via llama.cpp `/tokenize`.
- **Claude Haiku 4.5** — true `usage.prompt_tokens` via internal proxy (−7 chat-wrapper).
- 2 controlled experiments, real production tokenizers, comprehension-fidelity rubric (EXACT/ACCEPTABLE/LOSSY/WRONG). No estimated or fabricated counts.

## Conclusion
There is no token-efficiency win from inventing a new alphabet inside frozen models. The only lever is a shared, carefully-authored, in-context macro vocabulary — and a truly native AI language below human tokens requires changing the model (fine-tune / shared latent codec), not the wire.

## Status
- Empirical draft: June 2026
- Part of the SKGlossa design record (`skcomms` repo)
- Published: skresearch.skworld.io
