from django.urls import path
from .views import FCMTokenRegisterView, FCMTokenDeleteView, ScheduledNotificationTrigger

app_name = 'notification'

urlpatterns = [
    path('register-fcm-token/', FCMTokenRegisterView.as_view(), name='register_fcm_token'),
    path('delete-fcm-token/', FCMTokenDeleteView.as_view(), name='delete_fcm_token'),
    path('cron/send-daily-message/', ScheduledNotificationTrigger.as_view(), name='cron_send_daily_message'),

] 