
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import grangercausalitytests
import sys
import io
import warnings
from .models import DailyCheckIn, SurveyQuestion
from django.utils import timezone

# --- Analysis Configuration ---
MIN_VALID_DATA_THRESHOLD = 7
VALID_DATA_RATIO_THRESHOLD = 3  # 데이터의 1/3
REGRESSION_MAX_LAG = 7
CAUSAL_ANALYSIS_MAX_LAG = 4
CAUSAL_ANALYSIS_P_VALUE_THRESHOLD = 0.1
INSIGHT_P_VALUE_THRESHOLD = 0.2
MOVING_AVERAGE_WINDOW = 5
# --- End of Analysis Configuration ---

def prepare_regression_data(checkins, question_keys):
    """회귀분석을 위한 데이터 전처리 공통 함수"""
    df = pd.DataFrame([
        {'date': c.date, 'weight': c.morning_fasting_weight, **c.responses} for c in checkins
    ])
    
    # 체중 데이터가 없는 행만 제거
    df = df.dropna(subset=['weight'])
    
    # 독립변수 결측값 처리: 충분한 데이터가 있는 변수만 포함
    min_data_threshold = MIN_VALID_DATA_THRESHOLD
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
    df, valid_question_keys = prepare_regression_data(checkins, question_keys)
    
    min_required_data = len(valid_question_keys) + 2
    if df is None or len(df) < min_required_data:
        return None, None, None, None, None, None, []

    best_adj_r2 = -np.inf
    best_result = None
    best_lag = 0

    for lag in range(1, REGRESSION_MAX_LAG + 1):
        if len(df) <= lag:
            continue

        X = df[valid_question_keys].shift(lag).dropna()
        y = df['weight'][X.index]

        if len(X) < min_required_data:
            continue
            
        X = sm.add_constant(X)
        model = sm.OLS(y, X)
        results = model.fit()
        
        if results.rsquared_adj > best_adj_r2:
            best_adj_r2 = results.rsquared_adj
            best_result = results
            best_lag = lag

    if best_result:
        p_values_series = best_result.pvalues.drop('const', errors='ignore')
        p_values = np.array([p_values_series.get(k, None) for k in question_keys])
        
        coefs_series = best_result.params.drop('const', errors='ignore')
        coefs = np.array([coefs_series.get(k, None) for k in valid_question_keys])

        return (best_result, coefs, p_values, best_lag, 
                best_result.rsquared, best_result.rsquared_adj, valid_question_keys)

    return None, None, None, None, None, None, []

def moving_average(arr, window=MOVING_AVERAGE_WINDOW):
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
    question_texts = {q.question_key: q.question_text for q in questions}
    badge_labels = {q.question_key: (q.badge_label or q.question_key.upper()) for q in questions}

    # Group questions by category
    questions_by_category = {}
    for q in questions:
        if q.category_main not in questions_by_category:
            questions_by_category[q.category_main] = []
        questions_by_category[q.category_main].append(q)

    # Perform analysis for each category
    category_analysis_results = {}
    overall_coef_map = {}
    overall_pvalue_map = {}

    for category, category_questions in questions_by_category.items():
        category_question_keys = [q.question_key for q in category_questions]
        
        best_model, best_coefs, p_values, best_lag, best_r2, best_adj_r2, valid_question_keys = perform_regression_analysis(checkins, category_question_keys)

        ai_insight = None
        insight_message = None
        model_confidence = None
        
        if best_model is not None:
            coef_info = []
            for i, k in enumerate(valid_question_keys):
                original_idx = category_question_keys.index(k)
                coef = best_coefs[i]
                pvalue = p_values[original_idx]
                overall_coef_map[k] = coef
                overall_pvalue_map[k] = pvalue
                
                coef_info.append({
                    'key': k,
                    'text': question_texts[k],
                    'coef': coef,
                    'pvalue': pvalue,
                    'badge': badge_labels.get(k, k.upper()),
                    'action_text': convert_coefficient_to_action_language(coef, badge_labels.get(k, k.upper())),
                })
            
            coef_info = [c for c in coef_info if c['pvalue'] is not None and c['pvalue'] < INSIGHT_P_VALUE_THRESHOLD and c['coef'] < 0]
            coef_info = sorted(coef_info, key=lambda x: abs(x['coef']), reverse=True)
            
            ai_insight = {'positive': coef_info, 'negative': []}
            model_confidence = get_model_confidence_text(best_r2)
        else:
            insight_message = "아직 이 카테고리의 패턴을 분석하기 위한 데이터가 부족합니다."

        category_analysis_results[category] = {
            'ai_insight': ai_insight,
            'insight_message': insight_message,
            'model_confidence': model_confidence,
            'best_lag': best_lag,
            'best_adj_r2': best_adj_r2,
        }

    # Prepare data for charts
    weight_data = [{'date': c.date.strftime('%Y-%m-%d'), 'weight': c.morning_fasting_weight} for c in checkins]
    weight_data_dates = [c['date'] for c in weight_data]
    weight_data_weights = [c['weight'] for c in weight_data]
    
    wellness_data = {q.question_key: [] for q in questions}
    for c in checkins:
        for q in questions:
            val = c.responses.get(q.question_key)
            wellness_data[q.question_key].append({'date': c.date.strftime('%Y-%m-%d'), 'score': val})

    wellness_data_scores = {k: [v['score'] for v in wellness_data[k]] for k in wellness_data}

    def get_circle_color(coef, pvalue):
        if coef is None or pvalue is None or pvalue >= INSIGHT_P_VALUE_THRESHOLD or coef > 0:
            return "#cccccc"
        else:
            return "#28a745"

    wellness_questions_chart_data = [
        {
            'question_key': q.question_key,
            'question_text': q.question_text,
            'scores': wellness_data_scores[q.question_key],
            'scores_smooth': moving_average(wellness_data_scores[q.question_key]),
            'weights': moving_average(weight_data_weights),
            'badge': badge_labels.get(q.question_key, q.question_key.upper()),
            'coef': overall_coef_map.get(q.question_key),
            'pvalue': overall_pvalue_map.get(q.question_key),
            'circle_color': get_circle_color(overall_coef_map.get(q.question_key), overall_pvalue_map.get(q.question_key)),
        }
        for q in questions
    ]

    return {
        'weight_data': weight_data,
        'weight_data_dates': weight_data_dates,
        'weight_data_weights': weight_data_weights,
        'wellness_data_scores': wellness_data_scores,
        'wellness_questions_chart_data': wellness_questions_chart_data,
        'questions': questions,
        'category_analysis_results': category_analysis_results,
        'today': today,
        'no_data': False,
        'coef_map': overall_coef_map,
        'pvalue_map': overall_pvalue_map,
    }

