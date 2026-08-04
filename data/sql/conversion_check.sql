-- Conversion rate with previous day and 7-day average
SELECT Date,
       ROUND(ConversionRate, 3) AS ConversionRate,
       ROUND(ConversionRate_7d_avg, 3) AS Avg7d,
       ROUND( (ConversionRate - ConversionRate_7d_avg) / NULLIF(ConversionRate_7d_avg,0) * 100 , 1) AS PctVs7d
FROM daily_kpis
WHERE ConversionRate_7d_avg IS NOT NULL
ORDER BY Date;