
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from scipy import stats
from statsmodels.tsa.stattools import grangercausalitytests
import sys
import io
import warnings
from .models import DailyCheckIn, SurveyQuestion

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

def get_dashboard_data(user):
    today = timezone.localdate()
    checkins = DailyCheckIn.objects.filter(user=user).order_by('date')

    if not checkins.exists():
        return {'no_data': True, 'today': today}

    questions = SurveyQuestion.objects.filter(is_active=True).order_by('order')
    question_keys = [q.question_key for q in questions]
    question_texts = {q.question_key: q.question_text for q in questions}
    badge_labels = {q.question_key: (q.badge_label or q.question_key.upper()) for q in questions}

    weight_data = [{'date': c.date.strftime('%Y-%m-%d'), 'weight': c.morning_fasting_weight} for c in checkins]
    
    wellness_data = {k: [] for k in question_keys}
    for c in checkins:
        for k in question_keys:
            val = c.responses.get(k)
            if val is None:
                wellness_data[k].append({'date': c.date.strftime('%Y-%m-%d'), 'score': None})
            else:
                wellness_data[k].append({'date': c.date.strftime('%Y-%m-%d'), 'score': val})

    best_model, best_coefs, p_values, best_lag, best_r2, best_adj_r2, valid_question_keys = perform_regression_analysis(checkins, question_keys)

    ai_insight = None
    insight_message = None
    model_confidence = None
    coef_map = {}
    pvalue_map = {}

    if best_model is not None:
        coefs = best_coefs
        coef_info = []
        for i, k in enumerate(valid_question_keys):
            original_idx = question_keys.index(k) if k in question_keys else None
            coef_info.append({
                'key': k,
                'text': question_texts[k],
                'coef': coefs[i],
                'pvalue': p_values[original_idx] if original_idx is not None else None,
                'badge': badge_labels.get(k, k.upper()),
                'label': badge_labels.get(k, k.upper()),
                'action_text': convert_coefficient_to_action_language(coefs[i], badge_labels.get(k, k.upper())),
            })
        
        coef_info = [c for c in coef_info if c['pvalue'] is not None and c['pvalue'] < 0.2 and c['coef'] < 0]
        coef_info = sorted(coef_info, key=lambda x: abs(x['coef']), reverse=True)
        
        positive = coef_info
        negative = []
        
        ai_insight = {'positive': positive, 'negative': negative}
        model_confidence = get_model_confidence_text(best_r2)

        for i, k in enumerate(valid_question_keys):
            original_idx = question_keys.index(k) if k in question_keys else None
            coef_map[k] = best_coefs[i]
            pvalue_map[k] = p_values[original_idx] if original_idx is not None else None
    else:
        insight_message = "아직 고객님의 웰니스 패턴을 분석하기 위한 데이터가 부족합니다. 매일 꾸준히 기록하시면 더욱 정확한 인사이트를 드릴 수 있어요!"

    weight_data_dates = [c['date'] for c in weight_data]
    weight_data_weights = [c['weight'] for c in weight_data]
    wellness_data_scores = {k: [v['score'] for v in wellness_data[k]] for k in question_keys}

    for k in question_keys:
        if not wellness_data_scores[k]:
            wellness_data_scores[k] = []

    def get_circle_color(coef, pvalue):
        if coef is None or pvalue is None or pvalue >= 0.2 or coef > 0:
            return "#cccccc"
        else:
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

    return {
        'weight_data': weight_data,
        'weight_data_dates': weight_data_dates,
        'weight_data_weights': weight_data_weights,
        'wellness_data': wellness_data,
        'wellness_data_scores': wellness_data_scores,
        'wellness_questions_chart_data': wellness_questions_chart_data,
        'questions': questions,
        'ai_insight': ai_insight,
        'insight_message': insight_message,
        'today': today,
        'no_data': False,
        'model_confidence': model_confidence,
        'best_lag': best_lag,
        'best_adj_r2': best_score,
        'coef_map': coef_map,
        'pvalue_map': pvalue_map,
    }

def perform_causal_analysis(checkins, question_keys, coef_map, pvalue_map):
    warnings.filterwarnings("ignore", category=FutureWarning)
    badge_labels = {q.question_key: (q.badge_label or q.question_key.upper()) for q in SurveyQuestion.objects.filter(is_active=True)}
    result = {'causal_links_list': [], 'causal_nodes_vis': [], 'causal_edges_vis': []}
    
    df, valid_question_keys = prepare_regression_data(checkins, question_keys)
    
    if df is not None and len(df) >= len(valid_question_keys) + 2:
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
                return "#cccccc"
            else:
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
        
    return result
