# KPI Pulse

Detect sudden shifts in business metrics and rank what likely caused them.

Instead of monitoring models, this pipeline watches the numbers finance and ops actually care about:

- profit
- conversion rate
- refund rate
- inventory consistency
- supplier anomalies

When something moves outside a normal range it flags the day and ranks possible causes (refund spike, specific SKUs, volume drop, etc.).

---

### Results

Open **`results/index.html`** in a browser for charts and sample alerts.

Or check the PNGs in `results/` and the CSVs in `exports/`.

Quick takeaways from the run:
- 63 alerts over Dec 2010 – Dec 2011 (31 high severity)
- Early Jan profit drops mostly tied to refund spikes
- Inventory snapshots regularly show negative / missing stock (data quality issue)

More detail in `findings.md`.

---

### Data

- **UCI Online Retail** (real UK e-commerce transactions, ~542k rows) — already messy: returns, missing IDs, cancellations
- Extra tables for suppliers, inventory snapshots and website sessions (with realistic noise)

Raw files live in `data/raw/`. Cleaned + KPI tables in `data/processed/`.

---

### Run it

```bash
pip install -r requirements.txt
python scripts/run_all.py
```

Steps individually:
```bash
python scripts/clean_data.py
python scripts/build_kpis.py
python scripts/detect_drift.py
python scripts/explain_causes.py
```

SQL examples are in `data/sql/` (SQLite).

---

### Stack

Python · pandas · scikit-learn · SQL · Excel · Tableau (optional — CSVs in `exports/` are ready to connect)

---

### Folder overview

```
scripts/     clean → KPIs → drift → root cause
data/        raw + processed + sql
results/     charts + HTML summary
exports/     dashboard-ready CSVs and Excel
notebooks/   quick EDA
```
