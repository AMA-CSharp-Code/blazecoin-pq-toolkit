-- The three coin states of the Blazecoin Quantum Bridge, counted over the whole unspent output set: exposed, hash-safe, post-quantum. Schema: the project's block indexer.
-- A key counts as exposed when its address has been spent from at least once (the spend reveals the key) or when it is paid by a
-- pay-to-public-key output (the key is in the output). Keys revealed off the chain (a signed message, a shared extended public
-- key, a fork of the chain) cannot be seen here, so the exposed share is a lower bound and the hash-safe share an upper bound.
-- Run against an index at the height you want the snapshot for; the last statement reports that height.
SET NOCOUNT ON; SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
SELECT DISTINCT Address INTO #exposed FROM dbo.Outputs WHERE IsOrphaned = 0 AND ScriptType <> 'pqkh' AND (IsSpent = 1 OR ScriptType = 'pubkey');
CREATE UNIQUE CLUSTERED INDEX ix ON #exposed(Address);
SELECT State, COUNT(*) AS UnspentOutputs, COUNT(DISTINCT Address) AS Addresses,
       CAST(SUM(CAST(Amount AS decimal(38,0)))/100000000 AS decimal(20,2)) AS Coins
FROM (SELECT o.Address, o.Amount,
        CASE WHEN o.ScriptType = 'pqkh' THEN '3 post-quantum'
             WHEN o.ScriptType = 'pubkey' THEN '1 exposed (pay-to-public-key output)'
             WHEN e.Address IS NOT NULL THEN '1 exposed (key revealed by a spend or by a pay-to-public-key output)'
             WHEN o.ScriptType IN ('pubkeyhash','scripthash') THEN '2 hash-safe'
             ELSE '4 other' END AS State
      FROM dbo.Outputs o LEFT JOIN #exposed e ON e.Address = o.Address
      WHERE o.IsSpent = 0 AND o.IsOrphaned = 0) x
GROUP BY State ORDER BY State;
SELECT MAX(Height) AS AtHeight, MAX([Timestamp]) AS AtTime FROM dbo.Blocks WHERE IsOrphaned = 0;
