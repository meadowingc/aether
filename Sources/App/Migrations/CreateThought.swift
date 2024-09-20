import Fluent

struct CreateThought: AsyncMigration {
  func prepare(on database: Database) async throws {
    try await database.schema("thoughts")
      .id()
      .field("text", .string, .required)
      .field("antidote", .string)
      .field("inserted_at", .datetime)
      .create()
  }

  func revert(on database: Database) async throws {
    try await database.schema("thoughts").delete()
  }
}
