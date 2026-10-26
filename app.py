"""Local Streamlit research demo for the locked FlyCall predictor."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from flycall_data.predictor import FlyCallPredictor, PredictorError  # noqa: E402


def main() -> None:
    try:
        import streamlit as st
    except ImportError as error:
        raise SystemExit(
            "Install the optional demo dependency in the model environment with "
            "`uv pip install --python <venv-python> -r requirements-demo.txt`."
        ) from error

    st.set_page_config(page_title="FlyCall-1999 研究 Demo", page_icon="☎️", layout="centered")
    st.title("FlyCall-1999 服務分類研究 Demo")
    st.caption("合成資料訓練 · 研究 Demo · 模擬派送")
    st.warning(
        "模型以合成資料訓練，資料逐筆人工複核仍待完成。結果只供研究展示；每筆都需要人工確認，"
        "此頁不會送出或執行真實派工。"
    )

    manifest_text = os.environ.get("FLYCALL_MODEL_MANIFEST", "")
    snapshot_text = os.environ.get("E5_SNAPSHOT", "")
    if not manifest_text or not snapshot_text:
        st.error(
            "尚未設定 FLYCALL_MODEL_MANIFEST 與 E5_SNAPSHOT。請先放入通過 checksum、候選鎖定與設定鎖定的模型 manifest。"
        )
        return
    manifest_path = Path(manifest_text)
    snapshot_path = Path(snapshot_text)

    @st.cache_resource(show_spinner="正在驗證模型檔案並載入本機模型…")
    def load_predictor(manifest_name: str, model_snapshot: str, manifest_sha256: str) -> FlyCallPredictor:
        return FlyCallPredictor.from_locked_manifest(
            Path(manifest_name),
            e5_snapshot=Path(model_snapshot),
        )

    try:
        manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        predictor = load_predictor(str(manifest_path), str(snapshot_path), manifest_sha256)
    except (PredictorError, OSError, RuntimeError, ValueError) as error:
        st.error(f"模型未載入：{error}")
        return

    transcript = st.text_area(
        "通話逐字稿",
        height=220,
        placeholder="貼上單筆逐字稿；本 Demo 不會讀取專案資料集。",
    )
    if st.button("分類（研究展示）", type="primary"):
        try:
            prediction = predictor.predict(transcript)
        except (PredictorError, RuntimeError, ValueError) as error:
            st.error(f"無法分類：{error}")
            return

        st.subheader("模擬分類結果")
        st.metric("預測類別", prediction.predicted_label)
        st.write("流程：" + " → ".join(prediction.stages))
        st.dataframe(
            [
                {
                    "服務類別": label,
                    "分數": probability,
                    "Logit": logit,
                }
                for label, probability, logit in zip(
                    prediction.label_order,
                    prediction.probabilities,
                    prediction.logits,
                    strict=True,
                )
            ],
            hide_index=True,
            width="stretch",
        )
        st.info(f"模擬派送類別：{prediction.predicted_label}。請由人工確認後再決定後續處理；未執行真實派工。")


if __name__ == "__main__":
    main()
