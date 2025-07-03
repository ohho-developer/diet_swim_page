from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()

class SurveyQuestion(models.Model):
    question_key = models.CharField(max_length=50, unique=True)
    question_text = models.TextField()
    guide_text = models.TextField(blank=True, null=True)
    category_main = models.CharField(max_length=50)
    order = models.IntegerField()
    is_active = models.BooleanField(default=True)
    # Optional fields for flexibility
    question_type = models.CharField(max_length=20, default='score_5pt')  # e.g., 'score_5pt', 'yes_no'
    min_score = models.IntegerField(default=1)
    max_score = models.IntegerField(default=5)
    badge_label = models.CharField(max_length=20, blank=True, verbose_name='뱃지명(한글 약칭)')

    class Meta:
        ordering = ['order']
        verbose_name = '설문 문항'
        verbose_name_plural = '설문 문항'

    def __str__(self):
        return f"[{self.category_main}] {self.question_text}"[:50]

class DailyCheckIn(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    morning_fasting_weight = models.FloatField()
    responses = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'date')
        verbose_name = '데일리 웰니스 체크인'
        verbose_name_plural = '데일리 웰니스 체크인'

    def __str__(self):
        return f"{self.user.username} - {self.date}"
