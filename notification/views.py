from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model # 중복 제거

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated # 중복 제거

from .models import FCMDevice, InAppNotification
from .utils import send_fcm_notification # 중복 제거
from django.conf import settings
import os
import re
from datetime import datetime


# Create your views here.
class FCMTokenRegisterView(APIView):
    permission_classes = [IsAuthenticated] # 로그인한 사용자만 접근 가능하도록
    
    def get(self, request):
        """간단한 연결 테스트용 GET 요청"""
        print(f"\n=== FCM API Connection Test ===")
        print(f"User: {request.user.username} (ID: {request.user.id})")
        print(f"Request Method: {request.method}")
        print(f"Request Path: {request.path}")
        print(f"User Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
        print(f"Remote Address: {request.META.get('REMOTE_ADDR', 'Unknown')}")
        print(f"Request Headers: {dict(request.headers)}")
        
        return Response({
            'message': 'FCM API is accessible',
            'user': request.user.username,
            'timestamp': str(datetime.now())
        }, status=status.HTTP_200_OK)

    def detect_platform(self, user_agent):
        """User agent에서 플랫폼 감지"""
        if not user_agent:
            return 'web'
        
        user_agent_lower = user_agent.lower()
        
        if 'iphone' in user_agent_lower or 'ipad' in user_agent_lower:
            return 'ios'
        elif 'android' in user_agent_lower:
            return 'android'
        else:
            return 'web'

    def post(self, request):
        # 상세한 서버 로깅
        print(f"\n=== FCM Token Registration Request ===")
        print(f"User: {request.user.username} (ID: {request.user.id})")
        print(f"Request Method: {request.method}")
        print(f"Request Path: {request.path}")
        print(f"User Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
        print(f"Remote Address: {request.META.get('REMOTE_ADDR', 'Unknown')}")
        print(f"Request Headers: {dict(request.headers)}")
        print(f"Request Data: {request.data}")
        
        registration_id = request.data.get('token')
        device_name = request.data.get('name', None)
        platform = request.data.get('platform', None)
        user_agent = request.data.get('user_agent', None)

        if not registration_id:
            print("❌ ERROR: No registration token provided")
            return Response({'error': 'FCM registration token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        print(f"✅ Token received: {registration_id[:50]}...")
        print(f"Device Name: {device_name}")
        print(f"Platform: {platform}")
        print(f"User Agent from request: {user_agent}")

        try:
            # User agent와 플랫폼 정보 추출 (서버에서도 감지)
            server_user_agent = request.META.get('HTTP_USER_AGENT', '')
            detected_platform = self.detect_platform(server_user_agent)
            
            print(f"Server detected platform: {detected_platform}")
            print(f"Client provided platform: {platform}")
            print(f"Server User Agent: {server_user_agent}")
            
            # 플랫폼 정보 통합 (클라이언트 제공 정보 우선)
            final_platform = platform if platform else detected_platform
            final_user_agent = user_agent if user_agent else server_user_agent
            
            print(f"Final platform: {final_platform}")
            print(f"Final user agent: {final_user_agent}")
            
            # 이미 존재하는 토큰인지 확인하고 업데이트하거나 새로 생성
            fcm_device, created = FCMDevice.objects.update_or_create(
                user=request.user,
                registration_id=registration_id,
                defaults={
                    'name': device_name, 
                    'active': True,
                    'user_agent': final_user_agent,
                    'platform': final_platform
                }
            )
            
            print(f"✅ Device registration {'CREATED' if created else 'UPDATED'}")
            print(f"Device ID: {fcm_device.id}")
            print(f"Platform: {fcm_device.platform}")
            print(f"Active: {fcm_device.active}")
            print(f"Created At: {fcm_device.created_at}")
            print(f"Updated At: {fcm_device.updated_at}")
            
            # 사용자의 전체 FCM 디바이스 수 확인
            total_devices = FCMDevice.objects.filter(user=request.user).count()
            active_devices = FCMDevice.objects.filter(user=request.user, active=True).count()
            print(f"User total devices: {total_devices}")
            print(f"User active devices: {active_devices}")
            
            return Response({
                'message': 'FCM token registered successfully.', 
                'created': created,
                'platform': final_platform,
                'device_id': fcm_device.id,
                'total_devices': total_devices,
                'active_devices': active_devices
            }, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"❌ ERROR registering FCM token: {e}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FCMTokenDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        print(f"\n=== FCM Token Deletion Request ===")
        print(f"User: {request.user.username} (ID: {request.user.id})")
        print(f"Request Method: {request.method}")
        print(f"Request Path: {request.path}")
        print(f"User Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
        
        try:
            # 삭제 전 상태 확인
            before_count = FCMDevice.objects.filter(user=request.user, active=True).count()
            print(f"Active devices before deletion: {before_count}")
            
            # 현재 사용자의 모든 FCM 디바이스 토큰을 비활성화
            updated_count = FCMDevice.objects.filter(user=request.user, active=True).update(active=False)
            
            print(f"Devices deactivated: {updated_count}")
            
            # 삭제 후 상태 확인
            after_count = FCMDevice.objects.filter(user=request.user, active=True).count()
            print(f"Active devices after deletion: {after_count}")
            
            # 전체 디바이스 수 확인
            total_devices = FCMDevice.objects.filter(user=request.user).count()
            print(f"Total devices: {total_devices}")
            
            return Response({
                'message': f'FCM tokens deactivated successfully. Deactivated {updated_count} device(s).',
                'deactivated_count': updated_count,
                'total_devices': total_devices,
                'active_devices_remaining': after_count
            }, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"❌ ERROR in FCM Token Deletion: {e}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InAppNotificationView(APIView):
    """인앱 알림 관련 API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """사용자의 인앱 알림 목록 조회"""
        try:
            notifications = InAppNotification.objects.filter(
                user=request.user
            ).order_by('-created_at')[:50]  # 최근 50개만
            
            unread_count = InAppNotification.objects.filter(
                user=request.user, 
                is_read=False
            ).count()
            
            return Response({
                'notifications': [
                    {
                        'id': notif.id,
                        'title': notif.title,
                        'body': notif.body,
                        'type': notif.notification_type,
                        'is_read': notif.is_read,
                        'created_at': notif.created_at.isoformat(),
                        'data': notif.data
                    }
                    for notif in notifications
                ],
                'unread_count': unread_count
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """알림을 읽음으로 표시"""
        notification_id = request.data.get('notification_id')
        
        if not notification_id:
            return Response({'error': 'notification_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            notification = InAppNotification.objects.get(
                id=notification_id,
                user=request.user
            )
            notification.mark_as_read()
            
            return Response({
                'message': 'Notification marked as read',
                'notification_id': notification_id
            }, status=status.HTTP_200_OK)
        except InAppNotification.DoesNotExist:
            return Response({'error': 'Notification not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MarkAllNotificationsReadView(APIView):
    """모든 알림을 읽음으로 표시"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            from django.utils import timezone
            updated_count = InAppNotification.objects.filter(
                user=request.user,
                is_read=False
            ).update(is_read=True, read_at=timezone.now())
            
            return Response({
                'message': f'{updated_count} notifications marked as read',
                'updated_count': updated_count
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendDailyMessageView(APIView):
    """Cron job을 위한 일일 알림 전송 뷰"""
    
    def post(self, request):
        try:
            from django.core.management import call_command
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            
            # 활성 사용자 수 확인
            active_users = User.objects.filter(is_active=True).count()
            
            if active_users == 0:
                return Response({
                    'message': 'No active users found',
                    'users_count': 0
                }, status=status.HTTP_200_OK)
            
            # management command 실행
            call_command('send_daily_evening_message')
            
            return Response({
                'message': 'Daily evening messages sent successfully',
                'users_count': active_users
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FCMDeviceStatusView(APIView):
    """FCM 디바이스 상태 확인 API (디버깅용)"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        print(f"\n=== FCM Device Status Check ===")
        print(f"User: {request.user.username} (ID: {request.user.id})")
        print(f"Request Method: {request.method}")
        print(f"Request Path: {request.path}")
        print(f"User Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
        
        try:
            devices = FCMDevice.objects.filter(user=request.user)
            active_devices = devices.filter(active=True)
            inactive_devices = devices.filter(active=False)
            
            print(f"Total devices: {devices.count()}")
            print(f"Active devices: {active_devices.count()}")
            print(f"Inactive devices: {inactive_devices.count()}")
            
            # 플랫폼별 통계
            ios_devices = devices.filter(platform='ios')
            android_devices = devices.filter(platform='android')
            web_devices = devices.filter(platform='web')
            
            print(f"iOS devices: {ios_devices.count()}")
            print(f"Android devices: {android_devices.count()}")
            print(f"Web devices: {web_devices.count()}")
            
            # 각 디바이스 상세 정보
            for device in devices:
                print(f"Device {device.id}: {device.name} ({device.platform}) - Active: {device.active}")
                print(f"  Created: {device.created_at}")
                print(f"  Updated: {device.updated_at}")
                print(f"  Token: {device.registration_id[:50]}..." if device.registration_id else "  Token: None")
            
            return Response({
                'user': request.user.username,
                'user_id': request.user.id,
                'device_count': devices.count(),
                'active_devices': active_devices.count(),
                'inactive_devices': inactive_devices.count(),
                'platform_stats': {
                    'ios': ios_devices.count(),
                    'android': android_devices.count(),
                    'web': web_devices.count()
                },
                'devices': [
                    {
                        'id': device.id,
                        'name': device.name,
                        'platform': device.platform,
                        'active': device.active,
                        'created_at': device.created_at.isoformat(),
                        'updated_at': device.updated_at.isoformat(),
                        'registration_id': device.registration_id[:50] + '...' if device.registration_id else None,
                        'user_agent': device.user_agent[:100] + '...' if device.user_agent else None
                    }
                    for device in devices
                ]
            }, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"❌ ERROR in FCM Device Status Check: {e}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


User = get_user_model()






class ScheduledNotificationTrigger(APIView):
    def post(self, request):
        # 요청 출처 확인
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        referer = request.META.get('HTTP_REFERER', '')
        
        # 브라우저에서 온 요청인지 확인 (사용자가 버튼을 클릭한 경우)
        is_cronjob = 'cron-job.org' in user_agent
        is_browser_request = (
            not is_cronjob and (
                'mozilla' in user_agent or
                'chrome' in user_agent or
                'safari' in user_agent or
                'firefox' in user_agent or
                'edge' in user_agent or
                'bloomingswim.designusplus.com' in referer
            )
        )
        
        # 외부 cron job에서 온 요청인 경우에만 시크릿 키 검사
        if not is_browser_request:
            from django.conf import settings
            # 헤더를 여러 방식으로 읽어봄
            secret_key = request.headers.get('X-Secret-Key')
            secret_key_meta = request.META.get('HTTP_X_SECRET_KEY')
            print(f"[DEBUG] Received X-Secret-Key (headers): [{secret_key}]")
            print(f"[DEBUG] Received X-Secret-Key (META): [{secret_key_meta}]")
            print(f"[DEBUG] Expected CRON_SECRET_KEY: [{settings.CRON_SECRET_KEY}]")
            print(f"[DEBUG] Content-Type: {request.content_type}")
            # 실제 비교는 둘 중 하나라도 맞으면 통과
            if not settings.CRON_SECRET_KEY or (secret_key != settings.CRON_SECRET_KEY and secret_key_meta != settings.CRON_SECRET_KEY):
                return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        try:
            if is_browser_request:
                # 브라우저 요청: 로그인한 사용자 본인에게만 알림
                if not request.user.is_authenticated:
                    return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
                
                title = "테스트 알림"
                body = f"{request.user.username}님, 테스트 알림입니다!"
                data = {"type": "test_notification", "user_id": str(request.user.id)}
                
                if send_fcm_notification(request.user, title, body, data, data_only=True):
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
