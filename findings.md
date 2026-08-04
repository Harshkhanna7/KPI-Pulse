# Findings

Ran the pipeline on UCI Online Retail (Dec 2010 – Dec 2011) plus the supplier / inventory / session tables.

**63 alerts total, 31 high severity.**

A few things that stood out:

1. **Profit drops in early January** were mostly refund-driven. The ranker put “Elevated Refunds” first (~0.37). A lot of the volume sat on a small set of SKUs (including AMAZONFEE-type lines).

2. **Conversion anomalies** sometimes fired together with the multi-KPI Isolation Forest flag. That was a useful signal that more than one metric was off at the same time.

3. **Inventory** — negative on-hand and missing counts show up often. Looks more like process / system lag than pure demand changes.

Charts and a clickable summary are in `results/index.html`.  
Alert and root-cause tables are also exported as CSV under `exports/` and `results/`.
