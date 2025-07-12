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
        print(f"Timestamp: {datetime.now()}")
        print(f"User: {request.user.username} (ID: {request.user.id})")
        print(f"Request Method: {request.method}")
        print(f"Request Path: {request.path}")
        print(f"User Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
        print(f"Remote Address: {request.META.get('REMOTE_ADDR', 'Unknown')}")
        print(f"X-Forwarded-For: {request.META.get('HTTP_X_FORWARDED_FOR', 'None')}")
        print(f"Request Headers: {dict(request.headers)}")
        
        # iOS Safari 특별 로깅
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        is_ios = 'iPhone' in user_agent or 'iPad' in user_agent or 'iPod' in user_agent
        is_safari = 'Safari' in user_agent and 'Chrome' not in user_agent
        
        print(f"iOS Device: {is_ios}")
        print(f"Safari Browser: {is_safari}")
        
        return Response({
            'message': 'FCM API is accessible',
            'user': request.user.username,
            'timestamp': str(datetime.now()),
            'is_ios': is_ios,
            'is_safari': is_safari,
            'user_agent': user_agent
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
        print(f"Timestamp: {datetime.now()}")
        print(f"User: {request.user.username} (ID: {request.user.id})")
        print(f"Request Method: {request.method}")
        print(f"Request Path: {request.path}")
        print(f"User Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
        print(f"Remote Address: {request.META.get('REMOTE_ADDR', 'Unknown')}")
        print(f"X-Forwarded-For: {request.META.get('HTTP_X_FORWARDED_FOR', 'None')}")
        print(f"Request Headers: {dict(request.headers)}")
        print(f"Request Data: {request.data}")
        print(f"Content Type: {request.content_type}")
        
        # iOS Safari 특별 로깅
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        is_ios = 'iPhone' in user_agent or 'iPad' in user_agent or 'iPod' in user_agent
        is_safari = 'Safari' in user_agent and 'Chrome' not in user_agent
        
        print(f"iOS Device: {is_ios}")
        print(f"Safari Browser: {is_safari}")
        
        registration_id = request.data.get('token')
        device_name = request.data.get('name', None)
        platform = request.data.get('platform', None)
        user_agent = request.data.get('user_agent', None)

        # 토큰 유효성 검증 강화
        if not registration_id:
            print("❌ ERROR: No registration token provided")
            print(f"Available data keys: {list(request.data.keys())}")
            return Response({'error': 'FCM registration token is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 테스트 토큰인지 확인
        is_test_token = registration_id.startswith('test_token_') or registration_id.startswith('ios_test_token_')
        
        # 실제 FCM 토큰인 경우에만 형식 검증
        if not is_test_token:
            # 토큰 길이 및 형식 검증
            if len(registration_id) < 100:
                print("❌ ERROR: FCM token too short")
                return Response({'error': 'Invalid FCM token format.'}, status=status.HTTP_400_BAD_REQUEST)
            
            if len(registration_id) > 500:
                print("❌ ERROR: FCM token too long")
                return Response({'error': 'Invalid FCM token format.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # 토큰 형식 검증 (FCM 토큰은 보통 특정 패턴을 가짐)
            import re
            if not re.match(r'^[A-Za-z0-9:_-]+$', registration_id):
                print("❌ ERROR: Invalid FCM token format")
                return Response({'error': 'Invalid FCM token format.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            print(f"✅ Test token detected: {registration_id[:50]}...")
            # 테스트 토큰은 길이만 확인
            if len(registration_id) < 10:
                print("❌ ERROR: Test token too short")
                return Response({'error': 'Invalid test token format.'}, status=status.HTTP_400_BAD_REQUEST)

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
            
            # 브라우저 정보 추출
            browser_info = self.extract_browser_info(final_user_agent)
            device_type = self.detect_device_type(final_user_agent)
            
            print(f"Final platform: {final_platform}")
            print(f"Final user agent: {final_user_agent}")
            print(f"Browser info: {browser_info}")
            print(f"Device type: {device_type}")
            
            # 이미 존재하는 토큰인지 확인하고 업데이트하거나 새로 생성
            fcm_device, created = FCMDevice.objects.update_or_create(
                user=request.user,
                registration_id=registration_id,
                defaults={
                    'name': device_name, 
                    'active': True,
                    'user_agent': final_user_agent,
                    'platform': final_platform,
                    'device_type': device_type,
                    'browser': browser_info,
                    'app_version': request.data.get('app_version', None)
                }
            )
            
            # 모델 유효성 검증
            try:
                fcm_device.full_clean()
            except Exception as validation_error:
                print(f"❌ Validation error: {validation_error}")
                return Response({'error': 'Invalid device data.'}, status=status.HTTP_400_BAD_REQUEST)
            
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
            
            # 성공 응답에 추가 정보 포함
            response_data = {
                'message': 'FCM token registered successfully.', 
                'created': created,
                'platform': final_platform,
                'device_id': fcm_device.id,
                'total_devices': total_devices,
                'active_devices': active_devices,
                'device_name': fcm_device.get_display_name(),
                'device_type': device_type,
                'browser': browser_info
            }
            
            print(f"✅ Response sent: {response_data}")
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"❌ ERROR registering FCM token: {e}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def extract_browser_info(self, user_agent):
        """User agent에서 브라우저 정보 추출"""
        if not user_agent:
            return None
        
        user_agent_lower = user_agent.lower()
        
        if 'chrome' in user_agent_lower:
            return 'Chrome'
        elif 'safari' in user_agent_lower and 'chrome' not in user_agent_lower:
            return 'Safari'
        elif 'firefox' in user_agent_lower:
            return 'Firefox'
        elif 'edge' in user_agent_lower:
            return 'Edge'
        elif 'opera' in user_agent_lower:
            return 'Opera'
        else:
            return 'Unknown'

    def detect_device_type(self, user_agent):
        """User agent에서 디바이스 타입 감지"""
        if not user_agent:
            return 'desktop'
        
        user_agent_lower = user_agent.lower()
        
        if any(keyword in user_agent_lower for keyword in ['mobile', 'android', 'iphone', 'ipad']):
            return 'mobile'
        elif 'tablet' in user_agent_lower:
            return 'tablet'
        else:
            return 'desktop'


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
    """
    일일 알림 전송을 위한 cron-job 전용 뷰
    - cron-job.org에서만 호출됨
    - 모든 활성 사용자에게 일일 알림 전송
    """
    def post(self, request):
        # Cron job 시크릿 키 확인
        cron_secret = request.headers.get('X-Secret-Key')
        print(f"Received cron secret: {cron_secret}")
        print(f"Expected cron secret: {settings.CRON_SECRET_KEY}")
        
        if not cron_secret or cron_secret != settings.CRON_SECRET_KEY:
            return Response({'error': 'Invalid cron secret'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            # 모든 활성 사용자에게 알림 전송
            User = get_user_model()
            users_to_notify = User.objects.filter(is_active=True)
            sent_count = 0
            ios_count = 0
            web_count = 0
            failed_count = 0
            retry_users = []
            
            print(f"[CRON] Starting notification to {users_to_notify.count()} users")
            
            # 1차 전송
            for user in users_to_notify:
                try:
                    title = "오늘 하루 잘 보내셨나요?"
                    body = f"{user.username}님, 잊지 않으셨죠? 오늘을 기록해보세요."
                    data = {"type": "daily_evening_message", "user_id": str(user.id)}
                    
                    # iOS 사용자 확인
                    is_ios_user = any(device.is_ios_device() for device in user.fcm_devices.filter(active=True))
                    
                    print(f"[CRON] Sending to {user.username} (iOS: {is_ios_user})")
                    
                    if send_fcm_notification(user, title, body, data):
                        sent_count += 1
                        if is_ios_user:
                            ios_count += 1
                        else:
                            web_count += 1
                        print(f"[CRON] Success: {user.username}")
                    else:
                        failed_count += 1
                        retry_users.append(user)
                        print(f"[CRON] Failed: {user.username}")
                        
                except Exception as e:
                    failed_count += 1
                    retry_users.append(user)
                    print(f"[CRON] Error for {user.username}: {e}")
            
            # 최종 실패 수는 1차 시도에서 실패한 사용자 수
            final_failed = len(retry_users)
            
            print(f"[CRON] Final results - Success: {sent_count}, Failed: {final_failed}")
            
            return Response({
                'message': 'Scheduled task executed successfully',
                'users_notified': sent_count,
                'ios_users': ios_count,
                'web_users': web_count,
                'failed_users': final_failed,
                'total_users': users_to_notify.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
