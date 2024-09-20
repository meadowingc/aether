import Fluent
import FluentSQLiteDriver
import Leaf
import NIOSSL
import Vapor

// configures your application
public func configure(_ app: Application) async throws {
  app.http.server.configuration.port = 7483

  //   let corsConfiguration = CORSMiddleware.Configuration(
  //     allowedOrigin: .all,
  //     allowedMethods: [.GET, .POST, .PUT, .OPTIONS, .DELETE, .PATCH],
  //     allowedHeaders: [
  //       .accept, .authorization, .contentType, .origin, .xRequestedWith, .userAgent,
  //       .accessControlAllowOrigin,
  //     ]
  //   )
  //   let cors = CORSMiddleware(configuration: corsConfiguration)
  //   // cors middleware should come before default error middleware using `at: .beginning`
  //   app.middleware.use(cors, at: .beginning)

  // uncomment to serve files from /Public folder
  app.middleware.use(FileMiddleware(publicDirectory: app.directory.publicDirectory))

  app.databases.use(DatabaseConfigurationFactory.sqlite(.file("db.sqlite")), as: .sqlite)

  app.migrations.add(CreateTodo())
  app.migrations.add(CreateThought())

  try await app.autoMigrate()

  app.views.use(.leaf)
  app.leaf.tags["now"] = NowTag()

  // register routes
  try routes(app)
}
