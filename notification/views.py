from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model # 중복 제거

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated # 중복 제거

from .models import FCMDevice
from .utils import send_fcm_notification # 중복 제거
from django.conf import settings
import os


# Create your views here.
class FCMTokenRegisterView(APIView):
    permission_classes = [IsAuthenticated] # 로그인한 사용자만 접근 가능하도록

    def post(self, request):
        registration_id = request.data.get('token')
        device_name = request.data.get('name', None) # 선택 사항

        if not registration_id:
            return Response({'error': 'FCM registration token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 이미 존재하는 토큰인지 확인하고 업데이트하거나 새로 생성
            fcm_device, created = FCMDevice.objects.update_or_create(
                user=request.user,
                registration_id=registration_id,
                defaults={'name': device_name, 'active': True} # 항상 활성화 상태로
            )
            return Response({'message': 'FCM token registered successfully.', 'created': created}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


User = get_user_model()

@login_required
def send_test_notification_view(request):
    if request.method == 'GET':
        target_user_id = request.GET.get('user_id')
        if not target_user_id:
            return HttpResponse("Please provide a user_id parameter.", status=400)

        try:
            target_user = User.objects.get(id=target_user_id)
            send_fcm_notification(
                user=target_user,
                title="테스트 알림",
                body=f"{target_user.username}님, 테스트 알림입니다!",
                data={"url": "https://www.example.com/notifications", "type": "test"}
            )
            return HttpResponse(f"Test notification sent to {target_user.username}")
        except User.DoesNotExist:
            return HttpResponse("User not found.", status=404)
        except Exception as e:
            return HttpResponse(f"Error sending notification: {e}", status=500)
    return HttpResponse("Send a GET request to trigger a notification.")




class ScheduledNotificationTrigger(APIView):
    # 보안을 위해 비밀 키 확인 (필수)
    def post(self, request):
        # 클라우드타입 환경 변수에서 비밀 키를 가져옵니다.
        CRON_SECRET_KEY = os.environ.get('CRON_SECRET_KEY')
        secret_key = request.headers.get('X-Secret-Key')

        if not CRON_SECRET_KEY or secret_key != CRON_SECRET_KEY:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        try:
            # send_daily_evening_message 커스텀 명령의 로직을 여기에 직접 넣거나
            # 해당 로직을 유틸 함수로 분리하여 호출합니다.
            # 예를 들어, myapp.tasks.send_daily_evening_message() 함수를 직접 호출
            User = get_user_model()
            users_to_notify = User.objects.filter(is_active=True)
            for user in users_to_notify:
                title = "오늘 하루 잘 보내셨나요?"
                body = f"{user.username}님, 저녁 10시 알림입니다! 내일도 좋은 하루 되세요."
                data = {"type": "daily_evening_message", "user_id": str(user.id)}
                send_fcm_notification(user, title, body, data)
                print(f"Notification sent to {user.username}")

            return Response({'message': 'Scheduled task executed successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Error executing scheduled task: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
