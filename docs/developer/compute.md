# Compute strategy

| Tier | Where | Use for | Limits |
|---|---|---|---|
| T0 | Dev VPS (2 vCPU, 3 GB, no GPU) | Code, tests, simulators, classical CV, light model inference on tiny inputs, docs | Do not train; do not load models > ~1.5 GB |
| T1 | Google Colab through the Colab MCP (if available to the agent) | Training / fine-tuning / benchmarking neural models (SDT, One-DM, Graves RNN, OCR) | Sessions die; code must be notebook-reproducible |
| T2 | User's own machine (optional) | Same as T1, offline | Needs the user |
| T3 | Cloud APIs | **Opt-in plugins only**, never in default flows, never required for tests | Zero-egress rule |

## Rules

1. **Notebooks are the source of truth for anything run on T1/T2.** Put them in `notebooks/<card>-<name>.ipynb` with a first cell that pins versions and clones the repo at a commit hash. Strip outputs before committing except small result tables.
2. **Weights and datasets are never committed.** Record each artifact in `models/MANIFEST.md`: name, source URL, license, sha256, size, produced-by (notebook + commit), where it is stored (GitHub release asset or user storage), and whether redistribution is allowed.
3. **Tests run on T0 without weights.** Model-dependent tests are `integration` tests that look for the weight in `~/.penpress/models/` and are collected by a **separate marker** (`pytest -m models`). The T0 gate must still prove behaviour with small deterministic fixtures. Note: skipping tests silently is forbidden, so the model suite is its own command with its own evidence, not a skipped test.
4. **Everything shipped must run on a normal laptop CPU** in a reasonable time (target in R1 card), with GPU optional. If a model needs a GPU for acceptable speed, ADR must offer a CPU path (smaller model, ONNX, distillation) or a precompute strategy (render all glyph variants once per profile, then compose).
5. **Colab MCP usage pattern:** upload notebook -> run cells -> download artifacts to `research/<card>/results/` (small) or Drive (large) -> record in manifest. Log every session in `JOURNAL.md` with notebook commit hash.
