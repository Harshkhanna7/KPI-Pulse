"""
Automatic Root Cause Ranking
For each drift alert, compute simple contribution scores from related dimensions
and rank possible causes by probability / contribution.
"""

import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
EXPORT = ROOT / "exports"

def load():
    alerts = pd.read_csv(PROC / "drift_alerts.csv", parse_dates=["Date"])
    daily = pd.read_csv(PROC / "daily_kpis.csv", parse_dates=["Date"])
    sales = pd.read_csv(PROC / "sales_clean.csv", parse_dates=["InvoiceDate", "Date"])
    products = pd.read_csv(PROC / "products_clean.csv")
    returns = pd.read_csv(PROC / "returns_clean.csv", parse_dates=["Date"])
    inv = pd.read_csv(PROC / "inventory_daily_kpis.csv", parse_dates=["Date"])
    return alerts, daily, sales, products, returns, inv

def explain_profit_drop(alert_date, sales, products, returns, daily):
    """Rank causes for a profit drop on a given day."""
    day = pd.Timestamp(alert_date)
    window_start = day - pd.Timedelta(days=7)

    # Recent vs baseline
    recent = sales[(sales["Date"] >= window_start) & (sales["Date"] <= day)]
    baseline = sales[(sales["Date"] >= window_start - pd.Timedelta(days=14)) & (sales["Date"] < window_start)]

    causes = []

    # 1. Refund contribution
    recent_refund = returns[(returns["Date"] >= window_start) & (returns["Date"] <= day)]["RefundAmount"].sum()
    base_refund = returns[(returns["Date"] >= window_start - pd.Timedelta(days=14)) & (returns["Date"] < window_start)]["RefundAmount"].sum()
    if base_refund > 0:
        refund_lift = (recent_refund - base_refund) / base_refund
    else:
        refund_lift = 1.0 if recent_refund > 0 else 0
    causes.append({
        "Cause": "Elevated Refunds / Returns",
        "Evidence": f"Refunds in last 7d: £{recent_refund:,.0f} vs prior 14d avg period",
        "Score": min(0.95, max(0.1, abs(refund_lift) * 0.6 + 0.2)),
        "Detail": f"Lift ≈ {refund_lift:.1%}"
    })

    # 2. High-return SKUs
    top_return_skus = recent[recent["IsReturn"]].groupby("StockCode")["LineRevenueAbs"].sum().nlargest(5)
    if len(top_return_skus) > 0:
        causes.append({
            "Cause": "Specific SKU Return Spike",
            "Evidence": f"Top return SKUs: {', '.join(top_return_skus.index.astype(str)[:3])}",
            "Score": 0.55,
            "Detail": f"Top SKU refund volume £{top_return_skus.iloc[0]:,.0f}"
        })

    # 3. Supplier cost pressure (if cost data present)
    if "SupplierClean" in recent.columns:
        # crude: higher average unit price from a supplier
        causes.append({
            "Cause": "Supplier Price / Mix Change",
            "Evidence": "Possible shift in supplier mix or cost",
            "Score": 0.35,
            "Detail": "Check supplier_weekly_kpis for price outliers"
        })

    # 4. Volume drop
    recent_orders = recent["InvoiceNo"].nunique()
    base_orders = baseline["InvoiceNo"].nunique() / 2  # rough daily equivalent
    if base_orders > 0 and recent_orders < base_orders * 0.8:
        causes.append({
            "Cause": "Order Volume Decline",
            "Evidence": f"Orders in window lower than baseline",
            "Score": 0.45,
            "Detail": f"Recent unique invoices: {recent_orders}"
        })

    # 5. Category mix
    causes.append({
        "Cause": "Unfavourable Product Mix",
        "Evidence": "Higher share of low-margin categories possible",
        "Score": 0.25,
        "Detail": "Inspect CategoryClean profit contribution"
    })

    # Normalise scores to sum ~1 for ranking
    total = sum(c["Score"] for c in causes) or 1
    for c in causes:
        c["Probability"] = round(c["Score"] / total, 3)
    causes = sorted(causes, key=lambda x: -x["Probability"])
    return causes

def explain_conversion_drop(alert_date, daily, sales):
    causes = []
    day = pd.Timestamp(alert_date)
    row = daily[daily["Date"] == day]
    if row.empty:
        return [{"Cause": "Insufficient data", "Probability": 1.0, "Evidence": "", "Detail": ""}]

    conv = row["ConversionRate"].values[0]
    avg = row["ConversionRate_7d_avg"].values[0]
    causes.append({
        "Cause": "Traffic Quality / Channel Mix Shift",
        "Evidence": f"Conversion {conv:.2f}% vs 7d avg {avg:.2f}%",
        "Score": 0.4,
        "Detail": "Check ChannelClean distribution in sessions"
    })
    causes.append({
        "Cause": "Site / Checkout Friction (technical)",
        "Evidence": "Possible page latency or payment issues",
        "Score": 0.3,
        "Detail": "Correlate with device mix (Mobile vs Desktop)"
    })
    causes.append({
        "Cause": "Pricing or Promotion Change",
        "Evidence": "Sudden price increase or promo end",
        "Score": 0.2,
        "Detail": "Review UnitPrice distribution day-of vs prior"
    })
    causes.append({
        "Cause": "Seasonality / Day-of-Week Effect",
        "Evidence": "Weekend or holiday pattern",
        "Score": 0.1,
        "Detail": day.day_name()
    })
    total = sum(c["Score"] for c in causes)
    for c in causes:
        c["Probability"] = round(c["Score"] / total, 3)
    return sorted(causes, key=lambda x: -x["Probability"])

