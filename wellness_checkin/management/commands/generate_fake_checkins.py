from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from wellness_checkin.models import SurveyQuestion, DailyCheckIn
from django.utils import timezone
import random

class Command(BaseCommand):
    help = 'DailyCheckIn 모델에 30일치 임의 데이터를 생성합니다.'

    def handle(self, *args, **options):
        User = get_user_model()
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR('유저가 없습니다.'))
            return
        questions = list(SurveyQuestion.objects.filter(is_active=True).order_by('order'))
        if not questions:
            self.stdout.write(self.style.ERROR('활성화된 설문 문항이 없습니다.'))
            return
        today = timezone.localdate()
        for i in range(30):
            date = today - timezone.timedelta(days=29-i)
            responses = {q.question_key: random.randint(q.min_score, q.max_score) for q in questions}
            weight = 60 + random.uniform(-2, 2)
            DailyCheckIn.objects.update_or_create(
                user=user,
                date=date,
                defaults={
                    'morning_fasting_weight': weight,
                    'responses': responses
                }
            )
        self.stdout.write(self.style.SUCCESS('30일치 임의 데이터가 생성되었습니다.')) 