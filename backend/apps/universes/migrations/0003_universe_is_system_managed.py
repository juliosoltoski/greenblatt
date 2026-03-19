from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("universes", "0002_universe_is_starred_universe_notes_universe_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="universe",
            name="is_system_managed",
            field=models.BooleanField(default=False),
        ),
    ]
