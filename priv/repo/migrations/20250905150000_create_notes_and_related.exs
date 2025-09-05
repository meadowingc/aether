defmodule AetherPhx.Repo.Migrations.CreateNotesAndRelated do
  use Ecto.Migration

  def change do
    create table(:notes) do
      add :text, :text, null: false
      add :pub_date, :utc_datetime, null: false
      add :author, :string
      add :views, :integer, null: false, default: 0
      add :flags, :integer, null: false, default: 0
      add :created_device_id, :string
      timestamps()
    end

    create index(:notes, [:pub_date])
    create index(:notes, [:created_device_id])

    create table(:note_views) do
      add :note_id, references(:notes, on_delete: :delete_all), null: false
      add :device_id, :string, null: false
      timestamps(updated_at: false)
    end

    create unique_index(:note_views, [:note_id, :device_id])
    create index(:note_views, [:device_id, :inserted_at])

    create table(:note_flags) do
      add :note_id, references(:notes, on_delete: :delete_all), null: false
      add :device_id, :string, null: false
      timestamps(updated_at: false)
    end

    create unique_index(:note_flags, [:note_id, :device_id])
    create index(:note_flags, [:device_id, :inserted_at])
  end
end
