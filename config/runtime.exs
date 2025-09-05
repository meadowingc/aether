import Config

# Load environment variables from .env (simple loader, no external dependency)
env_file = Path.expand("../.env", __DIR__)
if File.exists?(env_file) do
  env_file
  |> File.stream!()
  |> Stream.map(&String.trim/1)
  |> Stream.reject(&(&1 == "" or String.starts_with?(&1, "#")))
  |> Enum.each(fn line ->
    case String.split(line, "=", parts: 2) do
      [k, v] -> System.put_env(k, v)
      _ -> :ok
    end
  end)
end

# config/runtime.exs is executed for all environments, including
# during releases. It is executed after compilation and before the
# system starts, so it is typically used to load production configuration
# and secrets from environment variables or elsewhere. Do not define
# any compile-time configuration in here, as it won't be applied.
# The block below contains prod specific runtime configuration.

# ## Using releases
#
# If you use `mix release`, you need to explicitly enable the server
# by passing the PHX_SERVER=true when you start it:
#
#     PHX_SERVER=true bin/aether_phx start
#
# Alternatively, you can use `mix phx.gen.release` to generate a `bin/server`
# script that automatically sets the env var above.
if System.get_env("PHX_SERVER") do
  config :aether_phx, AetherPhxWeb.Endpoint, server: true
end

# Dev runtime secret (moves dev secret_key_base out of dev.exs into env)
if config_env() == :dev do
  secret_key_base =
    System.get_env("SECRET_KEY_BASE") ||
      raise """
      environment variable SECRET_KEY_BASE is missing.
      Generate one with: mix phx.gen.secret
      """

  config :aether_phx, AetherPhxWeb.Endpoint,
    secret_key_base: secret_key_base
end

if config_env() == :prod do
  # Optional runtime database path override. If DATABASE_PATH is unset, we fall back
  # to the compile-time path configured in config.exs (../aether_phx_prod.db)
  if db_path = System.get_env("DATABASE_PATH") do
    config :aether_phx, AetherPhx.Repo, database: db_path
  end

  # The secret key base is required in prod
  secret_key_base =
    System.get_env("SECRET_KEY_BASE") ||
      raise """
      environment variable SECRET_KEY_BASE is missing.
      You can generate one by calling: mix phx.gen.secret
      """

  host = System.get_env("PHX_HOST") || "example.com"
  port = String.to_integer(System.get_env("PORT") || "4000")

  config :aether_phx, :dns_cluster_query, System.get_env("DNS_CLUSTER_QUERY")

  # Explicit websocket / request origin allowlist (minimal & static by design)
  # If you later need more, edit here instead of using env indirection.
  config :aether_phx, AetherPhxWeb.Endpoint,
    url: [host: host, port: 443, scheme: "https"],
    http: [
      # Enable IPv6 and bind on all interfaces.
      # Set it to  {0, 0, 0, 0, 0, 0, 0, 1} for local network only access.
      ip: {0, 0, 0, 0, 0, 0, 0, 0},
      port: port
    ],
    check_origin: [
      "https://aether.meadow.cafe",
      "http://aether.meadow.cafe",
      "http://localhost:#{port}",
      "http://127.0.0.1:#{port}"
    ],
    secret_key_base: secret_key_base

  # ## SSL Support
  #
  # To get SSL working, you will need to add the `https` key
  # to your endpoint configuration:
  #
  #     config :aether_phx, AetherPhxWeb.Endpoint,
  #       https: [
  #         ...,
  #         port: 443,
  #         cipher_suite: :strong,
  #         keyfile: System.get_env("SOME_APP_SSL_KEY_PATH"),
  #         certfile: System.get_env("SOME_APP_SSL_CERT_PATH")
  #       ]
  #
  # The `cipher_suite` is set to `:strong` to support only the
  # latest and more secure SSL ciphers. This means old browsers
  # and clients may not be supported. You can set it to
  # `:compatible` for wider support.
  #
  # `:keyfile` and `:certfile` expect an absolute path to the key
  # and cert in disk or a relative path inside priv, for example
  # "priv/ssl/server.key". For all supported SSL configuration
  # options, see https://hexdocs.pm/plug/Plug.SSL.html#configure/1
  #
  # We also recommend setting `force_ssl` in your config/prod.exs,
  # ensuring no data is ever sent via http, always redirecting to https:
  #
  #     config :aether_phx, AetherPhxWeb.Endpoint,
  #       force_ssl: [hsts: true]
  #
  # Check `Plug.SSL` for all available options in `force_ssl`.
end
