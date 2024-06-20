local fm = require "fullmoon"

fm.setRoute("/static/*", fm.serveAsset)

local db = fm.makeStorage("aether.sqlite3")
db:pragma("journal_mode=WAL")
db:pragma("synchronous=NORMAL")

db:execute [[
  CREATE TABLE IF NOT EXISTS migrations (
    name TEXT PRIMARY KEY
  )
]]

local function run_migration(name, sql)
    local res = db:fetchOne("SELECT name FROM migrations WHERE name = ?", name)
    if res ~= db.NONE then
        -- The migration has already been run, so return early
        return
    end

    db:execute(sql)
    db:execute("INSERT INTO migrations (name) VALUES (?)", name)
end

-- run migrations
run_migration("1__create_thoughts_table", [[
  CREATE TABLE IF NOT EXISTS thoughts (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    antidote TEXT,
    inserted_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  -- add some initial thoughts
  INSERT INTO thoughts (text, antidote) VALUES
    ('Thought 1', 'Antidote 1'),
    ('Thought 2', 'Antidote 2'),
    ('Thought 3', 'Antidote 3');
]])

fm.setTemplate({
    "/views/",
    tmpl = "fmt"
})

fm.setTemplate("header", [[
  <h1>
    {% function block.greet() %}
      Hi
    {% end %}

    {% block.greet() %}, {%& title %}!
  </h1>
]])

fm.setTemplate("hello", [[
    {% function block.layout_content() %}
        <h1>potato</h1>
        Hello, {%& name %}

        {% function block.greet() %}
        Hello overriden
        {% end %}

        {% render('header', {title=title}) %}!
    {% end %}

    {% render('layout') %}
]])

fm.setRoute("/", function(r)
    return fm.serveContent("home_fancy", {
        thoughts = db:fetchAll("select * from thoughts;"),
    })
end)

fm.setRoute("/about", function(r)
    return fm.serveContent("about")
end)


local thoughtsValidator = fm.makeValidator {
    { "text",     optional = false, minlen = 3, maxlen = 600, msg = "Invalid %s thought format" },
    { "antidote", optional = true,  minlen = 0, maxlen = 600, msg = "Invalid %s antidote format" },
    otherwise = function(validation_error)
        return fm.serveContent("home_fancy", {
            thoughts = db:fetchAll("select * from thoughts;"),
            validation_error = validation_error,
        })
    end,
}
fm.setRoute(fm.GET { "/thoughts" }, fm.serveRedirect('/'))
fm.setRoute(fm.POST { "/thoughts", _ = thoughtsValidator }, function(r)
    fm.logInfo("Creating thought: " .. r.params.text)

    local antidote = r.params.antidote
    if type(antidote) == "string" and #antidote == 0 then
        antidote = nil
    end
    db:execute("INSERT INTO thoughts (text, antidote) VALUES (?, ?)", r.params.text, antidote)
    -- r.params.name
    return fm.serveRedirect("/")
end)

fm.setRoute("/hello/:name", function(r)
    return fm.serveContent("hello", {
        name = r.params.name
    })
end)

-- this route serves a stream of messages
fm.setRoute("/stream", function()
    fm.streamResponse(200, {
        ContentType = "text/html"
    }, "Hello, World!")
    fm.sleep(1)
    fm.streamResponse("<p>More content</p>")
    fm.sleep(1)
    return "done for now"
end)

-- https://github.com/pkulchenko/fullmoon/tree/master?tab=readme-ov-file#schedules
--------------- ┌─────────── minute (0-59)
--------------- │ ┌───────── hour (0-23)
--------------- │ │ ┌─────── day of the month (1-31)
--------------- │ │ │ ┌───── month (1-12 or Jan-Dec)
--------------- │ │ │ │ ┌─── day of the week (0-6 or Sun-Mon)
--------------- │ │ │ │ │ --
--------------- │ │ │ │ │ --
fm.setSchedule("* * * * *", function()
    fm.logInfo("every minute --- hoho")
end)

fm.run({
    cookieOptions = {
        httponly = true,
        samesite = "Strict"
    },
    sessionOptions = {
        name = "aether_session",
        hash = "SHA256",
        secret = true,
        format = "lua"
    }
})
