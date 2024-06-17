defmodule Aether.Space do
  @moduledoc """
  The Space context.
  """

  import Ecto.Query, warn: false
  alias Aether.Repo

  alias Aether.Space.Thoughts
  alias Ecto.Changeset

  @doc """
  Returns the list of thoughts.

  ## Examples

      iex> list_thoughts()
      [%Thoughts{}, ...]

  """
  def list_thoughts do
    Repo.all(Thoughts)
  end

  @doc """
  Gets a single thoughts.

  Raises `Ecto.NoResultsError` if the Thoughts does not exist.

  ## Examples

      iex> get_thoughts!(123)
      %Thoughts{}

      iex> get_thoughts!(456)
      ** (Ecto.NoResultsError)

  """
  def get_thoughts!(id), do: Repo.get!(Thoughts, id)

  @doc """
  Creates a thoughts.

  ## Examples

      iex> create_thoughts(%{field: value})
      {:ok, %Thoughts{}}

      iex> create_thoughts(%{field: bad_value})
      {:error, %Ecto.Changeset{}}

  """
  def create_thoughts(attrs \\ %{}) do
    %Thoughts{}
    |> Thoughts.changeset(attrs)
    # |> dynamic_default(:expires_on, fn ->
    #   NaiveDateTime.utc_now()
    #   |> NaiveDateTime.add(1, :day)
    #   |> NaiveDateTime.truncate(:second)
    # end)
    |> Repo.insert()
  end

  # defp dynamic_default(changeset, key, value_fun) do
  #   case Changeset.get_field(changeset, key) do
  #     nil -> Changeset.put_change(changeset, key, value_fun.())
  #     _ -> changeset
  #   end
  # end

  @doc """
  Updates a thoughts.

  ## Examples

      iex> update_thoughts(thoughts, %{field: new_value})
      {:ok, %Thoughts{}}

      iex> update_thoughts(thoughts, %{field: bad_value})
      {:error, %Ecto.Changeset{}}

  """
  def update_thoughts(%Thoughts{} = thoughts, attrs) do
    thoughts
    |> Thoughts.changeset(attrs)
    |> Repo.update()
  end

  @doc """
  Deletes a thoughts.

  ## Examples

      iex> delete_thoughts(thoughts)
      {:ok, %Thoughts{}}

      iex> delete_thoughts(thoughts)
      {:error, %Ecto.Changeset{}}

  """
  def delete_thoughts(%Thoughts{} = thoughts) do
    Repo.delete(thoughts)
  end

  @doc """
  Returns an `%Ecto.Changeset{}` for tracking thoughts changes.

  ## Examples

      iex> change_thoughts(thoughts)
      %Ecto.Changeset{data: %Thoughts{}}

  """
  def change_thoughts(%Thoughts{} = thoughts, attrs \\ %{}) do
    Thoughts.changeset(thoughts, attrs)
  end
end