def perform_causal_analysis(checkins, question_keys, coef_map, pvalue_map):
    warnings.filterwarnings("ignore", category=FutureWarning)
    badge_labels = {q.question_key: (q.badge_label or q.question_key.upper()) for q in SurveyQuestion.objects.filter(is_active=True)}
    result = {'causal_links_list': [], 'causal_nodes_vis': [], 'causal_edges_vis': [], 'debug_logs': []}
    debug_logs = result['debug_logs']

    df, valid_question_keys = prepare_regression_data(checkins, question_keys)
    debug_logs.append(f"Initial data prepared. DataFrame size: {len(df) if df is not None else 0} rows.")
    debug_logs.append(f"Valid question keys for analysis: {valid_question_keys}")

    if df is None or len(df) < len(valid_question_keys) + 2:
        debug_logs.append("Analysis stopped: Not enough data for causal analysis after preparation.")
        if df is None:
            debug_logs.append("Reason: DataFrame is None.")
        else:
            debug_logs.append(f"Reason: DataFrame has {len(df)} rows, but at least {len(valid_question_keys) + 2} are required.")
        return result

    df_causal = df[valid_question_keys]
    causal_links = []
    debug_logs.append(f"Starting Granger causality tests for {len(df_causal.columns)} variables.")
    
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        for a in df_causal.columns:
            for b in df_causal.columns:
                if a == b:
                    continue
                
                test_data = df_causal[[b, a]].dropna()
                debug_logs.append(f"Testing causality from '{a}' to '{b}'. Number of paired data points: {len(test_data)}.")

                if len(test_data) <= CAUSAL_ANALYSIS_MAX_LAG + 2:
                    debug_logs.append(f"--> Skipped: Not enough data. Required > {CAUSAL_ANALYSIS_MAX_LAG + 2}.")
                    continue
                
                try:
                    granger_result = grangercausalitytests(test_data, maxlag=CAUSAL_ANALYSIS_MAX_LAG, verbose=False)
                    pvals = [granger_result[lag][0]['ssr_ftest'][1] for lag in range(1, CAUSAL_ANALYSIS_MAX_LAG + 1)]
                    min_p = min(pvals)
                    debug_logs.append(f"--> Granger test successful. Min p-value: {min_p:.4f}")
                    if min_p < CAUSAL_ANALYSIS_P_VALUE_THRESHOLD:
                        causal_links.append((a, b, min_p))
                        debug_logs.append(f"    **** Found significant causal link! ****")
                except Exception as e:
                    debug_logs.append(f"--> Granger test failed with error: {e}")
                    continue
    finally:
        sys.stdout = old_stdout
        
    debug_logs.append(f"Causality tests finished. Found {len(causal_links)} significant links.")

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
        debug_logs.append("No causal edges found. Displaying all valid question keys as nodes.")
    else:
        causal_nodes_set = set()
        for edge in causal_edges_vis:
            causal_nodes_set.add(edge['from'])
            causal_nodes_set.add(edge['to'])
        debug_logs.append(f"Found causal edges. Displaying {len(causal_nodes_set)} nodes involved in links.")
            
    def get_circle_color(coef, pvalue):
        if coef is None or pvalue is None or pvalue >= INSIGHT_P_VALUE_THRESHOLD or coef > 0:
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
