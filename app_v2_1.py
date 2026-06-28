"""
app_v2_1.py - 이커머스 리뷰 모니터링 대시보드 + AI 챗봇
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import os
import anthropic
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

st.set_page_config(page_title="리뷰 모니터링 대시보드", page_icon="📊", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }
    .section-title { font-size: 15px; font-weight: 700; color: #1A1A1A; margin-bottom: 12px; }
    .review-card { background: white; border-radius: 10px; padding: 14px 16px; margin-bottom: 10px; border: 1px solid #EAEAEA; border-left: 3px solid #E24B4A; }
    .review-card-pos { background: white; border-radius: 10px; padding: 14px 16px; margin-bottom: 10px; border: 1px solid #EAEAEA; border-left: 3px solid #1D9E75; }
    .review-card-all { background: white; border-radius: 10px; padding: 14px 16px; margin-bottom: 10px; border: 1px solid #EAEAEA; border-left: 3px solid #378ADD; }
    .review-text { font-size: 14px; color: #333; line-height: 1.6; }
    .review-meta { font-size: 12px; color: #AAA; margin-top: 6px; }
    .tag-neg { display: inline-block; background: #FFF0F0; color: #E24B4A; font-size: 11px; padding: 2px 8px; border-radius: 4px; margin-right: 4px; }
    .tag-pos { display: inline-block; background: #F0FFF8; color: #1D9E75; font-size: 11px; padding: 2px 8px; border-radius: 4px; margin-right: 4px; }
    .tag-all { display: inline-block; background: #F0F6FF; color: #378ADD; font-size: 11px; padding: 2px 8px; border-radius: 4px; margin-right: 4px; }
    div[data-testid="stMetric"] { background: white; border-radius: 12px; padding: 16px; border: 1px solid #EAEAEA; }
    div[data-testid="stMetricValue"] { font-size: 20px !important; }
    .report-section { background: white; border-radius: 12px; padding: 18px 20px; border: 1px solid #EAEAEA; margin-bottom: 12px; }
    .report-section-title { font-size: 13px; font-weight: 700; color: #555; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }
    .report-rec { background: #F0F6FF; border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; font-size: 14px; color: #333; border-left: 3px solid #378ADD; }
    /* 사이드바 다크 스타일 */
    [data-testid="stSidebar"] { background-color: #1E2130 !important; }
    [data-testid="stSidebar"] * { color: #CDD3E0 !important; }
    [data-testid="stSidebar"] h2 { color: white !important; font-size: 20px !important; font-weight: 700 !important; }
    [data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"] { display: none !important; }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] { display: flex !important; flex-direction: column !important; gap: 4px !important; }
    [data-testid="stSidebar"] .stRadio label { font-size: 22px !important; font-weight: 700 !important; color: white !important; padding: 12px 16px !important; border-radius: 8px !important; cursor: pointer !important; display: flex !important; align-items: center !important; }
    [data-testid="stSidebar"] .stRadio label:hover { background-color: #2D3348 !important; }
    [data-testid="stSidebar"] .stRadio input[type="radio"] { display: none !important; }
    [data-testid="stSidebar"] hr { border-color: #2D3348 !important; }
</style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

@st.cache_data(ttl=60)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT r.id, r.rating, r.review, r.sentiment, r.review_date,
               a.aspects, a.issues, a.summary
        FROM reviews r
        LEFT JOIN analysis_results a ON r.id = a.review_id
        WHERE r.is_analyzed = 1
    """, conn)
    conn.close()
    df["review_date"] = pd.to_datetime(df["review_date"])
    def parse_aspects(x):
        try:
            return json.loads(x) if x else []
        except:
            return []
    df["aspects_list"] = df["aspects"].apply(parse_aspects)
    return df

