import Fluent

import struct Foundation.UUID

/// Property wrappers interact poorly with `Sendable` checking, causing a warning for the `@ID` property
/// It is recommended you write your model with sendability checking on and then suppress the warning
/// afterwards with `@unchecked Sendable`.
final class Thought: Model, @unchecked Sendable {
  static let schema = "thoughts"

  @ID(key: .id)
  var id: UUID?

  @Field(key: "text")
  var text: String

  @Field(key: "antidote")
  var antidote: String?

  @Timestamp(key: "inserted_at", on: .create)
  var insertedAt: Date?

  init() {}

  init(id: UUID? = nil, text: String, antidote: String, insertedAt: Date) {
    self.id = id
    self.text = text
    self.antidote = antidote
    self.insertedAt = insertedAt
  }

  func toDTO() -> ThoughtDTO {
    .init(
      id: self.id,
      text: self.text,
      antidote: self.antidote,
      insertedAt: self.insertedAt
    )
  }
}
