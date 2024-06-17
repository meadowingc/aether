defmodule Aether.Repo.Migrations.CreateThoughts do
  use Ecto.Migration

  def change do
    create table(:thoughts) do
      add :text, :string
      add :antidote, :string
      add :expires_on, :naive_datetime

      timestamps(type: :utc_datetime)
    end
  end
end
