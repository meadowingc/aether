# This file is responsible for configuring your application
# and its dependencies with the aid of the Config module.
#
# This configuration file is loaded before any dependency and
# is restricted to this project.

# General application configuration
import Config

config :aether_phx,
  ecto_repos: [AetherPhx.Repo],
  generators: [timestamp_type: :utc_datetime]

# Base Repo configuration shared across environments.
# Only override in env files if you need sandbox, different flags, etc.
config :aether_phx, AetherPhx.Repo,
  # Dynamic per-environment database file (aether_phx_dev.db, aether_phx_prod.db, aether_phx_test.db)
  database: Path.expand("../aether_phx_#{config_env()}.db", __DIR__),
  # Pool size can still be overridden via POOL_SIZE env (esp. in prod)
  pool_size: String.to_integer(System.get_env("POOL_SIZE") || (if config_env() == :prod, do: "10", else: "5")),
  # SQLite performance / integrity pragmas
  journal_mode: :wal,
  synchronous: :normal,
  cache_size: -64000,
  foreign_keys: :on,
  busy_timeout: 5_000

# Configures the endpoint
config :aether_phx, AetherPhxWeb.Endpoint,
  url: [host: "localhost"],
  adapter: Bandit.PhoenixAdapter,
  render_errors: [
    formats: [html: AetherPhxWeb.ErrorHTML, json: AetherPhxWeb.ErrorJSON],
    layout: false
  ],
  pubsub_server: AetherPhx.PubSub,
  live_view: [signing_salt: "lZ7+sk4r"]

# Configure esbuild (the version is required)
config :esbuild,
  version: "0.17.11",
  aether_phx: [
    args:
      ~w(js/app.js --bundle --target=es2017 --outdir=../priv/static/assets --external:/fonts/* --external:/images/*),
    cd: Path.expand("../assets", __DIR__),
    env: %{"NODE_PATH" => Path.expand("../deps", __DIR__)}
  ]

# Configure tailwind (the version is required)
config :tailwind,
  version: "3.4.3",
  aether_phx: [
    args: ~w(
      --config=tailwind.config.js
      --input=css/app.css
      --output=../priv/static/assets/app.css
    ),
    cd: Path.expand("../assets", __DIR__)
  ]

# Configures Elixir's Logger
config :logger, :console,
  format: "$time $metadata[$level] $message\n",
  metadata: [:request_id]

# Use Jason for JSON parsing in Phoenix
config :phoenix, :json_library, Jason

# Kaffy admin configuration
config :kaffy,
  otp_app: :aether_phx,
  ecto_repo: AetherPhx.Repo,
  router: AetherPhxWeb.Router,
  admin_title: "Aether Admin",
  hide_dashboard: false,
  enable_context_dashboards: true

# Import environment specific config. This must remain at the bottom.
import_config "#{config_env()}.exs"
