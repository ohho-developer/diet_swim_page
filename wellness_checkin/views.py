from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import SurveyQuestion, DailyCheckIn
from django.db import IntegrityError
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from django.http import JsonResponse
import sys
import io
from scipy import stats
from statsmodels.tsa.stattools import grangercausalitytests
import warnings
from django.views.decorators.csrf import csrf_exempt
import json

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
        
        # 체중 유효성 검사 (먼저 체중 검사)
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
        
        # 각 문항에 대해 응답 추출 및 유효성 검사
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
        
        # 모든 문항이 응답되었는지 확인
        if len(responses) != len(questions):
            missing_questions = []
            for q in questions:
                if q.question_key not in responses:
                    missing_questions.append(q.question_text)
            if missing_questions:
                errors.append(f"다음 문항들에 응답해 주세요: {', '.join(missing_questions)}")
        
        # 중복 제출 방지는 이미 existing_checkin으로 처리됨 (업데이트 또는 생성)
        
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
def wellness_dashboard_loading_view(request):
    """대시보드 로딩 화면을 보여주는 뷰"""
    return render(request, 'wellness_checkin/dashboard_loading.html')

@login_required
def wellness_dashboard_view(request):
    user = request.user
    today = timezone.localdate()
    checkins = DailyCheckIn.objects.filter(user=user).order_by('date')
    if not checkins.exists():
        return render(request, 'wellness_checkin/wellness_dashboard.html', {
            'no_data': True,
            'today': today,
        })
    # 체중 변화 추이 데이터
    weight_data = [{'date': c.date.strftime('%Y-%m-%d'), 'weight': c.morning_fasting_weight} for c in checkins]
    # 활성화된 문항 정보
    questions = SurveyQuestion.objects.filter(is_active=True).order_by('order')
    question_keys = [q.question_key for q in questions]
    question_texts = {q.question_key: q.question_text for q in questions}
    # SurveyQuestion badge_label 매핑
    badge_labels = {q.question_key: (q.badge_label or q.question_key.upper()) for q in questions}
    # 웰니스 점수 변화 추이 데이터
    wellness_data = {k: [] for k in question_keys}
    for c in checkins:
        for k in question_keys:
            val = c.responses.get(k)
            # 새 질문이 추가된 경우 None 값을 null로 처리하여 그래프 인덱스 일관성 유지
            if val is None:
                # 새 질문이 추가된 경우 해당 날짜의 데이터는 null로 처리
                wellness_data[k].append({'date': c.date.strftime('%Y-%m-%d'), 'score': None})
            else:
                wellness_data[k].append({'date': c.date.strftime('%Y-%m-%d'), 'score': val})
    # 체중 변화 리스트 (그래프용)
    weight_data_weights = [c['weight'] for c in weight_data]
    # AI 인사이트: 최소 14개 이상 데이터일 때만 회귀분석
    ai_insight = None
    insight_message = None
    model_confidence = None
    best_lag = 1
    best_score = -np.inf
    best_model = None
    best_coefs = None
    best_r2 = None
    best_adj_r2 = None
    
    # 공통 회귀분석 함수 사용
    best_model, best_coefs, p_values, best_lag, best_r2, best_adj_r2, valid_question_keys = perform_regression_analysis(checkins, question_keys)
    
    if best_model is not None:
        coefs = best_coefs
        # 실제로 회귀분석에 사용된 변수들만 처리
        coef_info = []
        for i, k in enumerate(valid_question_keys):
            original_idx = question_keys.index(k) if k in question_keys else None
            coef_info.append({
                'key': k,
                'text': question_texts[k],
                'coef': coefs[i],
                'pvalue': p_values[original_idx] if original_idx is not None else None,
                'badge': badge_labels.get(k, k.upper()),
                'label': badge_labels.get(k, k.upper()),  # 그래프용 한글 약칭
                'action_text': convert_coefficient_to_action_language(coefs[i], badge_labels.get(k, k.upper())),  # 행동 언어
            })
        # p값이 0.1 미만이고 계수가 음수인 것만 사용 (체중감소에 도움이 되는 요소만)
        # 양수 계수는 체중증가에 영향을 주는 부정적인 습관이므로 제외
        coef_info = [c for c in coef_info if c['pvalue'] is not None and c['pvalue'] < 0.2 and c['coef'] < 0]
        coef_info = sorted(coef_info, key=lambda x: abs(x['coef']), reverse=True)
        # 체중감소에 도움이 되는 요소들만 (음수 계수)
        positive = coef_info  # 체중감소에 도움이 되는 요소들
        negative = []  # 체중증가 요소들은 제외
        ai_insight = {
            'positive': positive,
            'negative': negative,
        }
        # 템플릿용 리스트 가공
        ai_insight_labels_positive = [c['label'] for c in positive]
        ai_insight_labels_negative = [c['label'] for c in negative]
        ai_insight_data_positive = [c['coef'] for c in positive]
        ai_insight_data_negative = [c['coef'] for c in negative]
        # 모델 신뢰도 텍스트
        model_confidence = get_model_confidence_text(best_r2)
    else:
        insight_message = "아직 고객님의 웰니스 패턴을 분석하기 위한 데이터가 부족합니다. 매일 꾸준히 기록하시면 더욱 정확한 인사이트를 드릴 수 있어요!"
        ai_insight_labels_positive = []
        ai_insight_labels_negative = []
        ai_insight_data_positive = []
        ai_insight_data_negative = []
    weight_data_dates = [c['date'] for c in weight_data]
    weight_data_weights = [c['weight'] for c in weight_data]
    wellness_data_scores = {k: [v['score'] for v in wellness_data[k]] for k in question_keys}
    # 데이터가 없는 질문은 빈 리스트로 처리
    for k in question_keys:
        if not wellness_data_scores[k]:
            wellness_data_scores[k] = []
    # JS용 데이터셋 가공
    wellness_chart_datasets = [
        {
            'label': q.question_text,
            'data': wellness_data_scores[q.question_key],
        }
        for q in questions
    ]
    # ai_insight가 있을 때만 coef를 매핑
    coef_map = {}
    pvalue_map = {}
    if ai_insight and p_values is not None:
        # 실제로 회귀분석에 사용된 변수들만 매핑
        for i, k in enumerate(valid_question_keys):
            original_idx = question_keys.index(k) if k in question_keys else None
            coef_map[k] = best_coefs[i]
            pvalue_map[k] = p_values[original_idx] if original_idx is not None else None
    
    def get_circle_color(coef, pvalue):
        if coef is None or pvalue is None or pvalue >= 0.2 or coef > 0:
            # p값이 유의하지 않거나 양수 계수(체중증가 요소)는 회색으로 처리
            return "#cccccc"
        else:
            # 음수 계수(체중감소에 도움이 되는 요소)만 초록색으로 표시
            return "#28a745"
    wellness_questions_chart_data = [
        {
            'question_key': q.question_key,
            'question_text': q.question_text,
            'scores': wellness_data_scores[q.question_key],
            'scores_smooth': moving_average(wellness_data_scores[q.question_key], window=5),
            'weights': moving_average(weight_data_weights, window=5),
            'badge': badge_labels.get(q.question_key, q.question_key.upper()),
            'coef': coef_map.get(q.question_key),
            'pvalue': pvalue_map.get(q.question_key),
            'circle_color': get_circle_color(coef_map.get(q.question_key), pvalue_map.get(q.question_key)),
        }
        for q in questions
    ]
    # 행동 인과 분석 (Granger causality)
    causal_message = None
    causal_links_list = []
    causal_edges_vis = []
    try:
        if checkins.count() >= len(question_keys) + 2:
            df_causal = pd.DataFrame([
                {**c.responses} for c in checkins
            ])
            max_lag = 3
            causal_links = []
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                for a in df_causal.columns:
                    for b in df_causal.columns:
                        if a == b:
                            continue
                        test_data = df_causal[[b, a]].dropna()
                        if len(test_data) > max_lag + 2:
                            try:
                                granger_result = grangercausalitytests(test_data, maxlag=max_lag)
                                pvals = [granger_result[lag][0]['ssr_ftest'][1] for lag in range(1, max_lag+1)]
                                min_p = min(pvals)
                                if min_p < 0.05:
                                    causal_links.append((a, b, min_p))
                            except Exception as e:
                                continue
            finally:
                sys.stdout = old_stdout
            for a, b, p in sorted(causal_links, key=lambda x: x[2]):
                a_label = badge_labels.get(a, a.upper())
                b_label = badge_labels.get(b, b.upper())
                causal_links_list.append({'from': a_label, 'to': b_label, 'p': p})
                causal_edges_vis.append({
                    'from': a,
                    'to': b,
                    'arrows': 'to',
                    'color': { 'color': '#1976d2' },
                    'width': 1,
                })
            # 인과관계(엣지)가 없으면 question_keys 전체를 노드로 사용
            if not causal_edges_vis:
                causal_nodes_set = set(question_keys)
            else:
                causal_nodes_set = set()
                for edge in causal_edges_vis:
                    causal_nodes_set.add(edge['from'])
                    causal_nodes_set.add(edge['to'])

            result = {'causal_links_list': causal_links_list, 'causal_edges_vis': causal_edges_vis, 'causal_nodes_vis': []}
            result['causal_nodes_vis'] = [
                {
                    'id': k,
                    'label': badge_labels.get(k, k.upper()),
                    'shape': 'dot',
                    'size': 10,
                    'color': {'background': get_circle_color(coef_map.get(k), pvalue_map.get(k)), 'border': '#1976d2'},
                    'font': {'size': 14}
                }
                for k in causal_nodes_set
            ]
            if not causal_links_list:
                causal_message = "뚜렷한 인과 경로가 발견되지 않았습니다."
            else:
                causal_message = None
    except ImportError:
        causal_message = "statsmodels 패키지가 설치되어야 인과 분석이 가능합니다."
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
        'period': 28, # 기간 필터링 제거
        'today': today,
        'no_data': False,
        'model_confidence': model_confidence,
        'best_lag': best_lag,
        'best_adj_r2': best_score,
        'causal_message': causal_message,
        'causal_links_list': causal_links_list,
        'coef_map': coef_map,
        'pvalue_map': pvalue_map,
    })

