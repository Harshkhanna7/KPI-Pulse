-- Days with unusually high refund rate
SELECT Date,
       ROUND(RefundRatePct, 2) AS RefundRatePct,
       ROUND(RefundRatePct_7d_avg, 2) AS Avg7d,
       ROUND(RefundAmount, 2) AS RefundAmount
FROM daily_kpis
WHERE RefundRatePct > RefundRatePct_7d_avg + 2 * RefundRatePct_7d_std
ORDER BY RefundRatePct DESC;