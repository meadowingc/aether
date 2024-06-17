defmodule Aether.Repo.Migrations.RemoveThoughtManualExpirationTime do
  use Ecto.Migration

  def change do
    alter table(:thoughts) do
      remove :expires_on
    end
  end
end
