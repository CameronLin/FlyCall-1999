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
- 2026-10-26: Added a four-stage expandable inference guide with data shapes, purpose, source locations, and matching code excerpts. The architecture panel now distinguishes the checkpoint used for the current prediction from the uncalled research candidate. Replaced the fixed-order score/logit DataFrame with a light-background, dark-text HTML table to avoid dark-theme contrast problems. No new tests were run for this UI polish.
- 2026-10-26: Follow-up UI correction: moved the model-principles guide above the transcript input so it is visible before the long connectome diagram, set the classifier explanation open by default, and replaced `<pre>` code markup with an explicitly light, dark-text snippet panel to prevent inherited black code-block styling.
- 2026-10-26: Explicitly styled the transcript sample selectbox, its dropdown options, and the “還原預設” button with light backgrounds and dark text; the previous rule changed selectbox text only and left control surfaces to the active theme.
- 2026-10-26: Follow-up selector correction: the initial surface rule missed nested BaseWeb selectbox nodes. Added explicit light backgrounds and dark text to the select root and every nested control element, including the selected-value area.
- 2026-10-26: Added a project-level Streamlit light theme so native controls do not inherit a system dark theme; retain targeted selectbox and reset-button styling as a local guarantee.
- 2026-10-26: Added a four-stage inline SVG overview to the model-principles guide: R/L transcript, E5 vector, the active classifier layout, and illustrative five-class Softmax bars. SVGs are local, responsive, and do not depend on external image downloads.
- 2026-10-26: Added distinct, detailed illustrations inside the expandable inference steps: R/L turns merging into one transcript, E5 prefix/encoder/vector normalization, MLP layer connectivity or Fly A/B graph stages, and the Softmax formula with fixed-order class selection. The top flow remains a compact overview; detail illustrations include a note separating schematic sizes from actual model dimensions and predictions.
- 2026-10-27: Fixed the detailed Softmax figure layout. Long class labels had overlapped the central block; widened the viewBox into separate logits, Softmax, and class-score columns. Replaced the stacked fraction with a centered one-line formula and a short plain-language explanation.
- 2026-10-27: Simplified the Softmax visual for readability: the center now shows three labeled steps (raw scores → positive values → divide by the five-class total), with the one-line formula removed from the main diagram.
- 2026-10-27: Connected the detailed Softmax chart to the current prediction: it uses the fixed label order, displays the five actual probabilities to two decimal places, highlights the predicted class, and distinguishes pre-prediction schematic bars from real results. Added measured time to each executed inference stage (E5, the selected classifier or Fly A/Fly B, and Softmax output), with end-to-end duration labeled as including UI status updates. Made the full principles guide collapsible and closed by default so the transcript/classification workflow stays compact. Python AST parsing passed. Streamlit's versioned-reference discovery could not launch its probe process on this Windows environment (WinError 1920), so no browser/AppTest run was performed.
- 2026-10-27: Reworked the architecture/status panel's responsive layout after diagnosing crowding from fixed minimum grid widths and a single-row Fly A/B route. MLP and graph-core tracks now shrink within their containers, the Fly A/B route changes to a two-row snake layout at tablet widths and a vertical flow on phones, and section dividers separate active inference, network detail, and MaleCNS context. No browser rendering was available for visual acceptance.
- 2026-10-27: Follow-up spacing fix for the “本次實際執行” and “研究候選” role cards. Replaced their half-width side-by-side layout with full-width stacked cards; each card places its role/name beside the explanatory copy on wider screens and stacks all content on phones.
- 2026-10-27: Local launch diagnosis: global CPython 3.14 installations have none of the project packages, while `%TEMP%\flycall-m22b\venv` contains Streamlit 1.66.0, PyTorch 2.14.1 CPU, Transformers 5.20.2, and Sentence Transformers 6.0.0. That venv has no torchvision, but imports for the text E5 runtime succeed. The pinned E5 snapshot is present under `%TEMP%\flycall-m22b\hf-home`; launch the app with that venv's `streamlit.exe` and explicit manifest/snapshot paths. This was an import check only; no AppTest or browser render was performed.
- 2026-10-27: User screenshot exposed the cause of the crowded network panel: `_network_status_html()` left the outer `.fc-network-header` unclosed, so all following sections became flex children of the header. Added the missing closing `</div>`. Generated HTML from the project `app.py` now has balanced tags and renders both role cards after, rather than inside, the header. Browser visual retest remains pending.
