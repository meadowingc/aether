defmodule AetherWeb.ThoughtsControllerTest do
  use AetherWeb.ConnCase

  import Aether.SpaceFixtures

  @create_attrs %{text: "some text", antidote: "some antidote", expires_on: ~N[2024-06-16 18:37:00]}
  @update_attrs %{text: "some updated text", antidote: "some updated antidote", expires_on: ~N[2024-06-17 18:37:00]}
  @invalid_attrs %{text: nil, antidote: nil, expires_on: nil}

  describe "index" do
    test "lists all thoughts", %{conn: conn} do
      conn = get(conn, ~p"/thoughts")
      assert html_response(conn, 200) =~ "Listing Thoughts"
    end
  end

  describe "new thoughts" do
    test "renders form", %{conn: conn} do
      conn = get(conn, ~p"/thoughts/new")
      assert html_response(conn, 200) =~ "New Thoughts"
    end
  end

  describe "create thoughts" do
    test "redirects to show when data is valid", %{conn: conn} do
      conn = post(conn, ~p"/thoughts", thoughts: @create_attrs)

      assert %{id: id} = redirected_params(conn)
      assert redirected_to(conn) == ~p"/thoughts/#{id}"

      conn = get(conn, ~p"/thoughts/#{id}")
      assert html_response(conn, 200) =~ "Thoughts #{id}"
    end

    test "renders errors when data is invalid", %{conn: conn} do
      conn = post(conn, ~p"/thoughts", thoughts: @invalid_attrs)
      assert html_response(conn, 200) =~ "New Thoughts"
    end
  end

  describe "edit thoughts" do
    setup [:create_thoughts]

    test "renders form for editing chosen thoughts", %{conn: conn, thoughts: thoughts} do
      conn = get(conn, ~p"/thoughts/#{thoughts}/edit")
      assert html_response(conn, 200) =~ "Edit Thoughts"
    end
  end

  describe "update thoughts" do
    setup [:create_thoughts]

    test "redirects when data is valid", %{conn: conn, thoughts: thoughts} do
      conn = put(conn, ~p"/thoughts/#{thoughts}", thoughts: @update_attrs)
      assert redirected_to(conn) == ~p"/thoughts/#{thoughts}"

      conn = get(conn, ~p"/thoughts/#{thoughts}")
      assert html_response(conn, 200) =~ "some updated text"
    end

    test "renders errors when data is invalid", %{conn: conn, thoughts: thoughts} do
      conn = put(conn, ~p"/thoughts/#{thoughts}", thoughts: @invalid_attrs)
      assert html_response(conn, 200) =~ "Edit Thoughts"
    end
  end

  describe "delete thoughts" do
    setup [:create_thoughts]

    test "deletes chosen thoughts", %{conn: conn, thoughts: thoughts} do
      conn = delete(conn, ~p"/thoughts/#{thoughts}")
      assert redirected_to(conn) == ~p"/thoughts"

      assert_error_sent 404, fn ->
        get(conn, ~p"/thoughts/#{thoughts}")
      end
    end
  end

  defp create_thoughts(_) do
    thoughts = thoughts_fixture()
    %{thoughts: thoughts}
  end
end
