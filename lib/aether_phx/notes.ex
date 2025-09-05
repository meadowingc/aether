defmodule AetherPhx.Notes do
  @moduledoc """
  Context providing operations over short-lived Notes plus witness & flag tracking.

  Parity goals with Django version:
  - Anonymous note creation with optional author (defaults to "anonymous")
  - List notes from last 48h (max 200) sorted by pub_date desc
  - Unique witness per (note, device) increments denormalized views counter
  - Toggle flag per (note, device) increments/decrements flags counter
  - Delete allowed only if created_device_id matches
  """

  import Ecto.Query
  alias AetherPhx.Repo
  alias AetherPhx.Notes.{Note, NoteView, NoteFlag}

  @recent_cutoff_seconds 48 * 3600
  @max_list 200

  # Public API

  @doc """
  Create a new note.

  attrs expects at least "text".
  Adds current UTC timestamp as pub_date.
  """
  def create_note(attrs) when is_map(attrs) do
    now = DateTime.utc_now() |> DateTime.truncate(:second)

    %Note{}
    |> Note.changeset(Map.put(attrs, "pub_date", now))
    |> Repo.insert()
  end

  @doc """
  List notes from last 48h (limit #{@max_list}). Adds virtual display metadata.

  Returns a list of %Note{} with :opacity and :expires_in populated.
  """
  def list_recent_notes() do
    cutoff = DateTime.utc_now() |> DateTime.add(-@recent_cutoff_seconds, :second)

    Note
    |> where([n], n.pub_date >= ^cutoff)
    |> order_by([n], desc: n.pub_date)
    |> limit(^@max_list)
    |> Repo.all()
    |> attach_display_meta()
  end

  @doc """
  Record a witness (device seeing a note). Returns:

    {:ok, :new, views} when a new witness increments views
    {:ok, :already, views} when witness already existed
    {:error, :not_found} if note missing
    {:error, :invalid} if params invalid
  """
  def record_witness(note_id, device_id)
      when is_integer(note_id) and is_binary(device_id) and byte_size(device_id) > 0 do
    case Repo.get(Note, note_id) do
      nil ->
        {:error, :not_found}

      note ->
        params = %{"note_id" => note.id, "device_id" => device_id}

        case %NoteView{} |> NoteView.changeset(params) |> Repo.insert() do
          {:ok, _} ->
            increment_counter(note, :views)
            {:ok, :new, fetch_counter(note_id, :views)}

          {:error, changeset} ->
            if constraint_error?(changeset) do
              {:ok, :already, fetch_counter(note_id, :views)}
            else
              {:error, :invalid}
            end
        end
    end
  end

  def record_witness(_, _), do: {:error, :invalid}

  @doc """
  Toggle a flag. Returns:

    {:ok, :flagged, flags}
    {:ok, :unflagged, flags}
    {:error, :not_found}
    {:error, :invalid}
  """
  def toggle_flag(note_id, device_id)
      when is_integer(note_id) and is_binary(device_id) and byte_size(device_id) > 0 do
    case Repo.get(Note, note_id) do
      nil ->
        {:error, :not_found}

      note ->
        params = %{"note_id" => note.id, "device_id" => device_id}

        case %NoteFlag{} |> NoteFlag.changeset(params) |> Repo.insert() do
          {:ok, _} ->
            increment_counter(note, :flags)
            {:ok, :flagged, fetch_counter(note_id, :flags)}

          {:error, changeset} ->
            if constraint_error?(changeset) do
              # Already flagged - remove and decrement
              from(f in NoteFlag,
                where: f.note_id == ^note.id and f.device_id == ^device_id
              )
              |> Repo.delete_all()

              decrement_counter(note, :flags)
              {:ok, :unflagged, fetch_counter(note_id, :flags)}
            else
              {:error, :invalid}
            end
        end
    end
  end

  def toggle_flag(_, _), do: {:error, :invalid}

  @doc """
  Delete a note if created_device_id matches.

  Returns :ok | {:error, :forbidden} | {:error, :not_found}
  """
  def delete_note(note_id, device_id)
      when is_integer(note_id) and is_binary(device_id) and byte_size(device_id) > 0 do
    case Repo.get(Note, note_id) do
      nil ->
        {:error, :not_found}

      %Note{created_device_id: nil} ->
        {:error, :forbidden}

      %Note{created_device_id: creator} = note ->
        if creator == device_id do
          Repo.delete(note)
          :ok
        else
          {:error, :forbidden}
        end
    end
  end

  def delete_note(_, _), do: {:error, :invalid}

  # Internal helpers

  defp attach_display_meta(notes) do
    now = DateTime.utc_now()

    Enum.map(notes, fn n ->
      age_seconds = DateTime.diff(now, n.pub_date, :second)
      max_age = @recent_cutoff_seconds
      ratio = age_seconds / max_age |> clamp(0.0, 1.0)
      opacity = Float.round(1.0 - 0.6 * ratio, 3)
      remaining = max(max_age - age_seconds, 0)
      hours = div(remaining, 3600)
      minutes = div(rem(remaining, 3600), 60)

      %{n | opacity: opacity, expires_in: "#{hours}h #{minutes}m"}
    end)
  end

  defp clamp(v, min, _max) when v < min, do: min
  defp clamp(v, _min, max) when v > max, do: max
  defp clamp(v, _min, _max), do: v

  defp constraint_error?(%Ecto.Changeset{errors: errors}) do
    Enum.any?(errors, fn {_field, {_, meta}} -> match?(%{constraint: :unique}, meta) end)
  end
  defp constraint_error?(_), do: false

  defp increment_counter(%Note{id: id}, field) when field in [:views, :flags] do
    from(n in Note, where: n.id == ^id)
    |> Repo.update_all(inc: [{field, 1}])
    :ok
  end

  defp decrement_counter(%Note{id: id}, field) when field in [:views, :flags] do
    from(n in Note, where: n.id == ^id and field(n, ^field) > 0)
    |> Repo.update_all(inc: [{field, -1}])
    :ok
  end

  defp fetch_counter(id, field) do
    Repo.one(from n in Note, where: n.id == ^id, select: field(n, ^field)) || 0
  end
end