def explain_refund_spike(alert_date, returns, sales):
    day = pd.Timestamp(alert_date)
    window = returns[(returns["Date"] >= day - pd.Timedelta(days=3)) & (returns["Date"] <= day)]
    reasons = window["ReturnReasonClean"].value_counts(normalize=True).head(3)
    causes = []
    for reason, pct in reasons.items():
        causes.append({
            "Cause": f"Return Reason: {reason}",
            "Evidence": f"{pct:.0%} of recent returns",
            "Score": float(pct),
            "Detail": f"Count in 3-day window: {(window['ReturnReasonClean']==reason).sum()}"
        })
    if not causes:
        causes.append({"Cause": "Unspecified quality issue", "Evidence": "", "Score": 0.5, "Detail": ""})
    # SKU concentration
    top_sku = window.groupby("StockCode")["RefundAmount"].sum().nlargest(1)
    if len(top_sku) > 0:
        causes.append({
            "Cause": f"Concentrated on SKU {top_sku.index[0]}",
            "Evidence": f"£{top_sku.iloc[0]:,.0f} refunded",
            "Score": 0.35,
            "Detail": "Investigate product quality / description mismatch"
        })
    total = sum(c["Score"] for c in causes) or 1
    for c in causes:
        c["Probability"] = round(c["Score"] / total, 3)
    return sorted(causes, key=lambda x: -x["Probability"])

def explain_inventory(alert_date, inv):
    return [{
        "Cause": "Warehouse count process failure or system sync lag",
        "Evidence": "Negative or missing OnHandQty spikes",
        "Probability": 0.55,
        "Detail": "Check WH-London vs WH-North naming consistency"
    }, {
        "Cause": "Unrecorded returns put back into stock incorrectly",
        "Evidence": "High return volume + inventory mismatch",
        "Probability": 0.30,
        "Detail": "Reconcile returns_clean with inventory snapshots"
    }, {
        "Cause": "Theft / shrinkage or data entry error",
        "Evidence": "Persistent negative stock",
        "Probability": 0.15,
        "Detail": "Physical cycle count recommended"
    }]

def build_explanations(alerts, daily, sales, products, returns, inv):
    rows = []
    # Deduplicate by Date+KPI (keep highest severity)
    alerts = alerts.drop_duplicates(subset=["Date", "KPI"], keep="first")

    for _, alert in alerts.iterrows():
        kpi = alert["KPI"]
        dt = alert["Date"]
        if kpi == "Profit":
            causes = explain_profit_drop(dt, sales, products, returns, daily)
        elif kpi == "ConversionRate":
            causes = explain_conversion_drop(dt, daily, sales)
        elif kpi == "RefundRate":
            causes = explain_refund_spike(dt, returns, sales)
        elif kpi == "InventoryInconsistency":
            causes = explain_inventory(dt, inv)
        else:
            causes = [{"Cause": "Multi-dimensional anomaly – investigate Profit + Conversion + Refunds together",
                       "Probability": 1.0, "Evidence": "Isolation Forest flag", "Detail": ""}]

        for rank, c in enumerate(causes[:4], 1):
            rows.append({
                "AlertDate": dt,
                "KPI": kpi,
                "Severity": alert.get("Severity", ""),
                "Rank": rank,
                "Cause": c["Cause"],
                "Probability": c.get("Probability", c.get("Score", 0)),
                "Evidence": c.get("Evidence", ""),
                "Detail": c.get("Detail", "")
            })

    exp_df = pd.DataFrame(rows)
    exp_df.to_csv(PROC / "root_cause_explanations.csv", index=False)
    exp_df.to_csv(EXPORT / "root_cause_for_dashboard.csv", index=False)
    print(f"[RootCause] {len(exp_df)} ranked explanations written")
    return exp_df

if __name__ == "__main__":
    alerts, daily, sales, products, returns, inv = load()
    # Enrich sales with supplier for root cause
    products_small = products[["StockCode", "SupplierClean", "CategoryClean", "CostPrice"]]
    sales = sales.merge(products_small, on="StockCode", how="left")
    exp = build_explanations(alerts, daily, sales, products, returns, inv)
    print(exp.head(12).to_string(index=False))
    print("\n✅ Phase 07 complete")
