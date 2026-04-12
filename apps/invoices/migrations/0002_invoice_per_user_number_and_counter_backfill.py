# Per-user invoice numbers + backfill user.invoice_number_next

import re

from django.db import migrations, models


def backfill_invoice_counters(apps, schema_editor):
    """Set each user's next sequence from existing INV-NNNNNN numbers (or 1 if none)."""
    User = apps.get_model("accounts", "User")
    Invoice = apps.get_model("invoices", "Invoice")
    pattern = re.compile(r"^INV-(\d+)$")
    for user in User.objects.all():
        max_seq = 0
        for number in Invoice.objects.filter(user_id=user.pk).values_list(
            "invoice_number", flat=True
        ):
            match = pattern.match(number or "")
            if match:
                max_seq = max(max_seq, int(match.group(1)))
        User.objects.filter(pk=user.pk).update(invoice_number_next=max_seq + 1)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_invoice_number_next"),
        ("invoices", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invoice",
            name="invoice_number",
            field=models.CharField(
                db_index=True,
                help_text="Invoice number unique per user; assigned by the server on create",
                max_length=50,
            ),
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                fields=("user", "invoice_number"),
                name="invoices_user_invoice_number_uniq",
            ),
        ),
        migrations.RunPython(backfill_invoice_counters, migrations.RunPython.noop),
    ]
