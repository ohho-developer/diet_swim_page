from django.db import models
from django.conf import settings
import re

# Create your models here.

class FCMDevice(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fcm_devices')
    registration_id = models.CharField(max_length=500, help_text="FCM Registration Token for this device")
    name = models.CharField(max_length=255, blank=True, null=True, help_text="Device name or identifier (e.g., 'My iPhone', 'Work PC')")
    active = models.BooleanField(default=True, help_text="Is this device currently active for notifications?")
    # iOS 대응을 위한 추가 필드
    user_agent = models.TextField(blank=True, null=True, help_text="User agent string for platform detection")
    platform = models.CharField(max_length=20, blank=True, null=True, help_text="Platform: ios, android, web")
    # 추가 메타데이터 필드
    device_type = models.CharField(max_length=50, blank=True, null=True, help_text="Device type: mobile, tablet, desktop")
    browser = models.CharField(max_length=50, blank=True, null=True, help_text="Browser name and version")
    app_version = models.CharField(max_length=20, blank=True, null=True, help_text="App version if applicable")
    last_used = models.DateTimeField(auto_now=True, help_text="Last time this device was used")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FCM Device"
        verbose_name_plural = "FCM Devices"
        # 이제 (user, registration_id) 쌍이 고유해야 합니다.
        # 즉, 한 사용자는 한 기기 토큰을 한 번만 등록할 수 있지만,
        # 같은 기기 토큰은 여러 사용자에게 연결될 수 있습니다.
        unique_together = ('user', 'registration_id')
        indexes = [
            models.Index(fields=['user', 'active']),
            models.Index(fields=['platform', 'active']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        username = getattr(self.user, 'username', None)
        if not username:
            username = str(self.user) if self.user else 'UnknownUser'
        regid = self.registration_id[:10] + '...' if self.registration_id else 'NoToken'
        return f"{username}'s Device: {regid}" # 또는 이름이 있으면 이름으로
    
    def clean(self):
        """모델 유효성 검증"""
        from django.core.exceptions import ValidationError
        
        # FCM 토큰 형식 검증
        if self.registration_id:
            if len(self.registration_id) < 100:
                raise ValidationError('FCM registration token is too short')
            if len(self.registration_id) > 500:
                raise ValidationError('FCM registration token is too long')
            
            # FCM 토큰은 보통 특정 패턴을 가짐
            if not re.match(r'^[A-Za-z0-9:_-]+$', self.registration_id):
                raise ValidationError('Invalid FCM registration token format')
    
    def is_ios_device(self):
        """iOS 기기인지 확인"""
        if self.platform:
            return self.platform.lower() == 'ios'
        if self.user_agent:
            return 'iphone' in self.user_agent.lower() or 'ipad' in self.user_agent.lower()
        return False
    
    def is_mobile_device(self):
        """모바일 기기인지 확인"""
        if self.device_type:
            return self.device_type.lower() in ['mobile', 'tablet']
        if self.user_agent:
            mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'blackberry', 'windows phone']
            return any(keyword in self.user_agent.lower() for keyword in mobile_keywords)
        return False
    
    def get_display_name(self):
        """디바이스 표시 이름 반환"""
        if self.name:
            return self.name
        elif self.platform:
            return f"{self.platform.title()} Device"
        else:
            return "Unknown Device"
    
    def deactivate(self):
        """디바이스 비활성화"""
        self.active = False
        self.save(update_fields=['active', 'updated_at'])


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