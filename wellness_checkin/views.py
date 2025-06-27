from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import SurveyQuestion, DailyCheckIn
from django.db import IntegrityError
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

# Create your views here.

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
        # 각 문항에 대해 응답 추출 및 유효성 검사
        for q in questions:
            val = request.POST.get(q.question_key)
            if val is None or val == '':
                errors.append(f"{q.question_text}에 응답해 주세요.")
                continue
            try:
                score = int(val)
            except ValueError:
                errors.append(f"{q.question_text}의 점수가 올바르지 않습니다.")
                continue
            if not (q.min_score <= score <= q.max_score):
                errors.append(f"{q.question_text}의 점수는 {q.min_score}~{q.max_score} 사이여야 합니다.")
            responses[q.question_key] = score
        # 체중 유효성 검사
        if not weight:
            errors.append("아침 공복 체중을 입력해 주세요.")
        else:
            try:
                weight = float(weight)
            except ValueError:
                errors.append("체중은 숫자여야 합니다.")
        if errors:
            for err in errors:
                messages.error(request, err)
            # 기존 입력값을 다시 전달
            return render(request, 'wellness_checkin/daily_checkin_input.html', {
                'questions': questions,
                'existing_checkin': existing_checkin,
                'input_weight': request.POST.get('morning_fasting_weight', ''),
                'input_responses': responses,
                'today': today,
            })
        # 저장 또는 수정
        if existing_checkin:
            existing_checkin.morning_fasting_weight = weight
            existing_checkin.responses = responses
            existing_checkin.save()
            messages.success(request, "기록이 수정되었습니다!")
        else:
            try:
                DailyCheckIn.objects.create(
                    user=user,
                    date=today,
                    morning_fasting_weight=weight,
                    responses=responses
                )
                messages.success(request, "기록되었습니다!")
            except IntegrityError:
                messages.error(request, "이미 오늘의 기록이 존재합니다.")
        return redirect('wellness_checkin:daily_checkin_input')
    # GET 요청: 기존 데이터 전달
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
def wellness_dashboard_view(request):
    user = request.user
    # 기간 필터링: 기본 28일(4주), ?period=14 등 지원
    try:
        period = int(request.GET.get('period', 28))
    except ValueError:
        period = 28
    today = timezone.localdate()
    start_date = today - timezone.timedelta(days=period-1)
    checkins = DailyCheckIn.objects.filter(user=user, date__gte=start_date, date__lte=today).order_by('date')
    if not checkins.exists():
        return render(request, 'wellness_checkin/wellness_dashboard.html', {
            'no_data': True,
            'period': period,
            'today': today,
        })
    # 체중 변화 추이 데이터
    weight_data = [{'date': c.date.strftime('%Y-%m-%d'), 'weight': c.morning_fasting_weight} for c in checkins]
    # 활성화된 문항 정보
    questions = SurveyQuestion.objects.filter(is_active=True).order_by('order')
    question_keys = [q.question_key for q in questions]
    question_texts = {q.question_key: q.question_text for q in questions}
    # 웰니스 점수 변화 추이 데이터
    wellness_data = {k: [] for k in question_keys}
    for c in checkins:
        for k in question_keys:
            val = c.responses.get(k)
            wellness_data[k].append({'date': c.date.strftime('%Y-%m-%d'), 'score': val})
    # 체중 변화 리스트 (그래프용)
    weight_data_weights = [c['weight'] for c in weight_data]
    # AI 인사이트: 최소 14개 이상 데이터일 때만 회귀분석
    ai_insight = None
    insight_message = None
    if checkins.count() >= 14:
        # 데이터프레임 생성
        df = pd.DataFrame([
            {'date': c.date, 'weight': c.morning_fasting_weight, **c.responses} for c in checkins
        ])
        # X: 오늘의 설문, y: 다음날 체중
        X = df[question_keys][:-1].values
        y = df['weight'][1:].values
        # 회귀분석
        model = LinearRegression()
        model.fit(X, y)
        coefs = model.coef_
        # 영향력 큰 상위 5개 추출 (절댓값 기준)
        coef_info = []
        # SurveyQuestion badge_label 매핑
        badge_labels = {q.question_key: (q.badge_label or q.question_key.upper()) for q in questions}
        for i, k in enumerate(question_keys):
            coef_info.append({
                'key': k,
                'text': question_texts[k],
                'coef': coefs[i],
                'badge': badge_labels.get(k, k.upper()),
                'label': badge_labels.get(k, k.upper()),  # 그래프용 한글 약칭
            })
        coef_info = sorted(coef_info, key=lambda x: abs(x['coef']), reverse=True)[:5]
        # 긍정/부정 분리
        positive = [c for c in coef_info if c['coef'] < 0]  # 체중 감소에 기여
        negative = [c for c in coef_info if c['coef'] > 0]  # 체중 증가에 기여
        ai_insight = {
            'positive': positive,
            'negative': negative,
        }
        # 템플릿용 리스트 가공
        ai_insight_labels_positive = [c['label'] for c in positive]
        ai_insight_labels_negative = [c['label'] for c in negative]
        ai_insight_data_positive = [c['coef'] for c in positive]
        ai_insight_data_negative = [c['coef'] for c in negative]
    else:
        insight_message = "아직 고객님의 웰니스 패턴을 분석하기 위한 데이터가 부족합니다. 매일 꾸준히 기록하시면 더욱 정확한 인사이트를 드릴 수 있어요!"
        ai_insight_labels_positive = []
        ai_insight_labels_negative = []
        ai_insight_data_positive = []
        ai_insight_data_negative = []
    weight_data_dates = [c['date'] for c in weight_data]
    weight_data_weights = [c['weight'] for c in weight_data]
    wellness_data_scores = {k: [v['score'] for v in wellness_data[k]] for k in question_keys}
    # JS용 데이터셋 가공
    wellness_chart_datasets = [
        {
            'label': q.question_text,
            'data': wellness_data_scores[q.question_key],
        }
        for q in questions
    ]
    # 각 문항별 개별 그래프용 데이터 (체중도 포함)
    wellness_questions_chart_data = [
        {
            'question_key': q.question_key,
            'question_text': q.question_text,
            'scores': wellness_data_scores[q.question_key],
            'scores_smooth': moving_average(wellness_data_scores[q.question_key], window=3),
            'weights': weight_data_weights,
            'badge': badge_labels.get(q.question_key, q.question_key.upper()),
        }
        for q in questions
    ]
    return render(request, 'wellness_checkin/wellness_dashboard.html', {
        'weight_data': weight_data,
        'weight_data_dates': weight_data_dates,
        'weight_data_weights': weight_data_weights,
        'wellness_data': wellness_data,
        'wellness_data_scores': wellness_data_scores,
        'wellness_chart_datasets': wellness_chart_datasets,
        'wellness_questions_chart_data': wellness_questions_chart_data,
        'questions': questions,
        'ai_insight': ai_insight,
        'ai_insight_labels_positive': ai_insight_labels_positive,
        'ai_insight_labels_negative': ai_insight_labels_negative,
        'ai_insight_data_positive': ai_insight_data_positive,
        'ai_insight_data_negative': ai_insight_data_negative,
        'insight_message': insight_message,
        'period': period,
        'today': today,
        'no_data': False,
    })

def moving_average(arr, window=3):
    arr = np.array(arr, dtype=float)
    if len(arr) < window:
        return arr.tolist()
    return np.convolve(arr, np.ones(window)/window, mode='same').tolist()
