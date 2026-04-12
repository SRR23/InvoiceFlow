# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0002_merchantgatewaysettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="payment_url",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Gateway-hosted payment page URL for the payer (saved when the link is generated)",
            ),
        ),
    ]
