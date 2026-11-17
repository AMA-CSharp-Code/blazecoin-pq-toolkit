-- Post-quantum traffic since activation, split by kind: coinbase against payment, outputs per address, the shape of spending transactions, and where non-coinbase outputs were funded from. Schema: the project's block indexer.
-- A spend counts only if the spending transaction is itself inside the block range, so the result does not change
-- when the query is run later on a longer chain.
SET NOCOUNT ON; SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
SELECT o.Id, o.Amount, o.Address, CAST(CASE WHEN o.IsSpent = 1 AND sb.Height <= 4417513 THEN 1 ELSE 0 END AS bit) AS IsSpent, CASE WHEN o.IsSpent = 1 AND sb.Height <= 4417513 THEN o.SpentByTxId END AS SpentByTxId, t.TxId, t.IndexInBlock, b.Height
INTO #pq FROM dbo.Outputs o JOIN dbo.Transactions t ON t.Id = o.TransactionId JOIN dbo.Blocks b ON b.Id = t.BlockId LEFT JOIN dbo.Transactions st ON st.TxId = o.SpentByTxId LEFT JOIN dbo.Blocks sb ON sb.Id = st.BlockId
WHERE b.Height BETWEEN 4250000 AND 4417513 AND o.IsOrphaned = 0 AND o.ScriptType = 'pqkh';
SELECT CASE WHEN IndexInBlock = 0 THEN 'coinbase' ELSE 'payment' END AS Kind, COUNT(*) AS Outputs, SUM(CAST(IsSpent AS int)) AS Spent, COUNT(DISTINCT Address) AS Addresses, SUM(Amount)/100000000 AS BLZ FROM #pq GROUP BY CASE WHEN IndexInBlock = 0 THEN 'coinbase' ELSE 'payment' END;
SELECT Bucket, COUNT(*) AS Addresses, SUM(N) AS Outputs FROM (SELECT Address, COUNT(*) AS N, CASE WHEN COUNT(*)=1 THEN '1' WHEN COUNT(*)<=5 THEN '2-5' WHEN COUNT(*)<=100 THEN '6-100' ELSE '100+' END AS Bucket FROM #pq GROUP BY Address) x GROUP BY Bucket ORDER BY 1;
-- spending transactions: shape
SELECT Shape, COUNT(*) AS Txs, SUM(PqIn) AS PqInputs, AVG(CAST(Bytes AS float)) AS AvgBytes FROM (
  SELECT s.SpentByTxId, COUNT(*) AS PqIn, MAX(t.SizeBytes) AS Bytes, (SELECT COUNT(*) FROM dbo.Outputs o2 WHERE o2.TransactionId = t.Id) AS Outs,
   CASE WHEN COUNT(*) >= 10 AND (SELECT COUNT(*) FROM dbo.Outputs o2 WHERE o2.TransactionId = t.Id) <= 2 THEN 'consolidation (10+ in, 1-2 out)' WHEN (SELECT COUNT(*) FROM dbo.Outputs o2 WHERE o2.TransactionId = t.Id) >= 5 THEN 'batch payout (5+ out)' ELSE 'ordinary' END AS Shape
  FROM #pq s JOIN dbo.Transactions t ON t.TxId = s.SpentByTxId WHERE s.IsSpent = 1 GROUP BY s.SpentByTxId, t.Id) y GROUP BY Shape;
-- where do the coins come from for non-coinbase PQ outputs: is the funding tx spending PQ inputs (change / internal) or only classic inputs (migration in)
SELECT Src, COUNT(*) AS Outputs, COUNT(DISTINCT Address) AS Addresses FROM (
  SELECT p.Address, CASE WHEN EXISTS (SELECT 1 FROM #pq q WHERE q.SpentByTxId = p.TxId) THEN 'funded by a tx with PQ inputs' ELSE 'funded by classic inputs only' END AS Src FROM #pq p WHERE p.IndexInBlock <> 0) z GROUP BY Src;
