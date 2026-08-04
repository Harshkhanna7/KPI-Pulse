-- Daily Profit & Margin
SELECT Date,
       ROUND(Profit, 2) AS Profit,
       ROUND(ProfitMarginPct, 2) AS MarginPct,
       ROUND(GrossRevenue, 2) AS GrossRevenue,
       ROUND(RefundAmount, 2) AS Refunds
FROM daily_kpis
ORDER BY Date;