defmodule Aether.Space.Thoughts do
  use Ecto.Schema
  import Ecto.Changeset

  schema "thoughts" do
    field :text, :string
    field :antidote, :string

    timestamps(type: :utc_datetime)
  end

  @doc false
  def changeset(thought, attrs) do
    thought
    |> cast(attrs, [:text, :antidote])
    |> validate_required([:text])
    |> validate_length(:text, min: 3, max: 700)
    |> validate_length(:antidote, min: 0, max: 700)
  end
end
