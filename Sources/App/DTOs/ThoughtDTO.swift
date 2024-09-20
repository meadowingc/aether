import Fluent
import Vapor

struct ThoughtDTO: Content, Validatable {
  var id: UUID?
  var text: String
  var antidote: String?
  var insertedAt: Date?

  func toModel() -> Thought {
    let model = Thought()

    model.id = self.id

    model.text = text

    if let antidote = self.antidote {
      if antidote.isEmpty {
        model.antidote = nil
      } else {
        model.antidote = antidote
      }
    }

    if let insertedAt = self.insertedAt {
      model.insertedAt = insertedAt
    } else {
      model.insertedAt = Date()
    }

    return model
  }

  static func validations(_ validations: inout Validations) {
    validations.add(
      "text", as: String.self, is: !.empty,
      customFailureDescription: "You need to provide something to get off your chest!")
  }
}
