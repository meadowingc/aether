defmodule AetherPhx.Notes.NoteFlag do
  @moduledoc """
  Records that a given device has flagged a note (toggle-able).
  Uniqueness on (note_id, device_id) enforces one flag per device per note.
  """
  use Ecto.Schema
  import Ecto.Changeset

  schema "note_flags" do
    belongs_to :note, AetherPhx.Notes.Note
    field :device_id, :string
    timestamps(updated_at: false)
  end

  def changeset(flag, attrs) do
    flag
    |> cast(attrs, [:note_id, :device_id])
    |> validate_required([:note_id, :device_id])
    |> validate_length(:device_id, max: 64)
    |> unique_constraint([:note_id, :device_id], name: :note_flags_note_id_device_id_index)
  end
end
