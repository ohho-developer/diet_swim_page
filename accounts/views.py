from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.urls import reverse_lazy
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView, PasswordChangeDoneView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.views.generic import TemplateView
from .forms import ProfileForm
from .models import Profile







SignupView = CreateView.as_view(
    form_class=UserCreationForm,
    template_name='accounts/signup.html',
    success_url=reverse_lazy('accounts:login'),
)

LoginViewClass = LoginView.as_view(
    template_name='accounts/login.html',
    redirect_authenticated_user=True,
)

LogoutViewClass = LogoutView.as_view(
    next_page=reverse_lazy('accounts:login'),
)

PasswordChangeViewClass = PasswordChangeView.as_view(
    template_name='accounts/password_change.html',
    success_url=reverse_lazy('password_change_done'),
)

PasswordChangeDoneViewClass = PasswordChangeDoneView.as_view(
    template_name='accounts/password_change_done.html',
)

class UserDeleteView(LoginRequiredMixin, DeleteView):
    model = get_user_model()
    template_name = 'accounts/user_confirm_delete.html'
    success_url = reverse_lazy('accounts:login')

    def get_object(self):
        return self.request.user

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = Profile
    form_class = ProfileForm
    template_name = 'accounts/profile_update.html'
    success_url = '/accounts/profile/'

    def get_object(self):
        return self.request.user.profile
