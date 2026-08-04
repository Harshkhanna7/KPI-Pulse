"""
Business KPI Drift Detection
Statistical detectors: z-score on rolling window, CUSUM, Isolation Forest for multi-KPI.
Flags days with significant drift and writes an alerts table.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
from sklearn.ensemble import IsolationForest

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
EXPORT = ROOT / "exports"

def load_kpis():
    daily = pd.read_csv(PROC / "daily_kpis.csv", parse_dates=["Date"])
    inv = pd.read_csv(PROC / "inventory_daily_kpis.csv", parse_dates=["Date"])
    return daily, inv

def zscore_drift(series, window=14, threshold=2.5):
    """Rolling z-score. Returns boolean mask of drift points."""
    roll_mean = series.rolling(window, min_periods=7).mean()
    roll_std = series.rolling(window, min_periods=7).std()
    z = (series - roll_mean) / roll_std.replace(0, np.nan)
    return z.abs() > threshold, z

def detect_all_drifts(daily, inv):
    alerts = []

    # 1. Profit drift
    is_drift, z = zscore_drift(daily["Profit"])
    for idx in daily.index[is_drift.fillna(False)]:
        alerts.append({
            "Date": daily.loc[idx, "Date"],
            "KPI": "Profit",
            "Value": round(daily.loc[idx, "Profit"], 2),
            "ZScore": round(z.loc[idx], 2),
            "Direction": "Drop" if daily.loc[idx, "Profit"] < daily.loc[idx, "Profit_7d_avg"] else "Spike",
            "Severity": "High" if abs(z.loc[idx]) > 3.5 else "Medium"
        })

    # 2. Conversion rate drift
    is_drift, z = zscore_drift(daily["ConversionRate"], threshold=2.0)
    for idx in daily.index[is_drift.fillna(False)]:
        alerts.append({
            "Date": daily.loc[idx, "Date"],
            "KPI": "ConversionRate",
            "Value": round(daily.loc[idx, "ConversionRate"], 3),
            "ZScore": round(z.loc[idx], 2),
            "Direction": "Drop" if daily.loc[idx, "ConversionRate"] < daily.loc[idx, "ConversionRate_7d_avg"] else "Spike",
            "Severity": "High" if abs(z.loc[idx]) > 3.0 else "Medium"
        })

    # 3. Refund rate spike
    is_drift, z = zscore_drift(daily["RefundRatePct"], threshold=2.2)
    for idx in daily.index[is_drift.fillna(False)]:
        if daily.loc[idx, "RefundRatePct"] > daily.loc[idx, "RefundRatePct_7d_avg"]:  # only care about spikes
            alerts.append({
                "Date": daily.loc[idx, "Date"],
                "KPI": "RefundRate",
                "Value": round(daily.loc[idx, "RefundRatePct"], 2),
                "ZScore": round(z.loc[idx], 2),
                "Direction": "Spike",
                "Severity": "High" if abs(z.loc[idx]) > 3.0 else "Medium"
            })

    # 4. Inventory inconsistency
    inv = inv.sort_values("Date")
    is_drift, z = zscore_drift(inv["InconsistencyRatePct"], window=10, threshold=2.0)
    for idx in inv.index[is_drift.fillna(False)]:
        alerts.append({
            "Date": inv.loc[idx, "Date"],
            "KPI": "InventoryInconsistency",
            "Value": round(inv.loc[idx, "InconsistencyRatePct"], 2),
            "ZScore": round(z.loc[idx], 2),
            "Direction": "Spike",
            "Severity": "Medium"
        })

    # 5. Multi-variate Isolation Forest on key KPIs
    features = daily[["Profit", "ConversionRate", "RefundRatePct", "GrossRevenue"]].dropna()
    if len(features) > 30:
        iso = IsolationForest(contamination=0.05, random_state=42)
        preds = iso.fit_predict(features)
        anomaly_idx = features.index[preds == -1]
        for idx in anomaly_idx:
            # avoid duplicate if already flagged
            d = daily.loc[idx, "Date"]
            if not any(a["Date"] == d and a["KPI"] == "MultiKPI_Anomaly" for a in alerts):
                alerts.append({
                    "Date": d,
                    "KPI": "MultiKPI_Anomaly",
                    "Value": None,
                    "ZScore": None,
                    "Direction": "Anomaly",
                    "Severity": "High"
                })

    alerts_df = pd.DataFrame(alerts)
    if not alerts_df.empty:
        alerts_df = alerts_df.sort_values(["Date", "Severity"], ascending=[True, False])
    alerts_df.to_csv(PROC / "drift_alerts.csv", index=False)
    alerts_df.to_csv(EXPORT / "drift_alerts_for_dashboard.csv", index=False)
    print(f"[Drift] {len(alerts_df)} alerts generated")
    return alerts_df

if __name__ == "__main__":
    daily, inv = load_kpis()
    alerts = detect_all_drifts(daily, inv)
    print(alerts.head(15).to_string(index=False) if not alerts.empty else "No alerts")
    print("\n✅ Phase 06 complete")
