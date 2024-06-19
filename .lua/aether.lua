local fm = require "fullmoon"

fm.setRoute("/static/*", fm.serveAsset)

local db = fm.makeStorage("aether.sqlite3")

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
    return fm.serveContent("home")
end)

fm.setRoute("/about", function(r)
    return fm.serveContent("about")
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
