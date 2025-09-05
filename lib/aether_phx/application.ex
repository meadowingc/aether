defmodule AetherPhx.Application do
  # See https://hexdocs.pm/elixir/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    children = [
      AetherPhxWeb.Telemetry,
      AetherPhx.Repo,
      {Ecto.Migrator,
        repos: Application.fetch_env!(:aether_phx, :ecto_repos),
        skip: skip_migrations?()},
      {DNSCluster, query: Application.get_env(:aether_phx, :dns_cluster_query) || :ignore},
      {Phoenix.PubSub, name: AetherPhx.PubSub},
      # Start a worker by calling: AetherPhx.Worker.start_link(arg)
      # {AetherPhx.Worker, arg},
      # Start to serve requests, typically the last entry
      AetherPhxWeb.Endpoint
    ]

    # See https://hexdocs.pm/elixir/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: AetherPhx.Supervisor]
    Supervisor.start_link(children, opts)
  end

  # Tell Phoenix to update the endpoint configuration
  # whenever the application is updated.
  @impl true
  def config_change(changed, _new, removed) do
    AetherPhxWeb.Endpoint.config_change(changed, removed)
    :ok
  end

  defp skip_migrations?() do
    # By default, sqlite migrations are run when using a release
    System.get_env("RELEASE_NAME") != nil
  end
end
