defmodule AetherWeb.ThoughtsHTML do
  use AetherWeb, :html

  embed_templates "thoughts_html/*"

  @doc """
  Renders a thoughts form.
  """
  attr :changeset, Ecto.Changeset, required: true
  attr :action, :string, required: true

  def thoughts_form(assigns)
end
