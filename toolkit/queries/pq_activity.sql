-- Post-quantum outputs since activation: totals by script type, by month, the busiest addresses and the size of the spending transactions. Schema: the project's block indexer.
-- The block range is the one counted in REPORT.md section 6 (activation to the count of 11 November 2026). This query selects
-- post-quantum outputs by address prefix; the other two select by script type; on this chain the two select the same outputs.
-- A spend counts only if the spending transaction is itself inside the block range, so the result does not change
-- when the query is run later on a longer chain.
SET NOCOUNT ON; SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
SELECT o.Id, o.Amount, o.Address, CAST(CASE WHEN o.IsSpent = 1 AND sb.Height <= 4417513 THEN 1 ELSE 0 END AS bit) AS IsSpent, CASE WHEN o.IsSpent = 1 AND sb.Height <= 4417513 THEN o.SpentByTxId END AS SpentByTxId, o.ScriptType, b.Height, b.Timestamp AS T
INTO #pq FROM dbo.Outputs o JOIN dbo.Transactions t ON t.Id = o.TransactionId JOIN dbo.Blocks b ON b.Id = t.BlockId LEFT JOIN dbo.Transactions st ON st.TxId = o.SpentByTxId LEFT JOIN dbo.Blocks sb ON sb.Id = st.BlockId
WHERE b.Height BETWEEN 4250000 AND 4417513 AND o.IsOrphaned = 0 AND o.Address LIKE 'BQ%' COLLATE Latin1_General_BIN2;
SELECT ScriptType, COUNT(*) AS Outputs, SUM(CAST(IsSpent AS int)) AS Spent, COUNT(DISTINCT Address) AS Addresses, COUNT(DISTINCT SpentByTxId) AS SpendingTxs, SUM(Amount)/100000000 AS BLZ, MIN(Height) AS FirstHeight, MAX(Height) AS LastHeight FROM #pq GROUP BY ScriptType;
SELECT CONVERT(char(7), T, 120) AS Month, COUNT(*) AS Created, SUM(CAST(IsSpent AS int)) AS OfWhichSpent, COUNT(DISTINCT Address) AS Addresses FROM #pq GROUP BY CONVERT(char(7), T, 120) ORDER BY 1;
SELECT TOP 8 Address, COUNT(*) AS Outputs, SUM(CAST(IsSpent AS int)) AS Spent FROM #pq GROUP BY Address ORDER BY COUNT(*) DESC;
SELECT COUNT(*) AS SpendTxs, AVG(CAST(t.SizeBytes AS float)) AS AvgBytes, MAX(t.SizeBytes) AS MaxBytes, SUM(CAST(t.SizeBytes AS bigint)) AS TotalBytes FROM dbo.Transactions t WHERE t.TxId IN (SELECT DISTINCT SpentByTxId FROM #pq WHERE IsSpent = 1);
