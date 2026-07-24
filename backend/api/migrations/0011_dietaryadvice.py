from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0010_userprofile_preferred_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='DietaryAdvice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_text', models.TextField(blank=True)),
                ('response_data', models.JSONField(default=dict)),
                ('context_snapshot', models.JSONField(blank=True, default=dict)),
                ('model_id', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dietary_advice', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'dietary_advice',
                'ordering': ['-created_at'],
            },
        ),
    ]
