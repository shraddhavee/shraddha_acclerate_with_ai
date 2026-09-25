from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

from agents.orchestrator import approve_bronze, approve_gold, approve_silver, new_state, profile_and_prepare, resume_state

st.set_page_config(page_title="Retail Medallion Pipeline", layout="wide")
st.title("Retail Medallion Pipeline")
st.caption("Synthetic or uploaded retail CSVs, with human approval at every data contract boundary.")

if "state" not in st.session_state:
    st.session_state.state = None

uploads = st.file_uploader("Upload retail CSV files", type="csv", accept_multiple_files=True)
intent = st.text_area("Business intent", value="Understand retail performance by product and period")
resume_run_id = st.text_input("Resume run ID", help="Load a persisted run waiting at an approval gate.")

if st.button("Resume run"):
    try:
        st.session_state.state = resume_state(resume_run_id.strip())
        st.rerun()
    except (FileNotFoundError, ValueError) as exc:
        st.error(f"Unable to resume run: {exc}")

if st.button("Profile and create Bronze STTM", type="primary"):
    if not uploads:
        st.error("Upload at least one CSV.")
    else:
        paths = []
        upload_dir = Path("data/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        for upload in uploads:
            path = upload_dir / upload.name
            path.write_bytes(upload.getvalue())
            paths.append(str(path))
        st.session_state.state = profile_and_prepare(new_state(paths, intent))

state = st.session_state.state
if state:
    st.info(f"Run {state.run_id} | Status: {state.status}")
    if state.profile_path:
        with st.expander("Profile", expanded=False):
            st.json(Path(state.profile_path).read_text(encoding="utf-8"))
    for layer, path in (("Bronze", state.sttm_bronze_path), ("Silver", state.sttm_silver_path), ("Gold", state.sttm_gold_path)):
        if path and Path(path).exists():
            st.subheader(f"{layer} STTM")
            frame = pd.read_csv(path)
            st.dataframe(frame, use_container_width=True)
            if state.status == f"awaiting_{layer.lower()}_approval":
                left, right = st.columns(2)
                with left:
                    if st.button(f"Approve {layer}", key=f"approve_{layer}"):
                        handler = {"Bronze": approve_bronze, "Silver": approve_silver, "Gold": approve_gold}[layer]
                        st.session_state.state = handler(state, True)
                        st.rerun()
                with right:
                    if st.button(f"Reject {layer}", key=f"reject_{layer}"):
                        handler = {"Bronze": approve_bronze, "Silver": approve_silver, "Gold": approve_gold}[layer]
                        st.session_state.state = handler(state, False)
                        st.rerun()
    if state.status == "completed" and state.report_path:
        st.success("Pipeline completed. Gold data and the executive report are ready.")
        st.subheader("Executive report")
        st.components.v1.html(Path(state.report_path).read_text(encoding="utf-8"), height=700, scrolling=True)
        st.download_button("Download report", Path(state.report_path).read_bytes(), file_name="retail_report.html")
        st.write("Gold Parquet outputs")
        for output in state.gold_output_paths:
            st.code(output)
    if state.errors:
        st.error("\n".join(state.errors))
