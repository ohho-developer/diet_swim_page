from django.urls import path
from . import views
from .views import UserDeleteView, ProfileView, ProfileUpdateView

app_name = 'accounts'

urlpatterns = [
    # 프로필 관련 URL만 유지 (allauth와 중복되지 않는 것들)
    path('delete/', UserDeleteView.as_view(), name='user_delete'),
    path('profile/update/', ProfileUpdateView.as_view(), name='profile_update'),
    path('profile/', ProfileView.as_view(), name='profile'),
] 