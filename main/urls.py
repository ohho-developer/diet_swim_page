from django.urls import path
from . import views
from django.views.generic import TemplateView


urlpatterns = [
    path('privacy_policy/', TemplateView.as_view(template_name='main/privacy_policy.html'), name='privacy_policy'),
    path('terms/', TemplateView.as_view(template_name='main/terms.html'), name='terms'),
    # Serve the index.html template from the root URL
    path('subscribe/', views.email_subscribe, name='email_subscribe'),
    path('', views.index, name='index'),
]