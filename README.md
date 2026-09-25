# Retail Medallion Pipeline

A Python 3.11-compatible retail CSV pipeline with Bronze, Silver, and Gold approval gates. Transformations are deterministic. Groq is optional and reserved for profiling interpretation, STTM suggestions, and report narrative; tests and the default pipeline run without an API key.

## Run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python cli.py path\to\sales.csv --intent "Review product performance" --auto-approve
streamlit run streamlit_app.py
```

The normal workflow pauses after each generated STTM. Review and change `approval_status` to `approved` through the Streamlit controls or your own review process. Ambiguous joins and business rules remain pending rather than being guessed. `--auto-approve` is intended only for synthetic demos.

## Synthetic demo

Create a clearly labelled demo CSV with columns such as `order_id`, `product`, `order_date`, `quantity`, and `sales_amount`. The checked-in fixtures are `data/synthetic_demo_retail_sales.csv` and `data/synthetic_demo_retail_customers.csv`. Do not use synthetic data in production decisions without labelling it. Generated artifacts live under `data/`; secrets are loaded from `.env`, which is ignored by Git.

## Phase 4 verification

```powershell
python -m pip install -r requirements.txt
python -m pip check
python -c "import duckdb, pandas, plotly, pyarrow, streamlit; print('dependencies-ok')"
python cli.py data\synthetic_demo_retail_sales.csv --intent "Review synthetic sales" --auto-approve
```

The CLI writes Gold Parquet under `data/gold/`, trace JSONL under `data/traces/`, and the executive HTML report under `data/reports/`. The Streamlit completion view embeds the saved report and provides a download control. Groq is optional; tests and deterministic transformations run without a live API key.

## Tests

```powershell
pytest -q
```
