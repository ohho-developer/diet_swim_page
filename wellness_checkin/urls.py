from django.urls import path
from . import views

app_name = 'wellness_checkin'

urlpatterns = [
    path('checkin/', views.daily_checkin_input_view, name='daily_checkin_input'),
    path('dashboard/', views.wellness_dashboard_view, name='dashboard'),
    path('causal_analysis/', views.causal_analysis_api, name='causal_analysis'),
] 