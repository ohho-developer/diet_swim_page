from django.urls import path
from .views import FCMTokenRegisterView, send_test_notification_view, ScheduledNotificationTrigger

app_name = 'notification'

urlpatterns = [
    path('register-fcm-token/', FCMTokenRegisterView.as_view(), name='register_fcm_token'),
    path('send-test-notification/', send_test_notification_view, name='send_test_notification'),
    path('cron/send-daily-message/', ScheduledNotificationTrigger.as_view(), name='cron_send_daily_message'),

] 