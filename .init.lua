-- special script called by main redbean process at startup
ProgramBrand("aether")

-- sqlite3 = require "lsqlite3"

-- function OnWorkerStart()
--     db = sqlite3.open("db.sqlite3")
--     db:busy_timeout(1000)
--     db:exec [[PRAGMA journal_mode=WAL]]
--     db:exec [[PRAGMA synchronous=NORMAL]]
--     db:exec [[SELECT x FROM warmup WHERE x = 1]]
-- end

require "aether"