def moving_average(arr, window=5):
    # None 값을 NaN으로 변환하여 pandas가 올바르게 처리하도록 함
    processed_arr = [None if x is None else x for x in arr]
    s = pd.Series(processed_arr, dtype=float)
    result = s.rolling(window=window, min_periods=1, center=True).mean().tolist()
    # NaN을 None으로 변환하여 JSON 직렬화 시 null로 처리되도록 함
    return [None if pd.isna(x) else x for x in result]

def convert_coefficient_to_action_language(coef, badge_label):
    """회귀계수를 행동 언어로 변환 (체중감소에 도움이 되는 요소만)"""
    abs_coef = abs(coef)
    weight_change = abs_coef * 1000  # kg을 g로 변환
    
    # 음수 계수만 처리 (체중감소에 도움이 되는 요소)
    return f"{badge_label}을(를) 한 단계 더 좋게 하면 체중이 {weight_change:.0f}g 줄어들 가능성이 있어요"

def get_model_confidence_text(r2_score):
    """R² 점수를 신뢰도 텍스트로 변환"""
    if r2_score >= 0.8:
        return "매우 높은 신뢰도 (약 80% 이상의 정확도)"
    elif r2_score >= 0.6:
        return "높은 신뢰도 (약 60% 이상의 정확도)"
    elif r2_score >= 0.4:
        return "보통 신뢰도 (약 40% 이상의 정확도)"
    elif r2_score >= 0.2:
        return "낮은 신뢰도 (약 20% 이상의 정확도)"
    else:
        return "매우 낮은 신뢰도 (패턴이 불분명함)"

