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
    """iOS 사용자를 위한 알림 시스템 (이메일 제외)"""
    success_count = 0
    
    # 1. 인앱 알림
    if send_in_app_notification(user, title, body, data):
        success_count += 1
    
    # 2. iOS 웹 푸시 (제한적이지만 시도)
    ios_devices = FCMDevice.objects.filter(user=user, active=True, platform='ios')
    if ios_devices.exists():
        # iOS용 특별한 메시지 형식
        try:
            registration_ids = [device.registration_id for device in ios_devices]
            
            # iOS에서는 data-only 메시지가 더 안정적
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

def send_fcm_notification(user, title, body, data=None, data_only=False):
    """
    특정 사용자에게 FCM 푸시 알림을 보냅니다.
    iOS 사용자도 고려한 개선된 버전
    """
    # Firebase Admin SDK 초기화 확인
    try:
        import firebase_admin
        if not firebase_admin._apps:
            print("[ERROR] Firebase Admin SDK not initialized")
            # 인앱 알림만 시도
            return send_in_app_notification(user, title, body, data)
    except ImportError:
        print("[ERROR] Firebase Admin SDK not available")
        # 인앱 알림만 시도
        return send_in_app_notification(user, title, body, data)
    
    # iOS 사용자 확인
    if is_ios_user(user):
        print(f"[DEBUG] iOS user detected: {user.username}")
        # iOS 전용 처리
        return send_ios_notification(user, title, body, data)
    
    # 해당 사용자의 활성화된 모든 FCM 디바이스 토큰을 가져옵니다.
    devices = FCMDevice.objects.filter(user=user, active=True)
    if not devices:
        print(f"No active FCM devices found for user: {user.username}")
        # 인앱 알림만 시도
        return send_in_app_notification(user, title, body, data)

    registration_ids = [device.registration_id for device in devices]
    print(f"[DEBUG] Sending FCM to user: {user.username}, registration_ids: {registration_ids}")
    print(f"[DEBUG] Notification title: {title}, body: {body}")

    # data는 문자열-문자열 맵이어야 합니다.
    # 기존 data가 있다면 병합하고, 없다면 새로 만듭니다.
    payload_data = data if data is not None else {}

    # 알림 클릭 시 이동할 URL을 추가합니다.
    # 중요: URL은 반드시 문자열이어야 합니다.
    payload_data['url'] = 'https://bloomingswim.designusplus.com' # 여기에 원하는 URL을 직접 지정

    print(f"[DEBUG] Payload data: {payload_data}")

    try:
        if data_only:
            # data-only 메시지 (iOS에서 더 안정적)
            message = messaging.MulticastMessage(
                data={
                    "title": title,
                    "body": body,
                    **{k: str(v) for k, v in payload_data.items()}
                },
                tokens=registration_ids,
            )
        else:
            # 기존 방식 (notification 필드 포함)
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=payload_data,
                tokens=registration_ids,
            )

        response = messaging.send_each_for_multicast(message)
        success_count = sum(1 for r in response.responses if r.success)
        failure_count = sum(1 for r in response.responses if not r.success)
        print(f"Successfully sent message: {success_count} successful, {failure_count} failed")

        # 각 응답에 대한 상세 정보 출력
        for i, resp in enumerate(response.responses):
            if resp.success:
                print(f"[DEBUG] Token {i} ({registration_ids[i][:20]}...): SUCCESS")
            else:
                print(f"[DEBUG] Token {i} ({registration_ids[i][:20]}...): FAILED - {resp.exception}")
                # iOS 관련 오류는 별도 처리
                if "InvalidRegistration" in str(resp.exception) or "NotRegistered" in str(resp.exception):
                    print(f"[DEBUG] iOS device token may be invalid: {registration_ids[i][:20]}...")
                FCMDevice.objects.filter(registration_id=registration_ids[i]).update(active=False)

        # FCM 성공 여부와 관계없이 인앱 알림도 시도
        in_app_success = send_in_app_notification(user, title, body, data)
        
        return success_count > 0 or in_app_success
        
    except Exception as e:
        print(f"Error sending FCM notification: {e}")
        print(f"[DEBUG] registration_ids at error: {registration_ids}")
        import traceback
        traceback.print_exc()
        
        # FCM 실패 시 인앱 알림만 시도
        return send_in_app_notification(user, title, body, data)

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