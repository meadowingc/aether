defmodule AetherPhx.Notes.NoteView do
  @moduledoc """
  Records that a given device (client UUID) has witnessed a note.
  Enforces uniqueness on (note_id, device_id) to match Django uniqueness constraint.
  """
  use Ecto.Schema
  import Ecto.Changeset

  schema "note_views" do
    belongs_to :note, AetherPhx.Notes.Note
    field :device_id, :string
    timestamps(updated_at: false)
  end

  def changeset(view, attrs) do
    view
    |> cast(attrs, [:note_id, :device_id])
    |> validate_required([:note_id, :device_id])
    |> validate_length(:device_id, max: 64)
    |> unique_constraint([:note_id, :device_id], name: :note_views_note_id_device_id_index)
    # Name above must match index name; if Ecto generated a different one we can
    # adjust after inspecting sqlite. Leaving explicit so caller handles constraint error.
  end
end
