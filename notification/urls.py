from django.urls import path
from . import views

app_name = 'notification'

urlpatterns = [
    path('fcm/register/', views.FCMTokenRegisterView.as_view(), name='fcm_register'),
    path('fcm/delete/', views.FCMTokenDeleteView.as_view(), name='fcm_delete'),
    path('fcm/status/', views.FCMDeviceStatusView.as_view(), name='fcm_status'),
    path('scheduled/', views.ScheduledNotificationTrigger.as_view(), name='scheduled_notification'),
    # 인앱 알림 관련 URL
    path('in-app/', views.InAppNotificationView.as_view(), name='in_app_notifications'),
    path('in-app/mark-all-read/', views.MarkAllNotificationsReadView.as_view(), name='mark_all_read'),
] 