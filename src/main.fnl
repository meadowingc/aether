(local fm (require :src.fool))

(fm.set-route :/static/* fm.serve-asset)

(local db (fm.make-storage :aether.sqlite3))
(db:pragma :journal_mode=WAL)
(db:pragma :synchronous=NORMAL)

(db:execute "
  CREATE TABLE IF NOT EXISTS migrations (
    name TEXT PRIMARY KEY
  )
")

(fn run-migration [name sql]
  (let [res (db:fetchOne "SELECT name FROM migrations WHERE name = ?" name)]
    (when (not= res db.NONE) (lua "return "))
    (db:execute sql)
    (db:execute "INSERT INTO migrations (name) VALUES (?)" name)))

(run-migration :1__create_thoughts_table "
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
")

(fm.set-template {1 :/views/ :tmpl :fmt})

(fm.set-template :header "
  <h1>
    {% function block.greet() %}
      Hi
    {% end %}

    {% block.greet() %}, {%& title %}!
  </h1>
")

(fm.set-template :hello "
  {% function block.layout_content() %}
     <h1>potato</h1>
     Hello, {%& name %}

     {% function block.greet() %}
     Hello overriden
     {% end %}

     {% render('header', {title=title}) %}!
  {% end %}

  {% render('layout') %}
")

(fm.set-route "/"
              (fn [_r]
                (fm.serve-content :home_fancy
                                  {:thoughts (db:fetchAll "select * from thoughts;")})))

(fm.set-route :/about (fn [_r] (fm.serve-content :about)))

(local thoughts-validator
       (fm.make-validator {1 {1 :text
                              :maxlen 600
                              :minlen 3
                              :msg "Invalid %s thought format"
                              :optional false}
                           2 {1 :antidote
                              :maxlen 600
                              :minlen 0
                              :msg "Invalid %s antidote format"
                              :optional true}
                           :otherwise (fn [validation-error]
                                        (fm.serve-content :home_fancy
                                                          {:thoughts (db:fetchAll "select * from thoughts;")
                                                           :validation_error validation-error}))}))

(fm.set-route (fm.GET [:/thoughts]) (fm.serve-redirect "/"))

(fm.set-route (fm.POST {1 :/thoughts :_ thoughts-validator})
              (fn [r]
                (fm.log-info (.. "Creating thought: " r.params.text))
                (var antidote r.params.antidote)
                (when (and (= (type antidote) :string) (= (length antidote) 0))
                  (set antidote nil))
                (db:execute "INSERT INTO thoughts (text, antidote) VALUES (?, ?)"
                            r.params.text antidote)
                (fm.serve-redirect "/")))

(fm.set-route "/hello/:name"
              (fn [r] (fm.serve-content :hello {:name r.params.name})))

(fm.set-route :/stream (fn []
                         (fm.stream-response 200 {:ContentType :text/html}
                                             "Hello, World!")
                         (fm.sleep 1)
                         (fm.stream-response "<p>More content</p>")
                         (fm.sleep 1)
                         "done for now"))

(fm.set-schedule "* * * * *"
                 (fn []
                   (let [quotes ["To be, or not to be: that is the question."
                                 "All the world's a stage, and all the men and women merely players."
                                 "Good night, good night! Parting is such sweet sorrow."
                                 "We know what we are, but know not what we may be."
                                 "Love all, trust a few, do wrong to none."
                                 "Give every man thy ear, but few thy voice."
                                 "The course of true love never did run smooth."
                                 "Better three hours too soon than a minute too late."
                                 "Nothing will come of nothing: dare mighty things."
                                 "Uneasy lies the head that wears a crown."]
                         q (. quotes (math.random (length quotes)))]
                     (fm.log-info (.. "It's one minute and all is well: " q)))))

(fm.set-schedule "*/30 * * * *"
                 (fn []
                   (db:execute "DELETE FROM thoughts WHERE inserted_at < datetime('now', '-24 hours');")))

(fm.run {:cookieOptions {:httponly true :samesite :Strict}
         :sessionOptions {:format :lua
                          :hash :SHA256
                          :name :aether_session
                          :secret true}})
