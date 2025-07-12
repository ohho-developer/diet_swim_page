from firebase_admin import messaging
from .models import FCMDevice
from django.contrib.auth import get_user_model
import re
import json

User = get_user_model()

def is_ios_user(user):
    """사용자가 iOS 기기를 사용하는지 확인"""
    devices = FCMDevice.objects.filter(user=user, active=True)
    for device in devices:
        if device.is_ios_device():
            return True
    return False

def send_in_app_notification(user, title, body, data=None):
    """인앱 알림 저장 (데이터베이스에 저장하여 웹에서 표시)"""
    try:
        from .models import InAppNotification
        notification = InAppNotification.objects.create(
            user=user,
            title=title,
            body=body,
            data=data or {},
            notification_type='daily_reminder'
        )
        print(f"[DEBUG] In-app notification saved for {user.username}")
        return True
    except Exception as e:
        print(f"[DEBUG] In-app notification failed: {e}")
        return False

def send_ios_notification(user, title, body, data=None):
    """iOS 사용자를 위한 FCM 푸시 알림"""
    success_count = 0
    
    # iOS FCM 푸시 알림
    ios_devices = FCMDevice.objects.filter(user=user, active=True, platform='ios')
    if ios_devices.exists():
        try:
            registration_ids = [device.registration_id for device in ios_devices]
            
            # iOS용 FCM 메시지
            message = messaging.MulticastMessage(
                data={
                    "title": title,
                    "body": body,
                    "click_action": "https://bloomingswim.designusplus.com",
                    **{k: str(v) for k, v in (data or {}).items()}
                },
                tokens=registration_ids,
                # iOS 전용 설정
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            alert=messaging.ApsAlert(
                                title=title,
                                body=body
                            ),
                            badge=1,
                            sound='default'
                        )
                    )
                )
            )
            
            response = messaging.send_each_for_multicast(message)
            ios_success = sum(1 for r in response.responses if r.success)
            success_count += ios_success
            print(f"[DEBUG] iOS push notification: {ios_success} successful")
            
        except Exception as e:
            print(f"[DEBUG] iOS push notification failed: {e}")
    
    return success_count > 0

