defmodule AetherPhxWeb.Router do
  use AetherPhxWeb, :router

  import Phoenix.LiveDashboard.Router
  use Kaffy.Routes, scope: "/admin", pipe_through: [:admin_auth]

  pipeline :browser do
    plug(:accepts, ["html"])
    plug(:fetch_session)
    plug(:fetch_live_flash)
    plug(:put_root_layout, html: {AetherPhxWeb.Layouts, :root})
    plug(:protect_from_forgery)
    plug(:put_secure_browser_headers)
  end

  pipeline :api do
    plug(:accepts, ["json"])
  end

  # Basic auth for Kaffy (protects /admin)
  pipeline :admin_auth do
    plug(:basic_auth)
  end

  defp basic_auth(conn, _opts) do
    Plug.BasicAuth.basic_auth(conn,
      username: System.get_env("ADMIN_USER") || "admin",
      password: System.get_env("ADMIN_PASS") || "secret"
    )
  end

  scope "/", AetherPhxWeb do
    pipe_through(:browser)

    get("/", NoteController, :index)
    get("/about", NoteController, :about)
    post("/create-note", NoteController, :create)
    post("/witness", NoteController, :witness)
    post("/flag-note", NoteController, :flag)
    post("/delete-note", NoteController, :delete)
  end

  if Mix.env() in [:dev, :test] do
    scope "/dev" do
      pipe_through(:browser)
      live_dashboard("/dashboard", metrics: AetherPhxWeb.Telemetry)
    end
  end

  # scope "/api", AetherPhxWeb do
  #   pipe_through :api
  # end
end
