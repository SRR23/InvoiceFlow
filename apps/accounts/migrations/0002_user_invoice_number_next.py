# Generated manually for server-assigned invoice numbers

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="invoice_number_next",
            field=models.PositiveIntegerField(
                default=1,
                help_text="Next numeric suffix for auto-generated invoice numbers for this account",
            ),
        ),
    ]
