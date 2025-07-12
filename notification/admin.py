from django.contrib import admin
from .models import FCMDevice, InAppNotification


# Register your models here.
@admin.register(FCMDevice)
class FCMDeviceAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_display_name', 'platform', 'device_type', 'browser', 'active', 'created_at']
    list_filter = ['platform', 'device_type', 'browser', 'active', 'created_at']
    search_fields = ['user__username', 'user__email', 'name', 'registration_id', 'user_agent']
    readonly_fields = ['created_at', 'updated_at', 'last_used']
    list_per_page = 50
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('user', 'registration_id', 'name', 'active')
        }),
        ('플랫폼 정보', {
            'fields': ('platform', 'device_type', 'browser', 'app_version')
        }),
        ('기술 정보', {
            'fields': ('user_agent', 'created_at', 'updated_at', 'last_used'),
            'classes': ('collapse',)
        }),
    )
    
    def get_display_name(self, obj):
        return obj.get_display_name()
    get_display_name.short_description = '디바이스명'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # 편집 중인 경우
            return list(self.readonly_fields) + list(('registration_id', 'user'))
        return self.readonly_fields
    
    actions = ['activate_devices', 'deactivate_devices', 'delete_selected']
    
    def activate_devices(self, request, queryset):
        updated = queryset.update(active=True)
        self.message_user(request, f'{updated}개의 디바이스가 활성화되었습니다.')
    activate_devices.short_description = "선택된 디바이스 활성화"
    
    def deactivate_devices(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f'{updated}개의 디바이스가 비활성화되었습니다.')
    deactivate_devices.short_description = "선택된 디바이스 비활성화"


@admin.register(InAppNotification)
class InAppNotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'user__email', 'title', 'body']
    readonly_fields = ['created_at', 'read_at']
    list_per_page = 50
    
    fieldsets = (
        ('알림 정보', {
            'fields': ('user', 'title', 'body', 'notification_type')
        }),
        ('상태 정보', {
            'fields': ('is_read', 'read_at', 'created_at')
        }),
        ('추가 데이터', {
            'fields': ('data',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated}개의 알림이 읽음으로 표시되었습니다.')
    mark_as_read.short_description = "선택된 알림을 읽음으로 표시"
    
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False, read_at=None)
        self.message_user(request, f'{updated}개의 알림이 읽지 않음으로 표시되었습니다.')
    mark_as_unread.short_description = "선택된 알림을 읽지 않음으로 표시"