# myapp/management/commands/send_daily_evening_message.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from notification.utils import send_fcm_notification # 당신의 앱 이름에 맞게 수정
import traceback

# Django User 모델 가져오기
User = get_user_model()

class Command(BaseCommand):
    help = 'Sends daily evening FCM notifications to active users.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting daily evening message sending...'))

        try:
            # 여기에 알림을 보낼 사용자들을 필터링하는 로직을 넣으세요.
            # 예시: 모든 활성 사용자에게 알림을 보냅니다.
            users_to_notify = User.objects.filter(is_active=True)
            
            self.stdout.write(f"Found {users_to_notify.count()} active users")

            if not users_to_notify.exists():
                self.stdout.write(self.style.WARNING('No active users found to send notifications.'))
                return

            success_count = 0
            failure_count = 0

            for user in users_to_notify:
                try:
                    title = "오늘 하루 잘 보내셨나요?"
                    body = f"{user.username}님, 저녁 10시 알림입니다! 내일도 좋은 하루 되세요."
                    data = {"type": "daily_evening_message", "user_id": str(user.id)}

                    self.stdout.write(f"Sending notification to {user.username}...")
                    
                    success = send_fcm_notification(user, title, body, data)
                    
                    if success:
                        self.stdout.write(self.style.SUCCESS(f'Successfully sent notification to {user.username}'))
                        success_count += 1
                    else:
                        self.stdout.write(self.style.ERROR(f'Failed to send notification to {user.username}'))
                        failure_count += 1
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error sending notification to {user.username}: {e}'))
                    failure_count += 1
                    # 상세한 오류 정보 출력
                    traceback.print_exc()

            self.stdout.write(self.style.SUCCESS(f'Daily evening message sending complete. Success: {success_count}, Failed: {failure_count}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Critical error in daily evening message sending: {e}'))
            traceback.print_exc()