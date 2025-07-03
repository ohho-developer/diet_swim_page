from django import forms
from .models import Profile
from allauth.account.forms import SignupForm

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['nickname', 'bio', 'avatar', 'email_notify', 'web_notify']

class CustomSignupForm(SignupForm):
    email = forms.EmailField(
        label='이메일',
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': '이메일을 입력하세요'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 이메일 필드를 필수로 설정
        self.fields['email'].required = True
        # 폼 필드에 부트스트랩 클래스 추가
        for field in self.fields.values():
            if hasattr(field, 'widget') and hasattr(field.widget, 'attrs'):
                field.widget.attrs.update({'class': 'form-control'}) 