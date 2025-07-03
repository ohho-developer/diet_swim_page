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


class FCMTokenDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # 현재 사용자의 모든 FCM 디바이스 토큰 삭제
            deleted_count = FCMDevice.objects.filter(user=request.user).delete()[0]
            return Response({
                'message': f'FCM tokens deleted successfully. Deleted {deleted_count} device(s).',
                'deleted_count': deleted_count
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


User = get_user_model()






class ScheduledNotificationTrigger(APIView):
    def post(self, request):
        # 요청 출처 확인
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        referer = request.META.get('HTTP_REFERER', '')
        
        # 브라우저에서 온 요청인지 확인 (사용자가 버튼을 클릭한 경우)
        is_browser_request = any([
            'Mozilla' in user_agent,
            'Chrome' in user_agent,
            'Safari' in user_agent,
            'Firefox' in user_agent,
            'Edge' in user_agent,
            'bloomingswim.designusplus.com' in referer
        ])
        
        # 외부 cron job에서 온 요청인 경우에만 시크릿 키 검사
        if not is_browser_request:
            CRON_SECRET_KEY = os.environ.get('CRON_SECRET_KEY')
            secret_key = request.headers.get('X-Secret-Key')
            
            if not CRON_SECRET_KEY or secret_key != CRON_SECRET_KEY:
                return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        try:
            if is_browser_request:
                # 브라우저 요청: 로그인한 사용자 본인에게만 알림
                if not request.user.is_authenticated:
                    return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
                
                title = "테스트 알림"
                body = f"{request.user.username}님, 테스트 알림입니다!"
                data = {"type": "test_notification", "user_id": str(request.user.id)}
                
                if send_fcm_notification(request.user, title, body, data):
                    return Response({
                        'message': 'Test notification sent successfully',
                        'users_notified': 1,
                        'total_users': 1
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({'error': 'Failed to send notification'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                # 외부 cron job: 모든 활성 사용자에게 알림
                User = get_user_model()
                users_to_notify = User.objects.filter(is_active=True)
                sent_count = 0
                
                for user in users_to_notify:
                    title = "오늘 하루 잘 보내셨나요?"
                    body = f"{user.username}님, 잊지 않으셨죠? 오늘을 기록해보세요."
                    data = {"type": "daily_evening_message", "user_id": str(user.id)}
                    if send_fcm_notification(user, title, body, data):
                        sent_count += 1
                    print(f"Notification sent to {user.username}")

                return Response({
                    'message': 'Scheduled task executed successfully',
                    'users_notified': sent_count,
                    'total_users': users_to_notify.count()
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            print(f"Error executing scheduled task: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