def send_email_notification(user, title, body, data=None):
    """이메일 알림 전송 (iOS Safari 대안)"""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from django.template.loader import render_to_string
        
        # 이메일 템플릿 렌더링
        context = {
            'user': user,
            'title': title,
            'body': body,
            'data': data or {},
            'site_url': 'https://bloomingswim.designusplus.com'
        }
        
        html_message = render_to_string('notification/email_notification.html', context)
        plain_message = f"{title}\n\n{body}\n\n사이트 방문: https://bloomingswim.designusplus.com"
        
        # 이메일 전송
        send_mail(
            subject=f"[Blooming Swim] {title}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        print(f"[DEBUG] Email notification sent to {user.username} ({user.email})")
        return True
        
    except Exception as e:
        print(f"[DEBUG] Email notification failed for {user.username}: {e}")
        return False

def send_fcm_notification(user, title, body, data=None, data_only=False):
    """
    특정 사용자에게 FCM 푸시 알림을 보냅니다.
    백그라운드/앱이 꺼져있을 때도 받을 수 있는 실제 푸시 알림
    """
    # Firebase Admin SDK 초기화 확인 및 재시도
    try:
        import firebase_admin
        if not firebase_admin._apps:
            print("[ERROR] Firebase Admin SDK not initialized, attempting to initialize...")
            # Firebase 초기화 시도
            try:
                from django.conf import settings
                import base64
                import json
                
                # 환경 변수에서 서비스 계정 키 가져오기
                service_account_b64 = settings.FIREBASE_SERVICE_ACCOUNT_B64
                if service_account_b64:
                    service_account_info = json.loads(base64.b64decode(service_account_b64))
                    firebase_admin.initialize_app(
                        credential=firebase_admin.credentials.Certificate(service_account_info)
                    )
                    print("[SUCCESS] Firebase Admin SDK initialized successfully")
                else:
                    print("[ERROR] FIREBASE_SERVICE_ACCOUNT_B64 not found in settings")
                    return False
            except Exception as init_error:
                print(f"[ERROR] Failed to initialize Firebase Admin SDK: {init_error}")
                return False
    except ImportError:
        print("[ERROR] Firebase Admin SDK not available")
        return False
    
    # 해당 사용자의 활성화된 모든 FCM 디바이스 토큰을 가져옵니다.
    devices = FCMDevice.objects.filter(user=user, active=True)
    if not devices:
        print(f"No active FCM devices found for user: {user.username}")
        # FCM 디바이스가 없으면 실패로 처리
        return False

    registration_ids = [device.registration_id for device in devices]
    print(f"[DEBUG] Sending FCM to user: {user.username}, registration_ids: {registration_ids}")
    print(f"[DEBUG] Notification title: {title}, body: {body}")

    # data는 문자열-문자열 맵이어야 합니다.
    payload_data = data if data is not None else {}

    # 알림 클릭 시 이동할 URL을 추가합니다.
    payload_data['url'] = 'https://bloomingswim.designusplus.com'

    print(f"[DEBUG] Payload data: {payload_data}")

    try:
        # iOS 사용자 특별 처리
        ios_devices = [device for device in devices if device.is_ios_device()]
        web_devices = [device for device in devices if not device.is_ios_device()]
        
        success_count = 0
        
        # iOS 디바이스 처리 (강화된 로직)
        if ios_devices:
            ios_tokens = [device.registration_id for device in ios_devices]
            try:
                # iOS용 강화된 메시지 (cron job용 최적화)
                ios_message = messaging.MulticastMessage(
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                    ),
                    data=payload_data,
                    tokens=ios_tokens,
                    # iOS 전용 APNS 설정 (cron job용 강화)
                    apns=messaging.APNSConfig(
                        payload=messaging.APNSPayload(
                            aps=messaging.Aps(
                                alert=messaging.ApsAlert(
                                    title=title,
                                    body=body
                                ),
                                badge=1,
                                sound='default',
                                # iOS에서 백그라운드 처리 개선
                                content_available=True,
                                mutable_content=True,
                                # cron job용 추가 설정
                                category='DAILY_REMINDER',
                                thread_id='blooming-swim-daily'
                            ),
                            # iOS에서 알림 클릭 시 앱 열기
                            custom_data={
                                'url': 'https://bloomingswim.designusplus.com',
                                'click_action': 'FLUTTER_NOTIFICATION_CLICK',
                                'notification_type': 'daily_reminder'
                            }
                        ),
                        headers={
                            'apns-priority': '10',  # 즉시 전송
                            'apns-expiration': '0',  # 만료 없음
                            'apns-topic': 'com.bloomingswim.app'  # 앱 번들 ID
                        }
                    )
                )
                
                ios_response = messaging.send_each_for_multicast(ios_message)
                ios_success = sum(1 for r in ios_response.responses if r.success)
                success_count += ios_success
                print(f"[DEBUG] iOS push notification: {ios_success} successful, {len(ios_tokens) - ios_success} failed")
                
                # 실패한 iOS 토큰 비활성화 및 로깅
                for i, resp in enumerate(ios_response.responses):
                    if not resp.success:
                        error_msg = str(resp.exception) if hasattr(resp, 'exception') else 'Unknown error'
                        print(f"[DEBUG] iOS token failed: {ios_tokens[i][:20]}... - {error_msg}")
                        
                        # 특정 오류에 따른 처리
                        if "InvalidRegistration" in error_msg or "NotRegistered" in error_msg:
                            FCMDevice.objects.filter(registration_id=ios_tokens[i]).update(active=False)
                            print(f"[DEBUG] iOS token deactivated: {ios_tokens[i][:20]}...")
                        elif "Unregistered" in error_msg:
                            # 토큰이 만료된 경우
                            FCMDevice.objects.filter(registration_id=ios_tokens[i]).update(active=False)
                            print(f"[DEBUG] iOS token expired and deactivated: {ios_tokens[i][:20]}...")
                
            except Exception as e:
                print(f"[DEBUG] iOS push notification failed: {e}")
                # iOS 전용 오류 처리
                if "InvalidArgument" in str(e):
                    print("[DEBUG] iOS message format error, trying simplified format")
                    # 단순화된 메시지로 재시도
                    try:
                        simple_ios_message = messaging.MulticastMessage(
                            data={
                                "title": title,
                                "body": body,
                                **{k: str(v) for k, v in payload_data.items()}
                            },
                            tokens=ios_tokens,
                        )
                        simple_response = messaging.send_each_for_multicast(simple_ios_message)
                        simple_success = sum(1 for r in simple_response.responses if r.success)
                        success_count += simple_success
                        print(f"[DEBUG] Simplified iOS message: {simple_success} successful")
                    except Exception as simple_error:
                        print(f"[DEBUG] Simplified iOS message also failed: {simple_error}")
        
        # 웹 디바이스 처리
        if web_devices:
            web_tokens = [device.registration_id for device in web_devices]
            try:
                if data_only:
                    # data-only 메시지 (웹에서 더 안정적)
                    web_message = messaging.MulticastMessage(
                        data={
                            "title": title,
                            "body": body,
                            **{k: str(v) for k, v in payload_data.items()}
                        },
                        tokens=web_tokens,
                    )
                else:
                    # notification 필드 포함 (백그라운드에서도 표시)
                    web_message = messaging.MulticastMessage(
                        notification=messaging.Notification(
                            title=title,
                            body=body,
                        ),
                        data=payload_data,
                        tokens=web_tokens,
                        # 웹 푸시 최적화
                        webpush=messaging.WebpushConfig(
                            notification=messaging.WebpushNotification(
                                title=title,
                                body=body,
                                icon='/static/img/hochul.png',
                                badge='/static/img/hochul.png',
                                tag='blooming-swim-notification',
                                require_interaction=True,
                                actions=[
                                    messaging.WebpushNotificationAction(
                                        action='open',
                                        title='열기'
                                    )
                                ]
                            ),
                            fcm_options=messaging.WebpushFCMOptions(
                                link='https://bloomingswim.designusplus.com'
                            )
                        )
                    )
                
                web_response = messaging.send_each_for_multicast(web_message)
                web_success = sum(1 for r in web_response.responses if r.success)
                success_count += web_success
                print(f"[DEBUG] Web push notification: {web_success} successful, {len(web_tokens) - web_success} failed")
                
                # 실패한 웹 토큰 비활성화
                for i, resp in enumerate(web_response.responses):
                    if not resp.success:
                        FCMDevice.objects.filter(registration_id=web_tokens[i]).update(active=False)
                        print(f"[DEBUG] Web token deactivated: {web_tokens[i][:20]}...")
                
            except Exception as e:
                print(f"[DEBUG] Web push notification failed: {e}")

        print(f"Total success: {success_count} out of {len(registration_ids)}")
        return success_count > 0

    except Exception as e:
        print(f"Error sending FCM notification: {e}")
        return False

def send_fcm_notification_to_topic(topic, title, body, data=None):
    """
    특정 토픽을 구독하는 모든 사용자에게 FCM 푸시 알림을 보냅니다.
    """
    # Firebase Admin SDK 초기화 확인
    try:
        import firebase_admin
        if not firebase_admin._apps:
            print("[ERROR] Firebase Admin SDK not initialized")
            return False
    except ImportError:
        print("[ERROR] Firebase Admin SDK not available")
        return False
    
    payload_data = data if data is not None else {}
    payload_data['url'] = 'https://bloomingswim.designusplus.com' # 토픽 알림에도 URL 추가
    
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=payload_data,
        topic=topic,
    )

    try:
        response = messaging.send(message)
        print(f"Successfully sent message to topic {topic}: {response}")
        return True
    except Exception as e:
        print(f"Error sending FCM notification to topic {topic}: {e}")
        return False