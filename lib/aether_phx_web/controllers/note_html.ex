defmodule AetherPhxWeb.NoteHTML do
  @moduledoc """
  HEEx templates for public and admin note views.
  """
  use AetherPhxWeb, :html

  embed_templates "note_html/*"

  attr :note, :map, required: true

  def render_note(assigns) do
    ~H"""
    <article class="note-card"
             data-note-id={@note.id}
             data-created-by={@note.created_device_id || ""}
             style={"opacity: #{Float.to_string(@note.opacity || 1.0)};"}>
      <div class="note-text"><%= Phoenix.HTML.html_escape(@note.text) %></div>
      <footer class="note-meta">
        <span class="author"><%= @note.author || "anonymous" %></span>
        <span class="dot">•</span>
        <span class="expires">fades in <%= @note.expires_in %></span>
        <span class="dot">•</span>
        <span class="views" data-views><%= @note.views %><%= if @note.views == 1, do: " witness", else: " witnessed" %></span>
        <span class="del-wrap" style="display:none">
          <span class="dot">•</span>
          <a href="#" class="note-del" title="Delete this note" aria-label="Delete">del</a>
        </span>
        <span class="dot">•</span>
        <button type="button" class="flag-btn" aria-label="Flag this note as inappropriate" title="Flag this note as inappropriate">⚑</button>
      </footer>
    </article>
    """
  end
end
