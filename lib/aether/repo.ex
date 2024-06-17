defmodule Aether.Repo do
  use Ecto.Repo,
    otp_app: :aether,
    adapter: Ecto.Adapters.SQLite3
end
