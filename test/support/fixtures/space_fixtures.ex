defmodule Aether.SpaceFixtures do
  @moduledoc """
  This module defines test helpers for creating
  entities via the `Aether.Space` context.
  """

  @doc """
  Generate a thoughts.
  """
  def thoughts_fixture(attrs \\ %{}) do
    {:ok, thoughts} =
      attrs
      |> Enum.into(%{
        antidote: "some antidote",
        expires_on: ~N[2024-06-16 18:37:00],
        text: "some text"
      })
      |> Aether.Space.create_thoughts()

    thoughts
  end
end
