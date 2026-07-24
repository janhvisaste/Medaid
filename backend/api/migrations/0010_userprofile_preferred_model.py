from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0009_remove_medicalreport_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='preferred_model',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