@csrf_exempt
def causal_analysis_api(request):
    warnings.filterwarnings("ignore", category=FutureWarning)
    from statsmodels.tsa.stattools import grangercausalitytests
    user = request.user
    from django.utils import timezone
    from .models import SurveyQuestion, DailyCheckIn
    import pandas as pd
    import numpy as np
    import statsmodels.api as sm
    questions = SurveyQuestion.objects.filter(is_active=True).order_by('order')
    question_keys = [q.question_key for q in questions]
    badge_labels = {q.question_key: (q.badge_label or q.question_key.upper()) for q in questions}
    today = timezone.localdate()
    checkins = DailyCheckIn.objects.filter(user=user).order_by('date')
    result = {'causal_links_list': [], 'causal_nodes_vis': [], 'causal_edges_vis': []}
    
    if request.method == "POST":
        data = json.loads(request.body)
        coef_map = data.get("coef_map", {})
        pvalue_map = data.get("pvalue_map", {})
        if isinstance(coef_map, str):
            coef_map = json.loads(coef_map) if coef_map.strip() else {}
        if isinstance(pvalue_map, str):
            pvalue_map = json.loads(pvalue_map) if pvalue_map.strip() else {}
        
        # 회귀분석과 동일한 데이터 전처리 적용
        df, valid_question_keys = prepare_regression_data(checkins, question_keys)
        
        if df is not None and len(df) >= len(valid_question_keys) + 2:
            # 유효한 변수만으로 인과분석 수행
            df_causal = df[valid_question_keys]
            max_lag = 4
            causal_links = []
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                for a in df_causal.columns:
                    for b in df_causal.columns:
                        if a == b:
                            continue
                        test_data = df_causal[[b, a]].dropna()
                        if len(test_data) > max_lag + 2:
                            try:
                                granger_result = grangercausalitytests(test_data, maxlag=max_lag)
                                pvals = [granger_result[lag][0]['ssr_ftest'][1] for lag in range(1, max_lag+1)]
                                min_p = min(pvals)
                                if min_p < 0.1:
                                    causal_links.append((a, b, min_p))
                            except Exception as e:
                                continue
            finally:
                sys.stdout = old_stdout
            causal_links_list = []
            causal_edges_vis = []
            for a, b, p in sorted(causal_links, key=lambda x: x[2]):
                a_label = badge_labels.get(a, a.upper())
                b_label = badge_labels.get(b, b.upper())
                causal_links_list.append({'from': a_label, 'to': b_label, 'p': p})
                causal_edges_vis.append({
                    'from': a,
                    'to': b,
                    'arrows': 'to',
                    'color': { 'color': '#1976d2' },
                    'width': 1,
                })
            if not causal_edges_vis:
                causal_nodes_set = set(valid_question_keys)
            else:
                causal_nodes_set = set()
                for edge in causal_edges_vis:
                    causal_nodes_set.add(edge['from'])
                    causal_nodes_set.add(edge['to'])
            def get_circle_color(coef, pvalue):
                if coef is None or pvalue is None or pvalue >= 0.2 or coef > 0:
                    # p값이 유의하지 않거나 양수 계수(체중증가 요소)는 회색으로 처리
                    return "#cccccc"
                else:
                    # 음수 계수(체중감소에 도움이 되는 요소)만 초록색으로 표시
                    return "#28a745"
            result['causal_nodes_vis'] = []
            for k in causal_nodes_set:
                coef = coef_map.get(k)
                pvalue = pvalue_map.get(k)
                result['causal_nodes_vis'].append({
                    'id': k,
                    'label': badge_labels.get(k, k.upper()),
                    'shape': 'dot',
                    'size': 10,
                    'color': {'background': get_circle_color(coef, pvalue), 'border': '#1976d2'},
                    'font': {'size': 14}
                })
            result['causal_links_list'] = causal_links_list
            result['causal_edges_vis'] = causal_edges_vis
    return JsonResponse(result)

