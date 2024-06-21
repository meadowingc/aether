;; this is just a fennel wrapper for the real fullmoon.
;; I like to overcomplicate myself

(local fm (require :fullmoon))

{:GET (fn [...] (fm.GET ...))
 :POST (fn [...] (fm.POST ...))
 :log-info (fn [...] (fm.logInfo ...))
 :make-storage (fn [...] (fm.makeStorage ...))
 :make-validator (fn [...] (fm.makeValidator ...))
 :run (fn [...] (fm.run ...))
 :serve-asset (fn [...] (fm.serveAsset ...))
 :serve-content (fn [...] (fm.serveContent ...))
 :serve-redirect (fn [...] (fm.serveRedirect ...))
 :set-route (fn [...] (fm.setRoute ...))
 :set-schedule (fn [...] (fm.setSchedule ...))
 :set-template (fn [...] (fm.setTemplate ...))
 :sleep (fn [...] (fm.sleep ...))
 :stream-response (fn [...] (fm.streamResponse ...))}
