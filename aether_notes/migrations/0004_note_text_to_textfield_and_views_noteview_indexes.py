from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("aether_notes", "0003_alter_note_text"),
    ]

    operations = [
        migrations.AlterField(
            model_name="note",
            name="text",
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name="note",
            name="pub_date",
            field=models.DateTimeField(db_index=True, verbose_name="date published"),
        ),
        migrations.AddField(
            model_name="note",
            name="views",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="NoteView",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("device_id", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("note", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="note_views", to="aether_notes.note")),
            ],
            options={},
        ),
        migrations.AddConstraint(
            model_name="noteview",
            constraint=models.UniqueConstraint(fields=("note", "device_id"), name="unique_note_device_view"),
        ),
        migrations.AddIndex(
            model_name="noteview",
            index=models.Index(fields=["device_id", "created_at"], name="aether_notes_noteview_device_created_idx"),
        ),
    ]
