# myapp/management/commands/send_daily_evening_message.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from notification.utils import send_fcm_notification # 당신의 앱 이름에 맞게 수정
import traceback
import time

# Django User 모델 가져오기
User = get_user_model()

class Command(BaseCommand):
    help = 'Sends daily evening FCM notifications to active users with enhanced iOS support.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--retry-failed',
            action='store_true',
            help='Retry sending to users who failed in previous attempts',
        )
        parser.add_argument(
            '--max-retries',
            type=int,
            default=3,
            help='Maximum number of retry attempts for failed notifications',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting enhanced daily evening message sending...'))

        try:
            # 활성 사용자 필터링
            users_to_notify = User.objects.filter(is_active=True)
            
            self.stdout.write(f"Found {users_to_notify.count()} active users")

            if not users_to_notify.exists():
                self.stdout.write(self.style.WARNING('No active users found to send notifications.'))
                return

            success_count = 0
            failure_count = 0
            retry_users = []

            # 1차 알림 전송
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
                        self.stdout.write(self.style.WARNING(f'Failed to send notification to {user.username} - will retry'))
                        retry_users.append(user)
                        failure_count += 1
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error sending notification to {user.username}: {e}'))
                    retry_users.append(user)
                    failure_count += 1
                    traceback.print_exc()

            # 재시도 로직
            max_retries = options['max_retries']
            for attempt in range(1, max_retries + 1):
                if not retry_users:
                    break
                    
                self.stdout.write(f"Retry attempt {attempt}/{max_retries} for {len(retry_users)} users...")
                
                # 재시도 간격 (점진적으로 증가)
                time.sleep(attempt * 2)
                
                still_failed = []
                for user in retry_users:
                    try:
                        title = "오늘 하루 잘 보내셨나요? (재시도)"
                        body = f"{user.username}님, 저녁 10시 알림입니다! 내일도 좋은 하루 되세요."
                        data = {"type": "daily_evening_message", "user_id": str(user.id)}

                        self.stdout.write(f"Retrying notification to {user.username} (attempt {attempt})...")
                        
                        success = send_fcm_notification(user, title, body, data)
                        
                        if success:
                            self.stdout.write(self.style.SUCCESS(f'Successfully sent retry notification to {user.username}'))
                            success_count += 1
                        else:
                            self.stdout.write(self.style.WARNING(f'Retry failed for {user.username}'))
                            still_failed.append(user)
                            
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Retry error for {user.username}: {e}'))
                        still_failed.append(user)
                
                retry_users = still_failed

            # 최종 결과 출력
            self.stdout.write(self.style.SUCCESS(
                f'Enhanced daily evening message sending complete.\n'
                f'Success: {success_count}, Failed: {len(retry_users)}, '
                f'Total attempts: {success_count + failure_count + len(retry_users)}'
            ))
            
            if retry_users:
                self.stdout.write(self.style.WARNING(
                    f'Users who still failed after all retries: '
                    f'{", ".join([user.username for user in retry_users])}'
                ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Critical error in daily evening message sending: {e}'))
            traceback.print_exc()