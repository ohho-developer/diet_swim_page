# myapp/management/commands/send_daily_evening_message.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from notification.utils import send_fcm_notification # 당신의 앱 이름에 맞게 수정

# Django User 모델 가져오기
User = get_user_model()

class Command(BaseCommand):
    help = 'Sends daily evening FCM notifications to active users.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting daily evening message sending...'))

        # 여기에 알림을 보낼 사용자들을 필터링하는 로직을 넣으세요.
        # 예시: 모든 활성 사용자에게 알림을 보냅니다.
        users_to_notify = User.objects.filter(is_active=True)

        if not users_to_notify.exists():
            self.stdout.write(self.style.WARNING('No active users found to send notifications.'))
            return

        for user in users_to_notify:
            title = "오늘 하루 잘 보내셨나요?"
            body = f"{user.username}님, 저녁 10시 알림입니다! 내일도 좋은 하루 되세요."
            data = {"type": "daily_evening_message", "user_id": str(user.id)}

            success = send_fcm_notification(user, title, body, data)
            if success:
                self.stdout.write(self.style.SUCCESS(f'Successfully sent notification to {user.username}'))
            else:
                self.stdout.write(self.style.ERROR(f'Failed to send notification to {user.username}'))

        self.stdout.write(self.style.SUCCESS('Daily evening message sending complete.'))