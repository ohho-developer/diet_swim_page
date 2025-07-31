from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import SurveyQuestion, DailyCheckIn
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from . import services

@login_required
def daily_checkin_input_view(request):
    user = request.user
    today = timezone.localdate()
    questions = SurveyQuestion.objects.filter(is_active=True).order_by('order')
    existing_checkin = DailyCheckIn.objects.filter(user=user, date=today).first()

    if request.method == 'POST':
        weight = request.POST.get('morning_fasting_weight')
        responses = {}
        errors = []
        
        if not weight:
            errors.append("체중을 입력해 주세요.")
        else:
            try:
                weight = float(weight)
                if weight <= 0:
                    errors.append("체중은 0보다 큰 값이어야 합니다.")
                elif weight < 10:
                    errors.append("체중은 10kg 이상이어야 합니다. 올바른 값을 입력해 주세요.")
                elif weight > 300:
                    errors.append("체중은 300kg 이하여야 합니다. 올바른 값을 입력해 주세요.")
            except ValueError:
                errors.append("체중은 숫자여야 합니다 (예: 65.5).")
                weight = None
        
        for q in questions:
            val = request.POST.get(q.question_key)
            if val is None or val == '':
                errors.append(f"'{q.question_text}' 문항에 응답해 주세요.")
                continue
            try:
                score = int(val)
            except ValueError:
                errors.append(f"'{q.question_text}' 문항의 점수가 올바르지 않습니다.")
                continue
            if not (q.min_score <= score <= q.max_score):
                errors.append(f"'{q.question_text}' 문항의 점수는 {q.min_score}~{q.max_score} 사이여야 합니다.")
                continue
            responses[q.question_key] = score
        
        if len(responses) != len(questions):
            missing_questions = []
            for q in questions:
                if q.question_key not in responses:
                    missing_questions.append(q.question_text)
            if missing_questions:
                errors.append(f"다음 문항들에 응답해 주세요: {', '.join(missing_questions)}")
        
        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, 'wellness_checkin/daily_checkin_input.html', {
                'questions': questions,
                'existing_checkin': existing_checkin,
                'input_weight': request.POST.get('morning_fasting_weight', ''),
                'input_responses': responses,
                'today': today,
            })

        try:
            if existing_checkin:
                existing_checkin.morning_fasting_weight = weight
                existing_checkin.responses = responses
                existing_checkin.save()
                messages.success(request, "기록이 수정되었습니다!")
            else:
                DailyCheckIn.objects.create(
                    user=user,
                    date=today,
                    morning_fasting_weight=weight,
                    responses=responses
                )
                messages.success(request, "기록되었습니다!")
        except IntegrityError:
            messages.error(request, "이미 오늘의 기록이 존재합니다. 페이지를 새로고침 후 다시 시도해 주세요.")
        except Exception as e:
            messages.error(request, f"저장 중 오류가 발생했습니다: {str(e)}")
        
        return redirect('wellness_checkin:daily_checkin_input')

    input_weight = existing_checkin.morning_fasting_weight if existing_checkin else ''
    input_responses = existing_checkin.responses if existing_checkin else {}
    return render(request, 'wellness_checkin/daily_checkin_input.html', {
        'questions': questions,
        'existing_checkin': existing_checkin,
        'input_weight': input_weight,
        'input_responses': input_responses,
        'today': today,
    })

@login_required
def wellness_dashboard_loading_view(request):
    return render(request, 'wellness_checkin/dashboard_loading.html')

@login_required
def wellness_dashboard_view(request):
    user = request.user
    context = services.get_dashboard_data(user)

    if context.get('ai_insight') and context['ai_insight'].get('positive'):
        context['ai_insight_labels_positive'] = [item['badge'] for item in context['ai_insight']['positive']]
        context['ai_insight_data_positive'] = [item['coef'] for item in context['ai_insight']['positive']]
    
    return render(request, 'wellness_checkin/wellness_dashboard.html', context)

@csrf_exempt
@login_required
def causal_analysis_api(request):
    if request.method == "POST":
        data = json.loads(request.body)
        coef_map = data.get("coef_map", {})
        pvalue_map = data.get("pvalue_map", {})
        
        user = request.user
        checkins = DailyCheckIn.objects.filter(user=user).order_by('date')
        questions = SurveyQuestion.objects.filter(is_active=True).order_by('order')
        question_keys = [q.question_key for q in questions]
        
        result = services.perform_causal_analysis(checkins, question_keys, coef_map, pvalue_map)
        return JsonResponse(result)
    return JsonResponse({'error': 'Invalid request method'}, status=405)