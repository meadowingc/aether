import Fluent
import Vapor

func routes(_ app: Application) throws {
  app.get { req async throws -> View in
    struct Context: Encodable {
      let title: String
      let thoughts: [Thought]
      let validationError: String?
    }

    let allThoughts: [Thought] = try await Thought.query(on: req.db).all()
    let context = Context(title: "All todos!", thoughts: allThoughts, validationError: nil)
    return try await req.view.render("index", context)
  }

  app.post("thoughts") { req async throws -> Response in
    try ThoughtDTO.validate(content: req)
    let thought = try req.content.decode(ThoughtDTO.self).toModel()

    try await thought.save(on: req.db)
    return req.redirect(to: "/")
  }

  app.get("about") { req async throws in
    try await req.view.render("about", ["title": "About"])
  }

  app.get("hello") { req async -> String in
    "Hello, world!"
  }

  try app.register(collection: TodoController())
}
