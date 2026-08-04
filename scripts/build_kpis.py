"""
KPI Engineering
Builds daily / weekly business KPIs from cleaned tables.
Also writes SQL-style views and exports for Tableau / Excel.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
SQL_DIR = ROOT / "data" / "sql"
EXPORT = ROOT / "exports"
SQL_DIR.mkdir(exist_ok=True)
EXPORT.mkdir(exist_ok=True)

def load_clean():
    sales = pd.read_csv(PROC / "sales_clean.csv", parse_dates=["InvoiceDate"])
    sales["Date"] = pd.to_datetime(sales["Date"])
    products = pd.read_csv(PROC / "products_clean.csv")
    sessions = pd.read_csv(PROC / "sessions_clean.csv", parse_dates=["Date"])
    inventory = pd.read_csv(PROC / "inventory_clean.csv", parse_dates=["SnapshotDate"])
    returns = pd.read_csv(PROC / "returns_clean.csv", parse_dates=["InvoiceDate"])
    returns["Date"] = pd.to_datetime(returns["Date"])
    return sales, products, sessions, inventory, returns

def build_daily_kpis(sales, products, sessions, returns):
    # Enrich sales with cost
    sales = sales.merge(
        products[["StockCode", "CostPrice", "SupplierClean", "CategoryClean"]],
        on="StockCode", how="left"
    )
    sales["CostPrice"] = sales["CostPrice"].fillna(sales["UnitPrice"] * 0.55)
    sales["LineCost"] = sales["QuantityAbs"] * sales["CostPrice"]
    sales["LineProfit"] = sales["LineRevenue"] - (sales["Quantity"] * sales["CostPrice"])  # returns reduce profit

    # Daily sales side
    daily = sales.groupby("Date").agg(
        GrossRevenue=("LineRevenueAbs", "sum"),
        NetRevenue=("LineRevenue", "sum"),
        TotalCost=("LineCost", "sum"),
        Orders=("InvoiceNo", "nunique"),
        UnitsSold=("Quantity", lambda x: x[x > 0].sum()),
        ReturnUnits=("Quantity", lambda x: x[x < 0].abs().sum()),
        ReturnRows=("IsReturn", "sum"),
        UniqueCustomers=("CustomerID", "nunique")
    ).reset_index()

    # Refund amount
    refund_daily = returns.groupby("Date").agg(RefundAmount=("RefundAmount", "sum")).reset_index()
    daily = daily.merge(refund_daily, on="Date", how="left")
    daily["RefundAmount"] = daily["RefundAmount"].fillna(0)

    # Profit
    daily["Profit"] = daily["NetRevenue"] - daily["TotalCost"]   # already accounts for negative revenue on returns
    daily["ProfitMarginPct"] = np.where(daily["GrossRevenue"] > 0,
                                        daily["Profit"] / daily["GrossRevenue"] * 100, np.nan)

    # Conversion
    daily = daily.merge(sessions[["Date", "Sessions"]], on="Date", how="left")
    daily["Sessions"] = daily["Sessions"].ffill().fillna(daily["Orders"] * 40)
    daily["ConversionRate"] = daily["Orders"] / daily["Sessions"] * 100

    # Refund rate
    daily["RefundRatePct"] = np.where(daily["GrossRevenue"] > 0,
                                      daily["RefundAmount"] / daily["GrossRevenue"] * 100, 0)

    # Rolling baselines (for drift later)
    daily = daily.sort_values("Date")
    for col in ["Profit", "ConversionRate", "RefundRatePct", "GrossRevenue"]:
        daily[f"{col}_7d_avg"] = daily[col].rolling(7, min_periods=3).mean()
        daily[f"{col}_7d_std"] = daily[col].rolling(7, min_periods=3).std()

    daily.to_csv(PROC / "daily_kpis.csv", index=False)
    print(f"[KPI] Daily KPIs: {daily.shape}")
    return daily, sales

def build_supplier_kpis(sales):
    # Weekly supplier performance
    sales["YearWeek"] = sales["InvoiceDate"].dt.strftime("%Y-%W")
    sup = sales[sales["Quantity"] > 0].groupby(["YearWeek", "SupplierClean"]).agg(
        Revenue=("LineRevenueAbs", "sum"),
        Units=("Quantity", "sum"),
        AvgUnitPrice=("UnitPrice", "mean"),
        Orders=("InvoiceNo", "nunique")
    ).reset_index()
    sup.to_csv(PROC / "supplier_weekly_kpis.csv", index=False)
    print(f"[KPI] Supplier weekly: {sup.shape}")
    return sup

def build_inventory_kpis(inventory, sales):
    inv = inventory.copy()
    inv["Date"] = inv["SnapshotDate"]
    daily_inv = inv.groupby("Date").agg(
        Snapshots=("StockCode", "count"),
        NegativeStockCount=("IsNegativeStock", "sum"),
        MissingQtyCount=("IsMissingQty", "sum"),
        TotalOnHand=("OnHandQty", "sum")
    ).reset_index()
    daily_inv["InconsistencyRatePct"] = (
        (daily_inv["NegativeStockCount"] + daily_inv["MissingQtyCount"]) / daily_inv["Snapshots"] * 100
    )
    daily_inv.to_csv(PROC / "inventory_daily_kpis.csv", index=False)
    print(f"[KPI] Inventory daily: {daily_inv.shape}")
    return daily_inv

def create_sqlite_and_sql_views(daily, sales):
    """Create a SQLite DB so users can practice pure SQL KPI queries."""
    db_path = SQL_DIR / "kpi_drift.db"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)

    daily.to_sql("daily_kpis", conn, if_exists="replace", index=False)
    # Sample of sales for SQL practice (full table is large)
    sales_sample = sales[["InvoiceNo", "StockCode", "Quantity", "UnitPrice", "InvoiceDate",
                          "CustomerID", "Country", "IsReturn", "LineRevenue", "Date",
                          "SupplierClean", "CategoryClean"]].sample(n=min(50000, len(sales)), random_state=42)
    sales_sample.to_sql("sales_sample", conn, if_exists="replace", index=False)

    # Example SQL views / queries saved as .sql files
    queries = {
        "01_daily_profit_trend.sql": """
