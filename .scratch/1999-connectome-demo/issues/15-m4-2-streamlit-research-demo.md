# 15: M4.2 Streamlit research demo

**What to build:** Provide a local UI over the same M4.1 predictor. Show one transcript input, the E5→baseline or E5→Fly A→Fly B stages, five fixed-order class scores, prediction, simulated destination, error states and the pending manual-confirmation status.

**Formal test gate:** Manual review and final approval remain pending before any one-time test evaluation. The optional runtime, development/demo lock and selected model bundle are ready for technical acceptance.

**Status:** M4.2 technical acceptance passed through Streamlit 1.66.0 `AppTest` with the actual locked MLP checkpoint and E5 snapshot. Its displayed five logits/probabilities and predicted label exactly match the direct API and CLI. Formal manual review remains pending.

## Implemented

- `app.py` calls the same `FlyCallPredictor.predict()` API as the CLI.
- The page displays “合成資料訓練 · 研究 Demo · 模擬派送”, marks manual review pending, and explicitly states that no real dispatch occurs.
- The result view shows the predicted class, model stages, five class probabilities/logits and the human-confirmation requirement.
- Model loading validates the locked manifest and checksums before a transcript is accepted. Missing manifest, model, or E5 snapshot produces a visible error.
- `requirements-demo.txt` pins the optional Streamlit UI package; the existing M2.2b environment supplies the E5/model dependencies.

## Remaining acceptance conditions

- [x] Complete the provisional M3.4 three-seed validation comparison.
- [x] Record the user-directed development/demo model lock with human review explicitly pending.
- [x] Install the optional UI dependency in the isolated Windows environment.
- [x] Load `app.py` through Streamlit `AppTest`; verify missing-model error handling and render a synthetic fixture prediction with five scores and a human-confirmation notice, without loading a model or dataset.
- [x] Load `app.py` through Streamlit `AppTest` with the actual selected checkpoint; render five scores and the human-confirmation notice.
- [x] For one fixed synthetic transcript, verify UI probabilities/logits and predicted label match the CLI/API output exactly.
- [ ] Complete manual review and formal approval before the one-time test gate.

## Comments

- 2026-10-26: Added the Streamlit page and mocked UI test. No dataset or test transcript was read by the app test.
- 2026-10-26: M3.4 now has a provisional MLP validation winner from three seeds, but candidate and checkpoint-seed selection remain unlocked. Streamlit is still absent from the E5 environment, so browser rendering remains unverified.
- 2026-10-26: Installed the pinned Streamlit 1.66.0 runtime into the isolated E5 environment using a writable `%TEMP%` uv cache. Streamlit `AppTest` loaded `app.py`, observed the required-model-path error, and reported zero app exceptions. No model or dataset was loaded. Selected-model/browser acceptance remains open.
- 2026-10-26: Added `tests/test_streamlit_app.py` with optional-runtime coverage for both the missing-path and success display states. The success path patches the locked-manifest loader with an in-memory fixture predictor; Streamlit rendered the predicted label, score table and confirmation notice, with zero app exceptions and no model/data access.

- 2026-10-26: Actual-model AppTest passed with five score rows, manual-confirmation notice, and zero exceptions. Streamlit matched CLI/API exactly (max absolute logit/probability delta 0.0); no dataset or test data was accessed. See `../runs/m4-matched-budget-validation-20261026/m4_live_acceptance_report.md`.
