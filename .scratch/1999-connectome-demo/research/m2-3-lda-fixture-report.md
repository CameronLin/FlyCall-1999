# M2.3 LDA fixture-only implementation report

**Date:** 2026-10-21  
**Status:** fixture-only complete; M2.3 remains `in-progress`. Formal E5 embeddings and the train/validation smoke run remain blocked by M2.2b.

## Contract implemented

- Input seam accepts only `SplitEmbeddings` with `train` and `validation`; it has no test argument.
- Inputs must be 384-dimensional, matching the centralized E5-small target configuration. This checks dimensions only; the fixture vectors are synthetic and were not produced by E5.
- `LinearDiscriminantAnalysis(solver="svd", n_components=min(4, C - 1))` is fit on train embeddings and labels. For the five fixed taxonomy labels, this produces four dimensions.
- Train embeddings are projected from the fitted LDA state. Validation embeddings use `transform` only. Logistic Regression is fit only on projected train rows and train labels; validation is used for predictions and metrics only.
- Class scores are reordered from scikit-learn estimator class order into the fixed taxonomy order. Train and validation metrics use the existing M2.4 `classification_metrics` helper.
- The run result is marked `smoke_test/provisional`, `synthetic_fixture`, and test `not_run`.

## Fixture results

The fixture contained 15 synthetic training vectors (3 per class) and 5 synthetic validation vectors (1 per class), each 384-dimensional. Training and validation families were distinct. Seed was `23`; LDA used 4 components; Logistic Regression used `lbfgs`, `C=1.0`, and `max_iter=1000`.

These intentionally well-separated synthetic vectors yielded train accuracy/macro-F1 of `1.0 / 1.0` and validation accuracy/macro-F1 of `1.0 / 1.0`; each confusion matrix was a 5×5 identity matrix (train diagonal 3 per class, validation diagonal 1 per class). These are fixture checks only and say nothing about E5, formal data or classification performance.

For each of the five labels, fixture precision, recall and F1 were all `1.0`; support was 3 in train and 1 in validation. These values are not usable as model-quality evidence.

Tests verify the four-dimensional projection, fixed score/prediction order, repeatability for a fixed seed, train-only fitting when validation features and labels change, family and record-ID isolation, rejection of non-384 inputs and missing train classes, and absence of a test parameter. The implementation does not accept test rows; `test_status` remains `not_run`.

## TDD and verification

The new public-seam test was run before implementation and failed with `ModuleNotFoundError: flycall_data.lda_baseline`. After implementation, the following relevant suites passed:

```text
test_lda_baseline.py       6 passed
test_evaluation.py        11 passed
test_embedding_pipeline.py 7 passed
test_embedding_logistic.py 3 passed
Total                    27 passed
```

The combined in-process unittest run completed with exit code 0. It reported peak RSS `117,784,576` bytes (about `112.3 MiB`). The M2.4 evaluator suite includes synthetic `PredictionBatch(split="test")` fixtures to verify its separate test gate; those are fabricated evaluator-unit-test values, not project test rows and were never passed to M2.3. The M2.3 model run itself had no test input and retained `test_status=not_run`. A separate `/usr/bin/time -l` wrapper printed test success but returned nonzero because its final `sysctl kern.clockrate` query was denied by the sandbox; the successful in-process run is the test result used here.

## Resource and dependency snapshot

- Existing environment: CPython `3.13.0`, scikit-learn `1.9.1`, NumPy `2.5.4`, SciPy `1.18.1`.
- `vm_stat` reported physical memory `8,589,934,592` bytes, system-wide free percentage `30%` before and `35%` after tests, and `Pages throttled: 0` both times. It does not provide an explicit Activity Monitor color state.
- Available disk: `32,381,712 KiB` before and `32,393,636 KiB` after (about `30.88` and `30.89 GiB`). The difference was `+11,924 KiB`; no cause is inferred.
- `sysctl` and process listing requests were denied by the sandbox, so a current swap total and full process RSS list were not obtained. The tested fixture run was small and used no model runtime.
- No package was installed, no model downloaded or loaded, and no formal dataset or model cache was created.

## Still blocked

- M2.2b's resource gate must pass before downloading/loading E5 or producing formal E5 embeddings.
- No formal data rows were read here. Once the embedding gate passes, only train and validation may enter this model; any run while records remain `pending_manual_review` is provisional. Test remains unused and `not_run`.
- A formal smoke run, its checkpoint/reload check, and actual embedding provenance validation are not complete. M2.3 must remain `in-progress`.
