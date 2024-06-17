defmodule Aether.SpaceTest do
  use Aether.DataCase

  alias Aether.Space

  describe "thoughts" do
    alias Aether.Space.Thoughts

    import Aether.SpaceFixtures

    @invalid_attrs %{text: nil, antidote: nil, expires_on: nil}

    test "list_thoughts/0 returns all thoughts" do
      thoughts = thoughts_fixture()
      assert Space.list_thoughts() == [thoughts]
    end

    test "get_thoughts!/1 returns the thoughts with given id" do
      thoughts = thoughts_fixture()
      assert Space.get_thoughts!(thoughts.id) == thoughts
    end

    test "create_thoughts/1 with valid data creates a thoughts" do
      valid_attrs = %{text: "some text", antidote: "some antidote", expires_on: ~N[2024-06-16 18:37:00]}

      assert {:ok, %Thoughts{} = thoughts} = Space.create_thoughts(valid_attrs)
      assert thoughts.text == "some text"
      assert thoughts.antidote == "some antidote"
      assert thoughts.expires_on == ~N[2024-06-16 18:37:00]
    end

    test "create_thoughts/1 with invalid data returns error changeset" do
      assert {:error, %Ecto.Changeset{}} = Space.create_thoughts(@invalid_attrs)
    end

    test "update_thoughts/2 with valid data updates the thoughts" do
      thoughts = thoughts_fixture()
      update_attrs = %{text: "some updated text", antidote: "some updated antidote", expires_on: ~N[2024-06-17 18:37:00]}

      assert {:ok, %Thoughts{} = thoughts} = Space.update_thoughts(thoughts, update_attrs)
      assert thoughts.text == "some updated text"
      assert thoughts.antidote == "some updated antidote"
      assert thoughts.expires_on == ~N[2024-06-17 18:37:00]
    end

    test "update_thoughts/2 with invalid data returns error changeset" do
      thoughts = thoughts_fixture()
      assert {:error, %Ecto.Changeset{}} = Space.update_thoughts(thoughts, @invalid_attrs)
      assert thoughts == Space.get_thoughts!(thoughts.id)
    end

    test "delete_thoughts/1 deletes the thoughts" do
      thoughts = thoughts_fixture()
      assert {:ok, %Thoughts{}} = Space.delete_thoughts(thoughts)
      assert_raise Ecto.NoResultsError, fn -> Space.get_thoughts!(thoughts.id) end
    end

    test "change_thoughts/1 returns a thoughts changeset" do
      thoughts = thoughts_fixture()
      assert %Ecto.Changeset{} = Space.change_thoughts(thoughts)
    end
  end
end
