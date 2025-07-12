from django.contrib import admin
from .models import FCMDevice, InAppNotification


# Register your models here.
@admin.register(FCMDevice)
class FCMDeviceAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'platform', 'active', 'created_at']
    list_filter = ['platform', 'active', 'created_at']
    search_fields = ['user__username', 'user__email', 'name', 'registration_id']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(InAppNotification)
class InAppNotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'title', 'body']
    readonly_fields = ['created_at', 'read_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')