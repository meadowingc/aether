import Fluent
import Vapor

struct TodoController: RouteCollection {
  func boot(routes: RoutesBuilder) throws {
    let todos = routes.grouped("todos")

    todos.get(use: self.index)
    todos.post(use: self.create)
    todos.group(":todoID") { todo in
      todo.delete(use: self.delete)
    }
  }

  @Sendable
  func index(req: Request) async throws -> View {
    if !req.application.environment.isRelease {
      let titles = [
        "Eat bananas", "Read a book", "Go for a walk", "Write some code", "Cook dinner",
      ]
      let randomTitle = titles.randomElement()!

      try await Todo(title: randomTitle).create(on: req.db)
    }

    struct Context: Encodable {
      let title: String
      let todos: [Todo]
    }

    let allTodos: [Todo] = try await Todo.query(on: req.db).all()
    let context = Context(title: "All todos!", todos: allTodos)
    return try await req.view.render("todos", context)
  }

  @Sendable
  func create(req: Request) async throws -> Response {
    let todo = try req.content.decode(Todo.self)

    try await todo.save(on: req.db)
    return req.redirect(to: "/todos")
  }

  @Sendable
  func delete(req: Request) async throws -> HTTPStatus {
    guard let todo = try await Todo.find(req.parameters.get("todoID"), on: req.db) else {
      throw Abort(.notFound)
    }

    try await todo.delete(on: req.db)
    return .noContent
  }
}
