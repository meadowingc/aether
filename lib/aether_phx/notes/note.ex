defmodule AetherPhx.Notes.Note do
  @moduledoc """
  Note entity: short-lived (48h) anonymous message with denormalized counters.
  """
  use Ecto.Schema
  import Ecto.Changeset

  @max_length 2000

  schema "notes" do
    field :text, :string
    field :pub_date, :utc_datetime
    field :author, :string
    field :views, :integer, default: 0
    field :flags, :integer, default: 0
    field :created_device_id, :string

    # Virtual display metadata (computed at query/load time)
    field :opacity, :float, virtual: true
    field :expires_in, :string, virtual: true

    timestamps()
  end

  def changeset(note, attrs) do
    attrs =
      attrs
      |> normalize_text()
      |> normalize_author()
      |> cap_text()

    note
    |> cast(attrs, [:text, :pub_date, :author, :views, :flags, :created_device_id])
    |> validate_required([:text, :pub_date])
    |> validate_length(:text, max: @max_length)
    |> validate_length(:author, max: 100)
  end

  defp normalize_text(%{"text" => t} = attrs) when is_binary(t) do
    Map.put(attrs, "text", String.trim(t))
  end
  defp normalize_text(%{text: t} = attrs) when is_binary(t) do
    Map.put(attrs, :text, String.trim(t))
  end
  defp normalize_text(attrs), do: attrs

  defp cap_text(%{"text" => t} = attrs) when is_binary(t) do
    Map.put(attrs, "text", String.slice(t, 0, @max_length))
  end
  defp cap_text(%{text: t} = attrs) when is_binary(t) do
    Map.put(attrs, :text, String.slice(t, 0, @max_length))
  end
  defp cap_text(attrs), do: attrs

  defp normalize_author(%{"author" => a} = attrs) do
    a = a |> String.trim() |> blank_to_anonymous()
    Map.put(attrs, "author", a)
  end
  defp normalize_author(%{author: a} = attrs) do
    a = a |> String.trim() |> blank_to_anonymous()
    Map.put(attrs, :author, a)
  end
  defp normalize_author(attrs), do: Map.put(attrs, "author", "anonymous")

  defp blank_to_anonymous(""), do: "anonymous"
  defp blank_to_anonymous(nil), do: "anonymous"
  defp blank_to_anonymous(v), do: v
end
