from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.decorators import login_required

@csrf_exempt
@require_POST
def email_subscribe(request):
    email = request.POST.get('email')
    if not email:
        return JsonResponse({'success': False, 'message': '이메일을 입력해주세요.'})
    # 실제로는 DB 저장 등 추가 가능
    try:
        send_mail(
            '[DietSwim] 상담 신청이 접수되었습니다',
            f'상담 신청 이메일: {email}',
            settings.DEFAULT_FROM_EMAIL,
            ['hochul.kim@designusplus.com'],
        )
        return JsonResponse({'success': True, 'message': '상담 신청이 완료되었습니다! 곧 연락드리겠습니다.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': '메일 발송에 실패했습니다.'})


def index(request):
    if request.user.is_authenticated:
        return redirect(reverse('wellness_checkin:daily_checkin_input'))
    return render(request, 'main/index.html')

@login_required
def profile(request):
    return render(request, 'main/profile.html')