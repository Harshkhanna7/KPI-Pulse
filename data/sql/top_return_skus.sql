-- Top SKUs by refund amount (using sample table)
SELECT StockCode,
       SUM(CASE WHEN Quantity < 0 THEN Quantity * -1 * UnitPrice ELSE 0 END) AS RefundAmt,
       SUM(CASE WHEN Quantity < 0 THEN 1 ELSE 0 END) AS ReturnLines
FROM sales_sample
GROUP BY StockCode
HAVING RefundAmt > 0
ORDER BY RefundAmt DESC
LIMIT 20;