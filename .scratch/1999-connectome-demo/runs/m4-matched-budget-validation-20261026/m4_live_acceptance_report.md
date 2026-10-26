# M4 selected model and live interface acceptance

- Status: M4.1 locked predictor and M4.2 Streamlit research UI technical acceptance passed; manual review remains pending.
- Data: synthetic; test: `not_run`; test examples opened: 0.
- Selected development/demo candidate: registered MLP, seed 42, 384-to-16-to-5, ReLU, 80 epochs, learning rate 0.02.
- Locked manifest: `.scratch/1999-connectome-demo/runs/m2-2b-e5-seed-42-current-runner-20261026/locked_model_manifest.json` (SHA-256 `f050e8c64ae875c56048cb80e1c879d295e0f115ed20f361cfdeaafc45ccfe7c`).
- Checkpoint SHA-256: `d4a30ffba9e37fc68a150129d7418666251086020619d9767bc1395dafd559bf`.
- E5: `intfloat/multilingual-e5-small`, revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`, local snapshot verified against all pinned files.

## Candidate decision

The official M3.4 preregistered three-seed comparison selected MLP provisionally (mean validation Macro-F1 0.9022, sample SD 0.0274; accuracy 0.9067, sample SD 0.0231). The gated E5 residual reached mean Macro-F1 0.9048 (SD 0.0084) and accuracy 0.9089 (SD 0.0077) after four settings were compared on the same validation set. That small apparent gain is subject to validation-selection optimism.

A matched-budget, train/validation-only comparison used seeds 42, 1337, and 2026 for MLP, pure Fly A-to-B, and the gated residual:

| Candidate | Macro-F1 mean (sample SD) | Accuracy mean (sample SD) |
|---|---:|---:|
| MLP | 0.9104 (0.0302) | 0.9133 (0.0267) |
| Gated E5 residual | 0.9048 (0.0084) | 0.9089 (0.0077) |
| Pure Fly A-to-B | 0.8040 (0.0218) | 0.8244 (0.0077) |

The MLP leads the matched-budget validation mean by 0.0056 Macro-F1 and 0.0044 accuracy, while showing greater seed-to-seed variation. Keep the registered M3.4 MLP as the M4 development/demo model. Retain the residual as a research candidate; it does not replace the preregistered winner based on this validation evidence. This is a provisional selection on synthetic data, not a final performance claim.

## Actual checkpoint acceptance

Loaded the selected joblib checkpoint through the actual pinned E5 runtime and exercised the direct predictor API, `scripts/predict_flycall.py`, and `app.py` with Streamlit 1.66.0 `AppTest`. Each interface received this independently written synthetic transcript:

> M4 interface acceptance synthetic transcript: potholes reported.

All three returned `sidewalk_maintenance` in the fixed label order. Maximum absolute differences against the API were `0.0` for CLI logits and `0.0` for CLI probabilities; Streamlit differences were `0.0` for logits and `0.0` for probabilities. The UI rendered five score rows and the manual-confirmation notice with zero exceptions.

The output continued to identify synthetic data, pending manual review, simulated-only dispatch, and required human confirmation. This verification used no dataset rows or test split.

## Remaining project gates

- Formal data review and the user's final approval of the candidate/configuration remain pending.
- The final one-time test evaluation remains unopened and `not_run` until that review and approval are complete.
- After those gates, the remaining work is final evaluation and reporting; no M4 predictor or UI integration task remains for the selected MLP.

Machine-readable result: `m4_live_acceptance.json`. Reproduce with `m4_live_acceptance.py --manifest <locked_model_manifest.json> --snapshot <pinned-E5-snapshot> --output-json m4_live_acceptance.json`.
