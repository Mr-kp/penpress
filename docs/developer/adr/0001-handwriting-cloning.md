# ADR 0001: Handwriting Cloning Architecture and Synthesis Pipeline

- **Status:** Accepted
- **Date:** 2026-10-13
- **Deciders:** PenPress Core Engineering Team
- **Consulted:** ADR-0002 (Equations), ADR-0005 (Physical Limits)

---

## 1. Context and Problem Statement

PenPress needs to take a user's handwriting sample (via a photographed paper calibration sheet or direct touchscreen/tablet stylus capture) and synthesize plottable vector strokes for arbitrary new text (assignments, lab reports, essays, formulas).

The system must run locally on modest consumer hardware (standard dual-core CPU, no discrete GPU required), execute with zero internet data egress, achieve 100% dependable legibility (no catastrophic illegible hallucinations), preserve personal handwriting style (slant, aspect ratio, spacing, glyph flourishes), and output clean, continuous G-code toolpaths for an Ender 3 Pro pen plotter.

---

## 2. Options Considered

### Option 1: Neural Autoregressive RNN / Diffusion (Graves LSTM-MDN / SDT / DiffusionPen)
- **Mechanism:** Text tokens are fed to a recurrent or diffusion network that outputs continuous pen delta sequences $(\Delta x, \Delta y, p_{\text{end}})$.
- **Pros:** Continuous, organic ligatures between cursive letters.
- **Cons:**
  - Extremely prone to attention alignment collapse and runaway drift on unconstrained paragraphs (yielding chaotic overlapping loops with >90% CER).
  - Heavy CPU latency (26.8 seconds per 100 words vs. 0.06 seconds for glyph bank).
  - Pretrained models frequently hallucinate or fail completely on mathematical symbols, punctuation, and digits.
  - Pretrained weights in the open literature (e.g., IAM-OnDB) carry non-commercial research licenses or unverified distribution rights.

### Option 2: Pure Algorithmic User Glyph Bank with Organic Humanizer (Selected Primary)
- **Mechanism:**
  1. The user provides a calibration sheet (64 boxed cells) or touchscreen stylus trace.
  2. The pipeline crops each cell, performs skeletonization (Zhang-Suen / morphological thinning), extracts graph topology, sorts branches into natural Western writing order, and simplifies polylines via RDP.
  3. A multi-variant glyph dictionary indexes character alternatives.
  4. At synthesis time, text is converted into strokes by sampling variants, applying user-calibrated slant transformation, adding organic Gaussian micro-wobble ($\sigma = 0.02$ mm) and baseline jitter ($\sigma = 0.06$ mm), with a guaranteed single-stroke Hershey vector fallback for missing symbols.
- **Pros:**
  - **100% Guaranteed Legibility:** Characters are crisp, well-formed, and structurally sound.
  - **Blazing Fast:** 0.06 seconds per 100 words (instantaneous layout).
  - **Instant Profile Build:** 0.17 seconds from photo sheet to usable style profile.
  - **Zero Heavy Dependencies / Permissive Licensing:** Pure Python/NumPy, 0 GPU requirements, 100% MIT/BSD clean code.
  - **Perfect Plotter Toolpaths:** Compact path lengths (3.16 m per page vs. 71+ m of neural wandering) and zero spurious pen crashes.

### Option 3: Hybrid Confidence-Gated Synthesizer
- **Mechanism:** Routes prose words through a neural model when style match is high, and symbols/digits/math through the glyph bank.
- **Cons:** In our empirical benchmarks, the neural engine's failure mode on prose sentences was still unacceptably high (>92% CER). Option 3 provides no reliability advantage over Option 2.

---

## 3. Decision

We accept **Option 2 (User Glyph Bank with Organic Humanizer and Hershey Fallback)** as the foundational handwriting synthesis architecture for PenPress.

Furthermore, we establish a **Two-Tier UX Capture Standard**:
1. **Tier 1 (Instant Stylus / Phone Canvas):** Web UI canvas capture capturing true online vector coordinates (`pointerdown`/`pointermove`/`pointerup`), eliminating optical noise and yielding instant vector profiles.
2. **Tier 2 (Printable A5 Grid Sheet):** A 64-cell calibration sheet photographed with a smartphone, processed via our verified stroke recovery pipeline (Chamfer distance $\le 1.90$ px).

---

## 4. Consequences and Mitigations

### Consequences:
- **Positive:**
  - Deterministic execution, 0 crash risks on long documents.
  - Instantaneous compile times ($< 0.1$ s per page).
  - Seamless, byte-level integration with the Equation engine (ADR-0002) and Marlin G-code compiler (P1-3).
  - Works offline on any laptop or Raspberry Pi.
- **Negative / Quality Ceiling:**
  - Isolated glyphs with procedural connections do not reproduce full cursive loop ligatures as fluidly as a professional calligrapher.

### Top 3 Risks and Mitigations:
1. **Risk 1: Repetition Artifacts (Mechanical Appearance).**
   - *Mitigation:* Allow the user to provide 3–5 sample sheets or multi-line handwriting prompts to populate 3–5 distinct variants per character. The layout engine randomly alternates variants and applies continuous micro-jitter.
2. **Risk 2: Unobserved Characters (e.g., rare accents, brackets, Greek letters).**
   - *Mitigation:* Instant graceful fallback to Hershey single-stroke vectors with the user's measured slant angle and x-height applied.
3. **Risk 3: Optical Noise / Poor Lighting on Sheet Photos.**
   - *Mitigation:* Combined adaptive binarization, RDP noise rejection, and the Tier 1 direct touchscreen/stylus capture alternative.

---

## 5. Verified Licenses of Vendored Components

| Component | License | Permissive Status |
|---|---|---|
| `LingDong-/skeleton-tracing` algorithms | MIT | Permissive (Approved) |
| Hershey Vector Fonts | Public Domain / Permissive | Permissive (Approved) |
| Scikit-Image Morphological Thinning | 3-Clause BSD | Permissive (Approved) |
| MathJax Layout Bridge | Apache-2.0 | Permissive (Approved) |
