defmodule AetherWeb.ThoughtsController do
  use AetherWeb, :controller

  alias Aether.Space
  alias Aether.Space.Thoughts

  def index(conn, _params) do
    thoughts = Space.list_thoughts()
    render(conn, :index, thoughts_collection: thoughts)
  end

  def new(conn, _params) do
    changeset = Space.change_thoughts(%Thoughts{})
    render(conn, :new, changeset: changeset)
  end

  def create(conn, %{"thoughts" => thoughts_params}) do
    case Space.create_thoughts(thoughts_params) do
      {:ok, _thoughts} ->
        conn
        |> put_flash(:info, "Thoughts created successfully.")
        |> redirect(to: ~p"/")

      {:error, %Ecto.Changeset{} = changeset} ->
        render(conn, :new, changeset: changeset)
    end
  end

  def show(conn, %{"id" => id}) do
    thoughts = Space.get_thoughts!(id)
    render(conn, :show, thoughts: thoughts)
  end

  def edit(conn, %{"id" => id}) do
    thoughts = Space.get_thoughts!(id)
    changeset = Space.change_thoughts(thoughts)
    render(conn, :edit, thoughts: thoughts, changeset: changeset)
  end

  def update(conn, %{"id" => id, "thoughts" => thoughts_params}) do
    thoughts = Space.get_thoughts!(id)

    case Space.update_thoughts(thoughts, thoughts_params) do
      {:ok, thoughts} ->
        conn
        |> put_flash(:info, "Thoughts updated successfully.")
        |> redirect(to: ~p"/thoughts/#{thoughts}")

      {:error, %Ecto.Changeset{} = changeset} ->
        render(conn, :edit, thoughts: thoughts, changeset: changeset)
    end
  end

  def delete(conn, %{"id" => id}) do
    thoughts = Space.get_thoughts!(id)
    {:ok, _thoughts} = Space.delete_thoughts(thoughts)

    conn
    |> put_flash(:info, "Thoughts deleted successfully.")
    |> redirect(to: ~p"/thoughts")
  end
end