def render_reviews(drill_df, card_class, tag_class, page_key):
    per_page = 5
    total_pages = max(1, (len(drill_df) - 1) // per_page + 1)
    if f"{page_key}_page" not in st.session_state:
        st.session_state[f"{page_key}_page"] = 0
    page = st.session_state[f"{page_key}_page"]
    page_df = drill_df.iloc[page * per_page:(page + 1) * per_page]
    st.markdown(f"<p style='font-size:13px; color:#888;'>총 {len(drill_df):,}건 | {page+1}/{total_pages} 페이지</p>", unsafe_allow_html=True)
    for _, row in page_df.iterrows():
        aspects = row.get("aspects_list", [])
        if not isinstance(aspects, list): aspects = []
        tags_html = "".join([f"<span class='{tag_class}'>{a}</span>" for a in aspects[:3]])
        st.markdown(f"""
        <div class='{card_class}'>
            <div class='review-text'>{row['review']}</div>
            <div class='review-meta'>{row['review_date'].strftime('%Y-%m-%d')} · 별점 {row['rating']}점 &nbsp;{tags_html}</div>
        </div>
        """, unsafe_allow_html=True)
    if total_pages > 1:
        c1, _, c2 = st.columns([1, 4, 1])
        with c1:
            if st.button("◀ 이전", key=f"{page_key}_prev", disabled=(page == 0)):
                st.session_state[f"{page_key}_page"] -= 1
                st.rerun()
        with c2:
            if st.button("다음 ▶", key=f"{page_key}_next", disabled=(page >= total_pages - 1)):
                st.session_state[f"{page_key}_page"] += 1
                st.rerun()

df = load_data()

# 세션 상태 초기화
for key, val in [("chat_messages", []), ("last_aspects", []), ("last_sentiment", None), ("report_data", None), ("_last_chat_input", "")]:
    if key not in st.session_state:
        st.session_state[key] = val

# 사이드바 네비게이션
with st.sidebar:
    st.markdown("## 📊 리뷰 모니터링")
    page = st.radio(
        "nav",
        ["대시보드", "AI 챗봇"],
        label_visibility="collapsed",
        key="page_nav"
    )
    st.divider()

# ════════════════════════════════════════════════
# 대시보드
# ════════════════════════════════════════════════
if page == "대시보드":
    st.markdown("## 📊 이커머스 리뷰 모니터링 대시보드")
    st.markdown(f"<p style='color:#AAA; font-size:13px;'>마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>", unsafe_allow_html=True)
    st.divider()

    total = len(df)
    neg_count = len(df[df["sentiment"] == "부정"])
    neg_ratio = neg_count / total * 100 if total > 0 else 0
    today = datetime.today().date()
    today_count = len(df[df["review_date"].dt.date == today])
    today_neg_count = len(df[(df["review_date"].dt.date == today) & (df["sentiment"] == "부정")])
    aspect_counts = {}
    for al in df[df["sentiment"] == "부정"]["aspects_list"]:
        for a in al: aspect_counts[a] = aspect_counts.get(a, 0) + 1
    top_aspect = max(aspect_counts, key=aspect_counts.get) if aspect_counts else "없음"

    ALERT_THRESHOLD = 60
    if today_neg_count >= ALERT_THRESHOLD:
        st.markdown(f"""
        <div style='background:#FFF0F0; border:1.5px solid #E24B4A; border-radius:10px; padding:14px 20px; margin-bottom:16px; display:flex; align-items:center; gap:12px;'>
            <span style='font-size:22px;'>⚠️</span>
            <div>
                <div style='font-size:15px; font-weight:700; color:#A32D2D;'>오늘 부정 리뷰 {today_neg_count}건 — 기준치({ALERT_THRESHOLD}건) 초과!</div>
                <div style='font-size:13px; color:#C05050; margin-top:3px;'>즉각적인 이슈 확인이 필요합니다.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("전체 분석 건수", f"{total:,}건")
    with col2: st.metric("부정 리뷰 비율", f"{neg_ratio:.1f}%", delta=f"총 {neg_count:,}건", delta_color="off")
    with col3: st.metric("오늘 신규 리뷰", f"{today_count:,}건")
    with col4: st.metric("주요 이슈 속성", top_aspect)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>감성 비율 & 속성별 분석</div>", unsafe_allow_html=True)
    selected_sentiment = st.radio("감성 선택", ["부정", "긍정", "전체"], horizontal=True, label_visibility="collapsed", key="tab1_sentiment")

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown(f"<p style='font-size:13px; color:#888; text-align:center;'>총 {total:,}건 분석</p>", unsafe_allow_html=True)
        sentiment_counts = df["sentiment"].value_counts().reset_index()
        sentiment_counts.columns = ["감성", "건수"]
        color_map = {"긍정": "#1D9E75", "부정": "#E24B4A", "중립": "#B4B2A9"}
        fig_donut = go.Figure(data=[go.Pie(
            labels=sentiment_counts["감성"], values=sentiment_counts["건수"],
            hole=0.55, marker_colors=[color_map.get(s, "#ccc") for s in sentiment_counts["감성"]],
            textinfo="label+value", texttemplate="%{label}<br>%{value:,}건", textposition="outside",
        )])
        fig_donut.update_layout(showlegend=False, height=300, margin=dict(t=40, b=40, l=60, r=60), paper_bgcolor="white", font=dict(family="Noto Sans KR", size=12))
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_right:
        filtered_df_sent = df if selected_sentiment == "전체" else df[df["sentiment"] == selected_sentiment]
        sel_aspect_counts = {}
        for al in filtered_df_sent["aspects_list"]:
            for a in al: sel_aspect_counts[a] = sel_aspect_counts.get(a, 0) + 1
        if sel_aspect_counts:
            aspect_df = pd.DataFrame(list(sel_aspect_counts.items()), columns=["속성", "건수"]).sort_values("건수", ascending=False)
            bar_color = "#E24B4A" if selected_sentiment == "부정" else "#1D9E75" if selected_sentiment == "긍정" else "#378ADD"
            top_aspects = aspect_df.sort_values("건수", ascending=True).tail(7)
            fig_bar = go.Figure(go.Bar(
                x=top_aspects["건수"], y=top_aspects["속성"], orientation="h", marker_color=bar_color,
                text=top_aspects["건수"].apply(lambda x: f"{x:,}"), textposition="outside",
            ))
            fig_bar.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=60), paper_bgcolor="white", plot_bgcolor="white", xaxis_title="", yaxis_title="", font=dict(family="Noto Sans KR"), xaxis=dict(showgrid=False, showticklabels=False))
            st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>날짜별 리뷰 트렌드</div>", unsafe_allow_html=True)
    min_date = df["review_date"].min().date()
    max_date = df["review_date"].max().date()
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date = st.date_input("시작일", value=min_date, min_value=min_date, max_value=max_date, key="tab1_start")
    with col_d2:
        end_date = st.date_input("종료일", value=max_date, min_value=min_date, max_value=max_date, key="tab1_end")

    trend_df = df[(df["review_date"].dt.date >= start_date) & (df["review_date"].dt.date <= end_date)]
    if selected_sentiment != "전체":
        trend_df = trend_df[trend_df["sentiment"] == selected_sentiment]
    daily_trend = trend_df.groupby("review_date").size().reset_index(name="건수").sort_values("review_date")
    trend_color = "#E24B4A" if selected_sentiment == "부정" else "#1D9E75" if selected_sentiment == "긍정" else "#378ADD"
    fill_map = {"#E24B4A": "rgba(226,75,74,0.08)", "#1D9E75": "rgba(29,158,117,0.08)", "#378ADD": "rgba(55,138,221,0.08)"}
    show_text = len(daily_trend) <= 30
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=daily_trend["review_date"], y=daily_trend["건수"],
        mode="lines+markers+text" if show_text else "lines+markers",
        line=dict(color=trend_color, width=2), fill="tozeroy", fillcolor=fill_map[trend_color],
        text=daily_trend["건수"].apply(lambda x: f"{x:,}") if show_text else None,
        textposition="top center", textfont=dict(size=10, color=trend_color),
        marker=dict(size=5, color=trend_color),
    ))
    fig_trend.update_layout(height=260, margin=dict(t=20, b=10, l=10, r=10), paper_bgcolor="white", plot_bgcolor="white", xaxis_title="", yaxis_title="건수", font=dict(family="Noto Sans KR"), xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#F0F0F0"))
    st.plotly_chart(fig_trend, use_container_width=True)
    st.divider()

    st.markdown("<div class='section-title'>리뷰 탐색</div>", unsafe_allow_html=True)
    st.markdown(f"<p style='font-size:13px; color:#888;'>감성: <b>{selected_sentiment}</b> | 기간: {start_date} ~ {end_date}</p>", unsafe_allow_html=True)
    review_df = df if selected_sentiment == "전체" else df[df["sentiment"] == selected_sentiment]
    review_df = review_df[(review_df["review_date"].dt.date >= start_date) & (review_df["review_date"].dt.date <= end_date)].sort_values("review_date", ascending=False)
    card_class = "review-card" if selected_sentiment == "부정" else "review-card-pos" if selected_sentiment == "긍정" else "review-card-all"
    tag_class = "tag-neg" if selected_sentiment == "부정" else "tag-pos" if selected_sentiment == "긍정" else "tag-all"
    if len(review_df) > 0:
        render_reviews(review_df, card_class, tag_class, page_key="main_review")
    else:
        st.info("선택한 조건에 해당하는 리뷰가 없습니다.")
    st.divider()

    st.markdown("<div class='section-title'>📝 주간 리포트 자동 생성</div>", unsafe_allow_html=True)
    st.markdown("<p style='color:#888; font-size:13px;'>Claude Sonnet이 이번 주 리뷰 데이터를 분석해 인사이트 리포트를 작성합니다.</p>", unsafe_allow_html=True)
    report_placeholder = st.empty()

    if st.button("리포트 생성", type="primary", key="report_btn"):
        report_placeholder.info("⏳ Claude Sonnet이 리포트를 작성 중입니다...")
        try:
            week_ago = datetime.today() - timedelta(days=7)
            week_df = df[df["review_date"] >= week_ago]
            week_neg = week_df[week_df["sentiment"] == "부정"]
            week_pos = week_df[week_df["sentiment"] == "긍정"]
            week_aspects_neg = {}
            for al in week_neg["aspects_list"]:
                for a in al: week_aspects_neg[a] = week_aspects_neg.get(a, 0) + 1
            week_aspects_pos = {}
            for al in week_pos["aspects_list"]:
                for a in al: week_aspects_pos[a] = week_aspects_pos.get(a, 0) + 1
            neg_aspects_text = ", ".join([f"{k}({v}건)" for k, v in sorted(week_aspects_neg.items(), key=lambda x: -x[1])[:5]])
            pos_aspects_text = ", ".join([f"{k}({v}건)" for k, v in sorted(week_aspects_pos.items(), key=lambda x: -x[1])[:3]])
            week_issues = week_neg["issues"].dropna().tolist()[:15]
            issues_text = "\n".join(week_issues) if week_issues else "없음"
            total_week = len(week_df)
            neg_week = len(week_neg)
            pos_week = len(week_pos)
            neg_pct = f"{neg_week/total_week*100:.1f}" if total_week > 0 else "0"
            pos_pct = f"{pos_week/total_week*100:.1f}" if total_week > 0 else "0"
            prompt = f"""이커머스 쇼핑몰 최근 7일간 리뷰 분석:
전체: {total_week}건 | 부정: {neg_week}건({neg_pct}%) | 긍정: {pos_week}건({pos_pct}%)
주요 불만 속성: {neg_aspects_text} | 주요 만족 속성: {pos_aspects_text}
부정 이슈 샘플: {issues_text}
아래 JSON 형식으로만 응답하세요:
{{"summary": "이번 주 현황 요약 2-3문장", "top_issues": ["이슈1", "이슈2", "이슈3"], "aspect_analysis": {{"속성명": "핵심 이슈 한줄"}}, "recommendations": ["권고사항1", "권고사항2", "권고사항3"]}}"""
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            message = client.messages.create(model="claude-sonnet-4-5", max_tokens=800, messages=[{"role": "user", "content": prompt}])
            raw = message.content[0].text.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"): raw = raw[4:]
            st.session_state["report_data"] = json.loads(raw.strip())
            report_placeholder.empty()
        except Exception as e:
            report_placeholder.error(f"리포트 생성 실패: {e}")

    if st.session_state["report_data"] is not None:
        report = st.session_state["report_data"]
        st.markdown(f"""<div class='report-section'><div class='report-section-title'>📋 이번 주 현황</div><div style='font-size:14px; color:#333; line-height:1.7;'>{report['summary']}</div></div>""", unsafe_allow_html=True)
        issues_html = "".join([f"<div style='padding:6px 0; border-bottom:1px solid #F0F0F0; font-size:14px; color:#333;'>• {issue}</div>" for issue in report['top_issues']])
        st.markdown(f"""<div class='report-section'><div class='report-section-title'>⚠️ 주요 고객 불만</div>{issues_html}</div>""", unsafe_allow_html=True)
        aspect_rows = "".join([f"<tr><td style='padding:8px 12px; font-weight:500; color:#555; white-space:nowrap;'>{k}</td><td style='padding:8px 12px; color:#333;'>{v}</td></tr>" for k, v in report['aspect_analysis'].items()])
        st.markdown(f"""<div class='report-section'><div class='report-section-title'>🔍 속성별 핵심 이슈</div><table style='width:100%; border-collapse:collapse; font-size:14px;'><thead><tr style='background:#F8F9FA;'><th style='padding:8px 12px; text-align:left; color:#888; width:120px;'>속성</th><th style='padding:8px 12px; text-align:left; color:#888;'>이슈</th></tr></thead><tbody>{aspect_rows}</tbody></table></div>""", unsafe_allow_html=True)
        recs = report['recommendations'][:3]
        rec_html = "".join([f"<div class='report-rec'>{i+1}) {rec}</div>" for i, rec in enumerate(recs)])
        st.markdown(f"""<div class='report-section'><div class='report-section-title'>💡 개선 권고사항</div>{rec_html}</div>""", unsafe_allow_html=True)
        aspect_table_rows = "".join([f"<tr><td><b>{k}</b></td><td>{v}</td></tr>" for k, v in report['aspect_analysis'].items()])
        rec_divs = "".join([f'<div class="rec">{i+1}) {rec}</div>' for i, rec in enumerate(recs)])
        issue_divs = "".join([f'<div class="issue">• {issue}</div>' for issue in report['top_issues']])
        generated_at = datetime.now().strftime('%Y-%m-%d %H:%M')
        report_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{{font-family:sans-serif;max-width:800px;margin:40px auto;color:#333}}h1{{font-size:20px;border-bottom:2px solid #E24B4A;padding-bottom:10px}}h2{{font-size:15px;color:#555;margin-top:28px}}.summary{{background:#F8F9FA;border-radius:8px;padding:14px 18px;font-size:14px;line-height:1.7}}.issue{{padding:7px 0;border-bottom:1px solid #EEE;font-size:14px}}table{{width:100%;border-collapse:collapse;font-size:14px;margin-top:8px}}th{{background:#F8F9FA;padding:8px 12px;text-align:left;color:#888}}td{{padding:8px 12px;border-bottom:1px solid #EEE}}.rec{{background:#F0F6FF;border-left:3px solid #378ADD;border-radius:6px;padding:10px 14px;margin-bottom:8px;font-size:14px}}.footer{{font-size:12px;color:#AAA;margin-top:40px}}</style></head><body><h1>주간 리뷰 모니터링 리포트</h1><p style="font-size:13px;color:#AAA;">생성일시: {generated_at}</p><h2>📋 이번 주 현황</h2><div class="summary">{report['summary']}</div><h2>⚠️ 주요 고객 불만</h2>{issue_divs}<h2>🔍 속성별 핵심 이슈</h2><table><tr><th>속성</th><th>이슈</th></tr>{aspect_table_rows}</table><h2>💡 개선 권고사항</h2>{rec_divs}<div class="footer">본 리포트는 Claude Sonnet AI가 자동 생성했습니다.</div></body></html>"""
        st.download_button(label="📥 리포트 다운로드 (.html)", data=report_html.encode("utf-8"), file_name=f"review_report_{datetime.now().strftime('%Y%m%d_%H%M')}.html", mime="text/html")


# ════════════════════════════════════════════════
# AI 챗봇
# ════════════════════════════════════════════════
else:
    with st.sidebar:
        st.markdown("### 💬 질문 예시")
        st.info("""
- 전체 리뷰 중 부정 비율이 어떻게 돼?
- 월별 속성별 교차 분석 차트 그려줘
- 배송 부정 리뷰 보여줘
- 평점 분포 차트 그려줘
        """)
        st.markdown("### 📊 차트 요청 예시")
        st.success("""
- 감성 비율 파이차트
- 월별 감성 추이 라인차트
- 속성별 감성 비교 차트
- 평점 분포 보여줘
        """)

    col_title, col_clear = st.columns([6, 1])
    with col_title:
        st.markdown("## 🤖 AI 리뷰 분석 챗봇")
        st.markdown("<p style='color:#AAA; font-size:13px;'>리뷰 데이터에 대해 자유롭게 질문하세요. 차트도 그려드립니다.</p>", unsafe_allow_html=True)
    with col_clear:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)  # 수직 정렬
        if st.button("🔄 초기화", use_container_width=True):
            st.session_state["chat_messages"] = []
            st.session_state["last_aspects"] = []
            st.session_state["last_sentiment"] = None
    st.divider()

    @st.cache_data(ttl=300)
    def get_data_summary():
        total = len(df)
        sentiment_dist = df["sentiment"].value_counts().to_dict()
        aspect_counts_all = {}
        for al in df["aspects_list"]:
            for a in al: aspect_counts_all[a] = aspect_counts_all.get(a, 0) + 1
        aspect_sentiment = {}
        for _, row in df.iterrows():
            for a in row["aspects_list"]:
                if a not in aspect_sentiment:
                    aspect_sentiment[a] = {"긍정": 0, "부정": 0, "중립": 0}
                s = row["sentiment"]
                if s in aspect_sentiment[a]: aspect_sentiment[a][s] += 1
        date_range = f"{df['review_date'].min().strftime('%Y-%m-%d')} ~ {df['review_date'].max().strftime('%Y-%m-%d')}"
        monthly = df.groupby(df["review_date"].dt.strftime("%Y-%m")).size().to_dict()
        rating_dist = df["rating"].value_counts().sort_index().to_dict()
        return {"총 리뷰 수": total, "데이터 기간": date_range, "감성 분포": sentiment_dist, "속성별 리뷰 수": aspect_counts_all, "속성별 감성 분포": aspect_sentiment, "월별 리뷰 수": monthly, "평점 분포": rating_dist}

    data_summary = get_data_summary()
    llm = ChatAnthropic(model="claude-sonnet-4-5", api_key=os.getenv("ANTHROPIC_API_KEY"))

    def build_chart(question, aspects_filter, sentiment_filter, chart_type="기타"):
        q = question.lower()
        plot_df = df.copy()
        if aspects_filter:
            plot_df = plot_df[plot_df["aspects_list"].apply(lambda x: any(a in x for a in aspects_filter))]
        if sentiment_filter and sentiment_filter != "전체":
            plot_df = plot_df[plot_df["sentiment"] == sentiment_filter]
        bar_c = "#E24B4A" if sentiment_filter == "부정" else "#1D9E75" if sentiment_filter == "긍정" else "#378ADD"
        fill_c = "rgba(226,75,74,0.08)" if sentiment_filter == "부정" else "rgba(29,158,117,0.08)" if sentiment_filter == "긍정" else "rgba(55,138,221,0.08)"

        if chart_type == "monthly_aspect" or ("월별" in q and ("속성" in q or "교차" in q)):
            plot_df["월"] = plot_df["review_date"].dt.strftime("%Y-%m")
            rows = []
            for _, row in plot_df.iterrows():
                for a in row["aspects_list"]: rows.append({"월": row["월"], "속성": a})
            if not rows: return None
            cross_df = pd.DataFrame(rows).groupby(["월", "속성"]).size().reset_index(name="건수")
            top5 = cross_df.groupby("속성")["건수"].sum().nlargest(5).index.tolist()
            cross_df = cross_df[cross_df["속성"].isin(top5)]
            fig = px.bar(cross_df, x="월", y="건수", color="속성", barmode="group", title="월별 × 속성별 리뷰 수")
            fig.update_layout(height=400, paper_bgcolor="white", plot_bgcolor="white", font=dict(family="Noto Sans KR"))
            return fig

        if chart_type == "rating" or "평점" in q or "별점" in q:
            rating_counts = plot_df["rating"].value_counts().sort_index().reset_index()
            rating_counts.columns = ["평점", "건수"]
            rating_counts["라벨"] = rating_counts["평점"].apply(lambda x: f"★{x}")
            colors = ["#E24B4A", "#F4845F", "#B4B2A9", "#6EC197", "#1D9E75"]
            fig = go.Figure(go.Bar(x=rating_counts["라벨"], y=rating_counts["건수"], marker_color=colors[:len(rating_counts)], text=rating_counts["건수"].apply(lambda x: f"{x:,}"), textposition="outside"))
            fig.update_layout(title="평점 분포", height=350, paper_bgcolor="white", plot_bgcolor="white", font=dict(family="Noto Sans KR"), xaxis_title="", yaxis_title="건수")
            return fig

        if chart_type == "monthly_trend" or ("월별" in q and ("트렌드" in q or "추이" in q or "변화" in q)):
            plot_df["월"] = plot_df["review_date"].dt.strftime("%Y-%m")
            monthly = plot_df.groupby(["월", "sentiment"]).size().reset_index(name="건수")
            cmap3 = {"긍정": "#1D9E75", "부정": "#E24B4A", "중립": "#B4B2A9"}
            fig = px.line(monthly, x="월", y="건수", color="sentiment", color_discrete_map=cmap3, markers=True, title="월별 감성 추이")
            fig.update_layout(height=350, paper_bgcolor="white", plot_bgcolor="white", font=dict(family="Noto Sans KR"), legend_title="감성")
            return fig

        if "파이" in q or "pie" in q or ("비율" in q and "차트" in q):
            counts = plot_df["sentiment"].value_counts().reset_index()
            counts.columns = ["감성", "건수"]
            cmap = {"긍정": "#1D9E75", "부정": "#E24B4A", "중립": "#B4B2A9"}
            fig = go.Figure(go.Pie(labels=counts["감성"], values=counts["건수"], hole=0.4, marker_colors=[cmap.get(s, "#ccc") for s in counts["감성"]], textinfo="label+percent+value"))
            fig.update_layout(title="감성 분포", height=350, paper_bgcolor="white", font=dict(family="Noto Sans KR"))
        elif "라인" in q or "추이" in q or "트렌드" in q:
            daily = plot_df.groupby("review_date").size().reset_index(name="건수")
            fig = go.Figure(go.Scatter(x=daily["review_date"], y=daily["건수"], mode="lines+markers", line=dict(color=bar_c, width=2), fill="tozeroy", fillcolor=fill_c))
            fig.update_layout(title="날짜별 리뷰 트렌드", height=300, paper_bgcolor="white", plot_bgcolor="white", font=dict(family="Noto Sans KR"))
        elif "속성별 감성" in q or "감성 비교" in q:
            rows = []
            for a, sents in data_summary["속성별 감성 분포"].items():
                for s, cnt in sents.items(): rows.append({"속성": a, "감성": s, "건수": cnt})
            asp_df = pd.DataFrame(rows)
            asp_df = asp_df[asp_df["건수"] > 0]
            cmap2 = {"긍정": "#1D9E75", "부정": "#E24B4A", "중립": "#B4B2A9"}
            fig = px.bar(asp_df, x="속성", y="건수", color="감성", color_discrete_map=cmap2, barmode="stack", title="속성별 감성 분포")
            fig.update_layout(height=350, paper_bgcolor="white", plot_bgcolor="white", font=dict(family="Noto Sans KR"))
        else:
            asp_counts = {}
            for al in plot_df["aspects_list"]:
                for a in al: asp_counts[a] = asp_counts.get(a, 0) + 1
            if not asp_counts: return None
            asp_df = pd.DataFrame(list(asp_counts.items()), columns=["속성", "건수"]).sort_values("건수", ascending=True).tail(8)
            fig = go.Figure(go.Bar(x=asp_df["건수"], y=asp_df["속성"], orientation="h", marker_color=bar_c, text=asp_df["건수"].apply(lambda x: f"{x:,}"), textposition="outside"))
            fig.update_layout(title="속성별 리뷰 건수", height=350, paper_bgcolor="white", plot_bgcolor="white", xaxis=dict(showgrid=False, showticklabels=False), font=dict(family="Noto Sans KR"), margin=dict(t=40, b=10, l=10, r=60))
        return fig

    # 이전 대화 출력
    for i, message in enumerate(st.session_state["chat_messages"]):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("chart_json"):
                st.plotly_chart(go.Figure(message["chart_json"]), use_container_width=True, key=f"hist_{i}")

    # st.chat_input — 뷰포트 최하단에 sticky 고정 (사이드바 라디오로 페이지 전환 이미 해결됨)
    user_input = st.chat_input("질문을 입력하세요 (예: 월별 속성별 교차 분석 차트 그려줘)")

    if user_input:
        user_msg = user_input.strip()
        st.session_state["chat_messages"].append({"role": "user", "content": user_msg})

        # 처리 중 표시 (인라인 렌더링 없이 placeholder만 사용)
        with st.spinner("분석 중입니다..."):
            try:
                answer = ""
                fig = None
                chart_json = None

                decision_msg = [
                    ("system", """사용자 질문을 분석하여 아래 형식으로만 답하세요:
차트필요: [예/아니오]
차트종류: [monthly_aspect/monthly_trend/rating/기타]
속성필터: [배송/품질/가격/고객서비스/디자인/기능/사이즈/기타/없음]
감성필터: [긍정/부정/중립/전체/없음]"""),
                    ("user", user_msg)
                ]
                decision = llm.invoke(decision_msg).content.strip()
                need_chart = "차트필요: 예" in decision
                chart_type = "기타"
                aspects_filter = []
                sentiment_filter = None
                for line in decision.split("\n"):
                    if "차트종류" in line: chart_type = line.split(":")[-1].strip()
                    if "속성필터" in line:
                        val = line.split(":")[-1].strip()
                        if "없음" not in val:
                            aspects_filter = [v.strip() for v in val.replace("/", ",").split(",") if v.strip() and v.strip() != "없음"]
                    if "감성필터" in line:
                        val = line.split(":")[-1].strip()
                        if val not in ["없음", "전체"]: sentiment_filter = val
                if not aspects_filter and st.session_state["last_aspects"]:
                    aspects_filter = st.session_state["last_aspects"]
                if not sentiment_filter and st.session_state["last_sentiment"]:
                    sentiment_filter = st.session_state["last_sentiment"]

                if need_chart:
                    fig = build_chart(user_msg, aspects_filter, sentiment_filter, chart_type)
                    if fig is not None:
                        fig.update_layout(margin=dict(t=60, b=40))
                        chart_json = fig.to_dict()

                conversation_history = ""
                for msg in st.session_state["chat_messages"][-4:]:
                    role = "사용자" if msg["role"] == "user" else "AI"
                    conversation_history += f"{role}: {msg['content'][:200]}\n"

                system_prompt = f"""당신은 이커머스 리뷰 데이터 분석 전문가입니다.
규칙:
1. 데이터 수치를 정확히 사용하세요
2. 차트 코드나 JSON을 절대 출력하지 마세요
3. 마크다운 코드블록을 응답에 포함하지 마세요
4. 이전 대화 맥락을 참고하세요
5. 간결하고 명확하게 답변하세요

이전 대화: {conversation_history}
데이터: {json.dumps(data_summary, ensure_ascii=False)[:3000]}"""

                answer = llm.invoke([("system", system_prompt), ("user", f"질문: {user_msg}")]).content

                review_keywords = ["리뷰 보여줘", "원문", "전체 리뷰", "리뷰 목록", "리뷰 알려줘", "실제 리뷰", "어떤 리뷰", "리뷰 예시", "샘플"]
                if any(kw in user_msg for kw in review_keywords):
                    plot_df = df.copy()
                    if aspects_filter:
                        plot_df = plot_df[plot_df["aspects_list"].apply(lambda x: any(a in x for a in aspects_filter))]
                    if sentiment_filter:
                        plot_df = plot_df[plot_df["sentiment"] == sentiment_filter]
                    plot_df = plot_df.drop_duplicates(subset=["review"]).head(10)
                    if len(plot_df) > 0:
                        review_list = "\n".join([f"{i+1}. `{row['review_date'].strftime('%Y-%m-%d')}` ★{row['rating']} {row['review']}" for i, (_, row) in enumerate(plot_df.iterrows())])
                        answer += f"\n\n{review_list}"

                st.session_state["last_aspects"] = aspects_filter
                st.session_state["last_sentiment"] = sentiment_filter

            except Exception as e:
                answer = f"오류가 발생했습니다: {e}"
                chart_json = None

        # session_state에 저장 후 rerun → 루프에서 한 번만 깔끔하게 렌더링
        st.session_state["chat_messages"].append({
            "role": "assistant",
            "content": answer,
            "chart_json": chart_json
        })
        st.rerun()
                    decision_msg = [
                        ("system", """사용자 질문을 분석하여 아래 형식으로만 답하세요:
차트필요: [예/아니오]
차트종류: [monthly_aspect/monthly_trend/rating/기타]
속성필터: [배송/품질/가격/고객서비스/디자인/기능/사이즈/기타/없음]
감성필터: [긍정/부정/중립/전체/없음]"""),
                        ("user", user_msg)
                    ]
                    decision = llm.invoke(decision_msg).content.strip()
                    need_chart = "차트필요: 예" in decision
                    chart_type = "기타"
                    aspects_filter = []
                    sentiment_filter = None
                    for line in decision.split("\n"):
                        if "차트종류" in line: chart_type = line.split(":")[-1].strip()
                        if "속성필터" in line:
                            val = line.split(":")[-1].strip()
                            if "없음" not in val:
                                aspects_filter = [v.strip() for v in val.split(",") if v.strip()]
                        if "감성필터" in line:
                            val = line.split(":")[-1].strip()
                            if val not in ["없음", "전체"]: sentiment_filter = val
                    if not aspects_filter and st.session_state["last_aspects"]:
                        aspects_filter = st.session_state["last_aspects"]
                    if not sentiment_filter and st.session_state["last_sentiment"]:
                        sentiment_filter = st.session_state["last_sentiment"]

                    fig = None
                    if need_chart:
                        status_text.write("차트를 생성하고 있습니다...")
                        fig = build_chart(user_msg, aspects_filter, sentiment_filter, chart_type)

                    status_text.write("답변을 작성하고 있습니다...")
                    conversation_history = ""
                    for msg in st.session_state["chat_messages"][-4:]:
                        role = "사용자" if msg["role"] == "user" else "AI"
                        conversation_history += f"{role}: {msg['content'][:200]}\n"

                    system_prompt = f"""당신은 이커머스 리뷰 데이터 분석 전문가입니다.
규칙:
1. 데이터 수치를 정확히 사용하세요
2. 차트 코드나 JSON을 절대 출력하지 마세요
3. 마크다운 코드블록을 응답에 포함하지 마세요
4. 이전 대화 맥락을 참고하세요
5. 간결하고 명확하게 답변하세요

이전 대화: {conversation_history}
데이터: {json.dumps(data_summary, ensure_ascii=False)[:3000]}"""

                    answer = llm.invoke([("system", system_prompt), ("user", f"질문: {user_msg}")]).content

                    review_keywords = ["리뷰 보여줘", "원문", "전체 리뷰", "리뷰 목록", "리뷰 알려줘", "실제 리뷰", "어떤 리뷰", "리뷰 예시", "샘플"]
                    if any(kw in user_msg for kw in review_keywords):
                        plot_df = df.copy()
                        if aspects_filter:
                            plot_df = plot_df[plot_df["aspects_list"].apply(lambda x: any(a in x for a in aspects_filter))]
                        if sentiment_filter:
                            plot_df = plot_df[plot_df["sentiment"] == sentiment_filter]
                        plot_df = plot_df.drop_duplicates(subset=["review"]).head(10)
                        if len(plot_df) > 0:
                            review_list = "\n".join([f"{i+1}. `{row['review_date'].strftime('%Y-%m-%d')}` ★{row['rating']} {row['review']}" for i, (_, row) in enumerate(plot_df.iterrows())])
                            answer += f"\n\n{review_list}"

                    st.session_state["last_aspects"] = aspects_filter
                    st.session_state["last_sentiment"] = sentiment_filter
                    status_text.empty()
                    status.update(label="분석 완료!", state="complete", expanded=False)

                except Exception as e:
                    status.update(label="오류 발생", state="error")
                    answer = f"오류가 발생했습니다: {e}"
                    fig = None

            st.markdown(answer)
            chart_json = None
            if fig is not None:
                fig.update_layout(margin=dict(t=60, b=40))
                chart_json = fig.to_dict()
                st.plotly_chart(fig, use_container_width=True)

            st.session_state["chat_messages"].append({
                "role": "assistant",
                "content": answer,
                "chart_json": chart_json
            })