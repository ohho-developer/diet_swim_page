from django.db import models
from django.conf import settings

# Create your models here.

class FCMDevice(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fcm_devices')
    registration_id = models.CharField(max_length=255, help_text="FCM Registration Token for this device")
    name = models.CharField(max_length=255, blank=True, null=True, help_text="Device name or identifier (e.g., 'My iPhone', 'Work PC')")
    active = models.BooleanField(default=True, help_text="Is this device currently active for notifications?")
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