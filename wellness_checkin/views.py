from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import datetime # Import datetime
from .models import SurveyQuestion, DailyCheckIn
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from pprint import pprint
from . import services

@login_required
def daily_checkin_input_view(request, pk=None):
    user = request.user
    
    # 날짜 파라미터 처리
    selected_date_str = request.GET.get('date')
    
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "유효하지 않은 날짜 형식입니다.")
            selected_date = timezone.localdate()
    else:
        # URL에 date 파라미터가 없으면 무조건 오늘 날짜로 설정
        selected_date = timezone.localdate()

    questions = SurveyQuestion.objects.filter(is_active=True).order_by('order')

    checkin_instance = None
    if pk: # pk가 있으면 수정 모드
        try:
            checkin_instance = DailyCheckIn.objects.get(pk=pk, user=user)
            selected_date = checkin_instance.date # 수정 모드에서는 인스턴스의 날짜 사용
        except DailyCheckIn.DoesNotExist:
            messages.error(request, "해당 기록을 찾을 수 없습니다.")
            return redirect('wellness_checkin:daily_checkin_input') # 찾을 수 없으면 생성 모드로 리다이렉트
    else: # pk가 없으면 생성 모드
        # 선택된 날짜에 이미 기록이 있는지 확인
        existing_checkin_for_date = DailyCheckIn.objects.filter(user=user, date=selected_date).first()
        if existing_checkin_for_date:
            # 이미 기록이 있으면 해당 기록을 checkin_instance로 설정
            checkin_instance = existing_checkin_for_date

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
                'checkin_instance': checkin_instance,
                'input_weight': request.POST.get('morning_fasting_weight', ''),
                'input_responses': responses,
                'today': selected_date,
                'is_edit_mode': pk is not None,
            })

        try:
            if checkin_instance:
                checkin_instance.morning_fasting_weight = weight
                checkin_instance.responses = responses
                checkin_instance.save()
                messages.success(request, "기록이 수정되었습니다!")
            else:
                DailyCheckIn.objects.create(
                    user=user,
                    date=selected_date,
                    morning_fasting_weight=weight,
                    responses=responses
                )
                messages.success(request, "기록되었습니다!")
        except IntegrityError:
            messages.error(request, "이미 해당 날짜의 기록이 존재합니다. 수정하려면 해당 기록을 불러와주세요.")
        except Exception as e:
            messages.error(request, f"저장 중 오류가 발생했습니다: {str(e)}")
        
        # 선택된 날짜를 세션에 저장
        request.session['last_selected_date'] = selected_date.isoformat()
        return redirect('wellness_checkin:daily_checkin_input')

    input_weight = checkin_instance.morning_fasting_weight if checkin_instance else ''
    input_responses = checkin_instance.responses if checkin_instance else {}

    # 모든 기록 날짜를 가져와 JSON으로 변환
    all_checkin_dates = DailyCheckIn.objects.filter(user=user).values_list('date', flat=True)
    existing_checkin_dates_json = json.dumps([d.isoformat() for d in all_checkin_dates])

    return render(request, 'wellness_checkin/daily_checkin_input.html', {
        'questions': questions,
        'checkin_instance': checkin_instance,
        'input_weight': input_weight,
        'input_responses': input_responses,
        'today': selected_date,
        'is_edit_mode': pk is not None,
        'existing_checkin_dates_json': existing_checkin_dates_json,
    })

@login_required
def wellness_dashboard_loading_view(request):
    return render(request, 'wellness_checkin/dashboard_loading.html')

@login_required
def checkin_edit_view(request, pk):
    return daily_checkin_input_view(request, pk)

@login_required
def wellness_dashboard_view(request):
    user = request.user
    context = services.get_dashboard_data(user)

    # Process analysis results for each category to be used in the template
    if context.get('category_analysis_results'):
        for category, results in context['category_analysis_results'].items():
            if results.get('ai_insight') and results['ai_insight'].get('positive'):
                results['insight_labels'] = [item['badge'] for item in results['ai_insight']['positive']]
                results['insight_data'] = [item['coef'] for item in results['ai_insight']['positive']]

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
        
        # Print debug logs to the console
        if 'debug_logs' in result:
            print("\n--- Causal Analysis Debug Logs ---")
            pprint(result['debug_logs'])
            print("---------------------------------\n")

        return JsonResponse(result)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
def checkin_history_view(request):
    user = request.user
    checkins = DailyCheckIn.objects.filter(user=user).order_by('-date')
    return render(request, 'wellness_checkin/checkin_history.html', {'checkins': checkins})

@login_required
def checkin_delete_view(request, pk):
    if request.method == 'POST':
        try:
            checkin = DailyCheckIn.objects.get(pk=pk, user=request.user)
            checkin.delete()
            messages.success(request, "기록이 성공적으로 삭제되었습니다.")
        except DailyCheckIn.DoesNotExist:
            messages.error(request, "해당 기록을 찾을 수 없거나 삭제 권한이 없습니다.")
        except Exception as e:
            messages.error(request, f"기록 삭제 중 오류가 발생했습니다: {str(e)}")
    return redirect('wellness_checkin:checkin_history')