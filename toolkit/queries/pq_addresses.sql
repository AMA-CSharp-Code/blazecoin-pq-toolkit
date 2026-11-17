-- Every post-quantum address since activation: outputs received, outputs spent, whether it took coinbases, whether it was funded from classic inputs. Schema: the project's block indexer.
-- A spend counts only if the spending transaction is itself inside the block range, so the result does not change
-- when the query is run later on a longer chain.
SET NOCOUNT ON; SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
SELECT o.Address, CAST(CASE WHEN o.IsSpent = 1 AND sb.Height <= 4417513 THEN 1 ELSE 0 END AS bit) AS IsSpent, CASE WHEN o.IsSpent = 1 AND sb.Height <= 4417513 THEN o.SpentByTxId END AS SpentByTxId, t.TxId, t.IndexInBlock
INTO #pq FROM dbo.Outputs o JOIN dbo.Transactions t ON t.Id = o.TransactionId JOIN dbo.Blocks b ON b.Id = t.BlockId LEFT JOIN dbo.Transactions st ON st.TxId = o.SpentByTxId LEFT JOIN dbo.Blocks sb ON sb.Id = st.BlockId
WHERE b.Height BETWEEN 4250000 AND 4417513 AND o.IsOrphaned = 0 AND o.ScriptType = 'pqkh';
SELECT DISTINCT SpentByTxId AS TxId INTO #pqspend FROM #pq WHERE IsSpent = 1;
SELECT p.Address, p.IsSpent, CASE WHEN p.IndexInBlock = 0 THEN 1 ELSE 0 END AS Cb, CASE WHEN p.IndexInBlock <> 0 AND s.TxId IS NULL THEN 1 ELSE 0 END AS Cf
INTO #f FROM #pq p LEFT JOIN #pqspend s ON s.TxId = p.TxId;
SELECT Address, COUNT(*) AS N, SUM(CAST(IsSpent AS int)) AS Spent, MAX(Cb) AS Cb, MAX(Cf) AS ClassicFunded FROM #f GROUP BY Address;
