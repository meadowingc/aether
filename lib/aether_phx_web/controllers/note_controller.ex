defmodule AetherPhxWeb.NoteController do
  @moduledoc """
  Public + admin endpoints for notes (parity with Django version).
  """
  use AetherPhxWeb, :controller

  alias AetherPhx.Notes

  # ---------- Public Pages ----------

  def index(conn, _params) do
    notes = Notes.list_recent_notes()
    render(conn, :index, notes: notes)
  end

  def about(conn, _params) do
    render(conn, :about)
  end

  def create(conn, params) do
    text = (params["text"] || "") |> String.trim()
    author = (params["author"] || "") |> String.trim()
    device_id = (params["device_id"] || "") |> String.trim()

    if text == "" do
      redirect(conn, to: ~p"/")
    else
      _ = Notes.create_note(%{
        "text" => text,
        "author" => author,
        "created_device_id" => (device_id == "" && nil) || device_id
      })

      redirect(conn, to: ~p"/")
    end
  end

  # POST /witness
  def witness(conn, %{"note_id" => note_id_raw, "device_id" => device_id}) do
    with {note_id, ""} <- Integer.parse(to_string(note_id_raw)),
         true <- is_binary(device_id) and device_id != "" do
      case Notes.record_witness(note_id, device_id) do
        {:ok, :new, views} ->
          json(conn, %{ok: true, views: views})

        {:ok, :already, views} ->
          json(conn, %{ok: true, already: true, views: views})

        {:error, :not_found} ->
          conn |> put_status(:not_found) |> json(%{ok: false, error: "not_found"})

        _ ->
          conn |> put_status(:bad_request) |> json(%{ok: false, error: "invalid_payload"})
      end
    else
      _ ->
        conn |> put_status(:bad_request) |> json(%{ok: false, error: "invalid_payload"})
    end
  end

  # POST /flag-note
  def flag(conn, %{"note_id" => note_id_raw, "device_id" => device_id}) do
    with {note_id, ""} <- Integer.parse(to_string(note_id_raw)),
         true <- is_binary(device_id) and device_id != "" do
      case Notes.toggle_flag(note_id, device_id) do
        {:ok, :flagged, flags} ->
          json(conn, %{ok: true, flags: flags, flagged: true})

        {:ok, :unflagged, flags} ->
          json(conn, %{ok: true, flags: flags, flagged: false})

        {:error, :not_found} ->
          conn |> put_status(:not_found) |> json(%{ok: false, error: "not_found"})

        _ ->
          conn |> put_status(:bad_request) |> json(%{ok: false, error: "invalid_payload"})
      end
    else
      _ ->
        conn |> put_status(:bad_request) |> json(%{ok: false, error: "invalid_payload"})
    end
  end

  # POST /delete-note
  def delete(conn, %{"note_id" => note_id_raw, "device_id" => device_id}) do
    with {note_id, ""} <- Integer.parse(to_string(note_id_raw)),
         true <- is_binary(device_id) and device_id != "" do
      case Notes.delete_note(note_id, device_id) do
        :ok ->
          json(conn, %{ok: true})

        {:error, :forbidden} ->
          conn |> put_status(:forbidden) |> json(%{ok: false, error: "forbidden"})

        {:error, :not_found} ->
          conn |> put_status(:not_found) |> json(%{ok: false, error: "not_found"})

        _ ->
          conn |> put_status(:bad_request) |> json(%{ok: false, error: "invalid_payload"})
      end
    else
      _ ->
        conn |> put_status(:bad_request) |> json(%{ok: false, error: "invalid_payload"})
    end
  end
end
