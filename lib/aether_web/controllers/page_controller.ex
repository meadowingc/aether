defmodule AetherWeb.PageController do
  use AetherWeb, :controller

  alias Aether.Space
  alias Aether.Space.Thoughts

  def home(conn, _params) do
    # The home page is often custom made,
    # so skip the default app layout.
    thoughts = Space.list_thoughts()

    # new thought changeset
    changeset = Space.change_thoughts(%Thoughts{})

    conn
    |> assign(:thoughts, thoughts)
    |> assign(:changeset, changeset)
    |> render(:home, layout: false)
  end

  def about(conn, _params) do
    render(conn, :about, layout: false)
  end
end
