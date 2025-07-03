from django.urls import path
from . import views
from .views import SignupView, LoginViewClass, LogoutViewClass, PasswordChangeViewClass, PasswordChangeDoneViewClass, UserDeleteView, ProfileView, ProfileUpdateView

app_name = 'accounts'

urlpatterns = [
    path('signup/', SignupView, name='signup'),
    path('login/', LoginViewClass, name='login'),
    path('logout/', LogoutViewClass, name='logout'),
    path('password_change/', PasswordChangeViewClass, name='password_change'),
    path('password_change/done/', PasswordChangeDoneViewClass, name='password_change_done'),
    path('delete/', UserDeleteView.as_view(), name='user_delete'),
    path('profile/update/', ProfileUpdateView.as_view(), name='profile_update'),
    path('profile/', ProfileView.as_view(), name='profile'),

] 