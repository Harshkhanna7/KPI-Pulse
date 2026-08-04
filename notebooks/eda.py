"""
Lightweight EDA (run as script or convert to notebook)
Produces a few key plots and summary tables saved to exports/
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
EXPORT = ROOT / "exports"
EXPORT.mkdir(exist_ok=True)

daily = pd.read_csv(PROC / "daily_kpis.csv", parse_dates=["Date"])
sales = pd.read_csv(PROC / "sales_clean.csv", parse_dates=["InvoiceDate"])

# 1. Profit over time
fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(daily["Date"], daily["Profit"], label="Daily Profit", alpha=0.7)
ax.plot(daily["Date"], daily["Profit_7d_avg"], label="7d Avg", linewidth=2)
ax.axhline(0, color="red", linestyle="--", alpha=0.5)
ax.set_title("Daily Profit with 7-day Moving Average")
ax.legend()
fig.tight_layout()
fig.savefig(EXPORT / "eda_profit_trend.png", dpi=120)
plt.close()

# 2. Conversion & Refund dual axis
fig, ax1 = plt.subplots(figsize=(12, 4))
ax1.plot(daily["Date"], daily["ConversionRate"], color="tab:blue", label="Conversion %")
ax1.set_ylabel("Conversion Rate %", color="tab:blue")
ax2 = ax1.twinx()
ax2.plot(daily["Date"], daily["RefundRatePct"], color="tab:red", alpha=0.7, label="Refund Rate %")
ax2.set_ylabel("Refund Rate %", color="tab:red")
ax1.set_title("Conversion Rate vs Refund Rate")
fig.tight_layout()
fig.savefig(EXPORT / "eda_conversion_refund.png", dpi=120)
plt.close()

# 3. Returns by reason
returns = pd.read_csv(PROC / "returns_clean.csv")
reason_counts = returns["ReturnReasonClean"].value_counts()
fig, ax = plt.subplots(figsize=(8, 4))
reason_counts.plot(kind="bar", ax=ax, color="salmon")
ax.set_title("Return Reasons (cleaned)")
ax.set_ylabel("Count")
fig.tight_layout()
fig.savefig(EXPORT / "eda_return_reasons.png", dpi=120)
plt.close()

print("EDA plots saved to exports/")
print(daily[["Profit", "ConversionRate", "RefundRatePct"]].describe().round(2))