def prepare_regression_data(checkins, question_keys):
    """회귀분석을 위한 데이터 전처리 공통 함수"""
    df = pd.DataFrame([
        {'date': c.date, 'weight': c.morning_fasting_weight, **c.responses} for c in checkins
    ])
    
    # 체중 데이터가 없는 행만 제거
    df = df.dropna(subset=['weight'])
    
    # 독립변수 결측값 처리: 충분한 데이터가 있는 변수만 포함
    min_data_threshold = max(7, len(df) // 3)  # 최소 7개 또는 전체의 1/3 이상
    valid_question_keys = []
    
    for key in question_keys:
        if key in df.columns:
            # 해당 변수의 유효한 데이터 개수 확인
            valid_count = df[key].notna().sum()
            if valid_count >= min_data_threshold:
                valid_question_keys.append(key)
    
    # 유효한 변수가 없으면 분석 불가
    if not valid_question_keys:
        return None, []
    
    # 유효한 변수만으로 데이터 필터링 (완전한 케이스만 사용)
    df = df.dropna(subset=['weight'] + valid_question_keys)
    
    return df, valid_question_keys

def perform_regression_analysis(checkins, question_keys):
    """회귀분석을 수행하고 결과를 반환하는 공통 함수"""
    # 최소 데이터 요구사항: 자유도가 최소 1 이상이 되도록
    min_required_data = len(question_keys) + 2  # 변수 수 + 2 (자유도 1 이상)
    if len(checkins) < min_required_data:
        return None, None, None, None, None, None, []
    
    max_lag = 7
    best_score = -np.inf
    best_model = None
    best_coefs = None
    best_lag = 1
    best_r2 = None
    best_adj_r2 = None
    best_valid_keys = []
    
    for lag in range(1, max_lag + 1):
        if len(checkins) <= lag or len(checkins) - lag < 5:
            continue
        
        # 공통 데이터 전처리 함수 사용
        df, valid_question_keys = prepare_regression_data(checkins, question_keys)
        
        if df is None or len(df) <= lag:
            continue
        
        X = df[valid_question_keys][:-lag].to_numpy()
        y = df['weight'][lag:].to_numpy()
        
        # 자유도 검증: 최소 자유도 1 이상 보장
        if len(y) <= len(valid_question_keys) + 1:
            continue  # 자유도가 0 이하인 경우 건너뛰기
        
        # 추가적인 NaN 값 검사
        if np.any(np.isnan(X)) or np.any(np.isnan(y)):
            continue
        
        model = LinearRegression()
        model.fit(X, y)
        y_pred = model.predict(X)
        r2 = r2_score(y, y_pred)
        k = X.shape[1]
        n = len(y)
        adj_r2 = 1 - (1 - r2) * (n - 1) / (n - k - 1) if n - k - 1 > 0 else r2
        if adj_r2 > best_score:
            best_score = adj_r2
            best_lag = lag
            best_model = model
            best_coefs = model.coef_
            best_r2 = r2
            best_adj_r2 = adj_r2
            best_valid_keys = valid_question_keys
    
    if best_model is not None:
        # p값 계산 - 이미 찾은 best_valid_keys 사용
        df, _ = prepare_regression_data(checkins, question_keys)
        
        if df is None or len(df) <= best_lag:
            # 데이터가 부족한 경우 p값을 None으로 설정
            p_values = np.array([None] * len(question_keys))
            return best_model, best_coefs, p_values, best_lag, best_r2, best_adj_r2, best_valid_keys
        
        X = df[best_valid_keys][:-best_lag].to_numpy()
        y = df['weight'][best_lag:].to_numpy()
        
        # 추가적인 NaN 값 검사
        if np.any(np.isnan(X)) or np.any(np.isnan(y)):
            p_values = np.array([None] * len(question_keys))
            return best_model, best_coefs, p_values, best_lag, best_r2, best_adj_r2, best_valid_keys
        
        y_pred = best_model.predict(X)
        residuals = y - y_pred
        # 자유도 계산
        degrees_of_freedom = len(y) - len(best_valid_keys) - 1
        if degrees_of_freedom <= 0:
            # 자유도가 0 이하인 경우 p값을 None으로 설정
            p_values = np.array([None] * len(question_keys))
            return best_model, best_coefs, p_values, best_lag, best_r2, best_adj_r2, best_valid_keys
        
        mse = np.sum(residuals**2) / degrees_of_freedom
        # MSE가 0인 경우 처리
        if mse <= 0:
            p_values = np.array([None] * len(question_keys))
            return best_model, best_coefs, p_values, best_lag, best_r2, best_adj_r2, best_valid_keys
        
        # 더 안전한 방법으로 표준오차 계산
        try:
            XTX = np.dot(X.T, X)
            # 행렬이 특이행렬인지 확인
            if np.linalg.det(XTX) == 0:
                # 특이행렬인 경우 p값을 None으로 설정
                p_values = np.array([None] * len(question_keys))
            else:
                var_b = mse * np.linalg.inv(XTX).diagonal()
                # 음수 분산 및 NaN 방지
                var_b = np.where((var_b <= 0) | np.isnan(var_b), np.inf, var_b)
                # 안전한 제곱근 계산
                try:
                    sd_b = np.sqrt(var_b)
                except (RuntimeWarning, ValueError):
                    # sqrt 오류 시 inf로 처리
                    sd_b = np.where(np.isnan(var_b) | (var_b <= 0), np.inf, np.sqrt(np.abs(var_b)))
                # 0으로 나누기 방지
                sd_b = np.where(sd_b == 0, np.inf, sd_b)
                t_b = best_coefs / sd_b
                # inf 값 처리
                t_b = np.where(np.isinf(t_b), 0, t_b)
                
                # NaN 값 방지를 위한 추가 검증
                try:
                    p_values_raw = 2 * (1 - stats.t.cdf(abs(t_b), degrees_of_freedom))
                    # NaN 값 처리
                    p_values_raw = np.where(np.isnan(p_values_raw), None, p_values_raw)
                    
                    # 원래 question_keys 순서대로 p값 배열 재구성
                    p_values = np.array([None] * len(question_keys))
                    for i, k in enumerate(best_valid_keys):
                        if k in question_keys:
                            original_idx = question_keys.index(k)
                            p_values[original_idx] = p_values_raw[i]
                except (ValueError, RuntimeWarning):
                    # 통계 계산 오류 시 p값을 None으로 설정
                    p_values = np.array([None] * len(question_keys))
        except (np.linalg.LinAlgError, ValueError):
            # 선형대수 오류가 발생하면 p값을 None으로 설정
            p_values = np.array([None] * len(question_keys))
        
        return best_model, best_coefs, p_values, best_lag, best_r2, best_adj_r2, best_valid_keys
    
    return None, None, None, None, None, None, []
