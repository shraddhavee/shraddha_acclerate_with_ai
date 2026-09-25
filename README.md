# Retail Medallion Pipeline

A Python 3.11-compatible retail CSV pipeline with Bronze, Silver, and Gold approval gates. STTM suggestions and report narratives use an optional LangChain prompt chain backed by Groq, with deterministic intent-aware fallbacks when no API key is configured. Human approval remains required for generated contracts.

## Run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python cli.py path\to\sales.csv --intent "Review product performance" --auto-approve
streamlit run streamlit_app.py
```

The normal workflow pauses after each generated STTM. Review and change `approval_status` to `approved` through the interactive CLI or Streamlit controls. Silver rules and Gold KPI suggestions incorporate the supplied business intent; ambiguous joins and business rules remain pending rather than being guessed. `--auto-approve` is intended only for synthetic demos.

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
