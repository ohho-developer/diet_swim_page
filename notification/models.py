from django.db import models
from django.conf import settings

# Create your models here.

class FCMDevice(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fcm_devices')
    registration_id = models.CharField(max_length=255, help_text="FCM Registration Token for this device")
    name = models.CharField(max_length=255, blank=True, null=True, help_text="Device name or identifier (e.g., 'My iPhone', 'Work PC')")
    active = models.BooleanField(default=True, help_text="Is this device currently active for notifications?")
    # iOS 대응을 위한 추가 필드
    user_agent = models.TextField(blank=True, null=True, help_text="User agent string for platform detection")
    platform = models.CharField(max_length=20, blank=True, null=True, help_text="Platform: ios, android, web")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FCM Device"
        verbose_name_plural = "FCM Devices"
        # 이제 (user, registration_id) 쌍이 고유해야 합니다.
        # 즉, 한 사용자는 한 기기 토큰을 한 번만 등록할 수 있지만,
        # 같은 기기 토큰은 여러 사용자에게 연결될 수 있습니다.
        unique_together = ('user', 'registration_id')

    def __str__(self):
        return f"{self.user.username}'s Device: {self.registration_id[:10]}..." # 또는 이름이 있으면 이름으로
    
    def is_ios_device(self):
        """iOS 기기인지 확인"""
        if self.platform:
            return self.platform.lower() == 'ios'
        if self.user_agent:
            return 'iphone' in self.user_agent.lower() or 'ipad' in self.user_agent.lower()
        return False


class InAppNotification(models.Model):
    """인앱 알림 모델 (iOS 사용자 대체 알림)"""
    NOTIFICATION_TYPES = [
        ('daily_reminder', '일일 알림'),
        ('weekly_report', '주간 리포트'),
        ('achievement', '성취 알림'),
        ('system', '시스템 알림'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='in_app_notifications')
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='daily_reminder')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "In-App Notification"
        verbose_name_plural = "In-App Notifications"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
    
    def mark_as_read(self):
        """알림을 읽음으로 표시"""
        from django.utils import timezone
        self.is_read = True
        self.read_at = timezone.now()
        self.save()