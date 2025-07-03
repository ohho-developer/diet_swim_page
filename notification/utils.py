from firebase_admin import messaging
from .models import FCMDevice
from django.contrib.auth import get_user_model

User = get_user_model()

def send_fcm_notification(user, title, body, data=None):
    """
    특정 사용자에게 FCM 푸시 알림을 보냅니다.
    :param user: 알림을 보낼 Django User 객체
    :param title: 알림 제목
    :param body: 알림 내용
    :param data: (선택 사항) 알림과 함께 보낼 추가 데이터 (딕셔너리 형태)
    """
    # 해당 사용자의 활성화된 모든 FCM 디바이스 토큰을 가져옵니다.
    devices = FCMDevice.objects.filter(user=user, active=True)
    if not devices:
        print(f"No active FCM devices found for user: {user.username}")
        return False

    registration_ids = [device.registration_id for device in devices]
    print(f"[DEBUG] Sending FCM to user: {user.username}, registration_ids: {registration_ids}")

    # data는 문자열-문자열 맵이어야 합니다.
    # 기존 data가 있다면 병합하고, 없다면 새로 만듭니다.
    payload_data = data if data is not None else {}

    # 알림 클릭 시 이동할 URL을 추가합니다.
    # 중요: URL은 반드시 문자열이어야 합니다.
    payload_data['url'] = 'https://bloomingswim.designusplus.com' # 여기에 원하는 URL을 직접 지정


    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=payload_data,  # data는 문자열-문자열 맵이어야 합니다.
        tokens=registration_ids,
    )

    try:
        response = messaging.send_each_for_multicast(message)
        success_count = sum(1 for r in response.responses if r.success)
        failure_count = sum(1 for r in response.responses if not r.success)
        print(f"Successfully sent message: {success_count} successful, {failure_count} failed")

        # 실패한 토큰 처리 (선택 사항):
        if failure_count > 0:
            for i, resp in enumerate(response.responses):
                if not resp.success:
                    failed_token = registration_ids[i]
                    print(f"Failed to send to token {failed_token}: {resp.exception}")
                    FCMDevice.objects.filter(registration_id=failed_token).update(active=False)

        return True
    except Exception as e:
        print(f"Error sending FCM notification: {e}")
        print(f"[DEBUG] registration_ids at error: {registration_ids}")
        import traceback
        traceback.print_exc()
        return False

def send_fcm_notification_to_topic(topic, title, body, data=None):
    """
    특정 토픽을 구독하는 모든 사용자에게 FCM 푸시 알림을 보냅니다.
    """
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