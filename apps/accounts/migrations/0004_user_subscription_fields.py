# Generated manually for SaaS subscription + trial fields

from datetime import timedelta

from django.db import migrations, models


def backfill_trial_ends_at(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.filter(trial_ends_at__isnull=True):
        user.trial_ends_at = user.date_joined + timedelta(days=30)
        user.save(update_fields=['trial_ends_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_passwordresetotp'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='stripe_customer_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='user',
            name='stripe_subscription_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='user',
            name='subscription_status',
            field=models.CharField(
                db_index=True,
                default='none',
                help_text='Stripe subscription.status (e.g. active, canceled) or none for the monthly SaaS plan.',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='trial_ends_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Business features allowed before this instant without a paid Stripe subscription.',
                null=True,
            ),
        ),
        migrations.RunPython(backfill_trial_ends_at, migrations.RunPython.noop),
    ]
