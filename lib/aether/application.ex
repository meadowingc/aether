defmodule Aether.Application do
  # See https://hexdocs.pm/elixir/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    children = [
      AetherWeb.Telemetry,
      Aether.Repo,
      {Ecto.Migrator,
       repos: Application.fetch_env!(:aether, :ecto_repos), skip: skip_migrations?()},
      {DNSCluster, query: Application.get_env(:aether, :dns_cluster_query) || :ignore},
      {Phoenix.PubSub, name: Aether.PubSub},
      # Start the Finch HTTP client for sending emails
      {Finch, name: Aether.Finch},
      # Start a worker by calling: Aether.Worker.start_link(arg)
      # {Aether.Worker, arg},
      # Start to serve requests, typically the last entry
      AetherWeb.Endpoint
    ]

    # See https://hexdocs.pm/elixir/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: Aether.Supervisor]
    Supervisor.start_link(children, opts)
  end

  # Tell Phoenix to update the endpoint configuration
  # whenever the application is updated.
  @impl true
  def config_change(changed, _new, removed) do
    AetherWeb.Endpoint.config_change(changed, removed)
    :ok
  end

  defp skip_migrations?() do
    # By default, sqlite migrations are run when using a release
    System.get_env("RELEASE_NAME") != nil
  end
end
