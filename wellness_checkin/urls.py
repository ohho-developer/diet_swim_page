from django.urls import path
from . import views

app_name = 'wellness_checkin'

urlpatterns = [
    path('checkin/', views.daily_checkin_input_view, name='daily_checkin_input'),
    path('dashboard/loading/', views.wellness_dashboard_loading_view, name='dashboard_loading'),
    path('dashboard/', views.wellness_dashboard_view, name='dashboard'),
    path('causal_analysis/', views.causal_analysis_api, name='causal_analysis'),
    path('checkin/edit/<int:pk>/', views.checkin_edit_view, name='checkin_edit'),
    path('history/', views.checkin_history_view, name='checkin_history'),
    path('checkin/delete/<int:pk>/', views.checkin_delete_view, name='checkin_delete'),
] 