# Generated by Django 5.2.3 on 2025-06-27 10:30

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SurveyQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question_key', models.CharField(max_length=50, unique=True)),
                ('question_text', models.TextField()),
                ('guide_text', models.TextField(blank=True, null=True)),
                ('category_main', models.CharField(max_length=50)),
                ('order', models.IntegerField()),
                ('is_active', models.BooleanField(default=True)),
                ('question_type', models.CharField(default='score_5pt', max_length=20)),
                ('min_score', models.IntegerField(default=1)),
                ('max_score', models.IntegerField(default=5)),
                ('badge_label', models.CharField(blank=True, max_length=20, verbose_name='뱃지명(한글 약칭)')),
            ],
            options={
                'verbose_name': '설문 문항',
                'verbose_name_plural': '설문 문항',
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='DailyCheckIn',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('morning_fasting_weight', models.FloatField()),
                ('responses', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': '데일리 웰니스 체크인',
                'verbose_name_plural': '데일리 웰니스 체크인',
                'unique_together': {('user', 'date')},
            },
        ),
    ]