-- Daily Profit & Margin
SELECT Date,
       ROUND(Profit, 2) AS Profit,
       ROUND(ProfitMarginPct, 2) AS MarginPct,
       ROUND(GrossRevenue, 2) AS GrossRevenue,
       ROUND(RefundAmount, 2) AS Refunds
FROM daily_kpis
ORDER BY Date;
""",
        "02_conversion_drop_detection.sql": """
-- Conversion rate with previous day and 7-day average
SELECT Date,
       ROUND(ConversionRate, 3) AS ConversionRate,
       ROUND(ConversionRate_7d_avg, 3) AS Avg7d,
       ROUND( (ConversionRate - ConversionRate_7d_avg) / NULLIF(ConversionRate_7d_avg,0) * 100 , 1) AS PctVs7d
FROM daily_kpis
WHERE ConversionRate_7d_avg IS NOT NULL
ORDER BY Date;
""",
        "03_refund_spike.sql": """
-- Days with unusually high refund rate
SELECT Date,
       ROUND(RefundRatePct, 2) AS RefundRatePct,
       ROUND(RefundRatePct_7d_avg, 2) AS Avg7d,
       ROUND(RefundAmount, 2) AS RefundAmount
FROM daily_kpis
WHERE RefundRatePct > RefundRatePct_7d_avg + 2 * RefundRatePct_7d_std
ORDER BY RefundRatePct DESC;
""",
        "04_top_return_skus.sql": """
-- Top SKUs by refund amount (using sample table)
SELECT StockCode,
       SUM(CASE WHEN Quantity < 0 THEN Quantity * -1 * UnitPrice ELSE 0 END) AS RefundAmt,
       SUM(CASE WHEN Quantity < 0 THEN 1 ELSE 0 END) AS ReturnLines
FROM sales_sample
GROUP BY StockCode
HAVING RefundAmt > 0
ORDER BY RefundAmt DESC
LIMIT 20;
"""
    }
    for name, sql in queries.items():
        (SQL_DIR / name).write_text(sql.strip())

    conn.close()
    print(f"[SQL] SQLite DB + example queries → {db_path}")

def export_for_bi(daily, inv_kpi, sup_kpi):
    """Dashboard-ready flat files."""
    daily.to_csv(EXPORT / "daily_kpis_for_dashboard.csv", index=False)
    inv_kpi.to_csv(EXPORT / "inventory_kpis_for_dashboard.csv", index=False)
    sup_kpi.to_csv(EXPORT / "supplier_kpis_for_dashboard.csv", index=False)

    # Excel multi-sheet for stakeholders who live in Excel
    with pd.ExcelWriter(EXPORT / "KPI_Summary_Workbook.xlsx", engine="xlsxwriter") as writer:
        daily.tail(60).to_excel(writer, sheet_name="Last_60_Days_KPIs", index=False)
        daily.describe().to_excel(writer, sheet_name="KPI_Stats")
        inv_kpi.tail(30).to_excel(writer, sheet_name="Inventory_Recent", index=False)
    print("[Export] Dashboard CSVs + Excel workbook ready")

if __name__ == "__main__":
    sales, products, sessions, inventory, returns = load_clean()
    daily, sales_enriched = build_daily_kpis(sales, products, sessions, returns)
    sup = build_supplier_kpis(sales_enriched)
    inv_kpi = build_inventory_kpis(inventory, sales)
    create_sqlite_and_sql_views(daily, sales_enriched)
    export_for_bi(daily, inv_kpi, sup)
    print("\n✅ Phase 05 complete")
