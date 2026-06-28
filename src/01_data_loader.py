"""
01_data_loader.py
네이버 쇼핑 리뷰 데이터를 SQLite DB에 적재하고,
날짜별 시뮬레이션 데이터를 생성하는 스크립트
"""

import sqlite3
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import random

# ── 경로 설정 ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_PATH = os.path.join(BASE_DIR, "data", "raw", "naver_shopping.txt")
DB_PATH = os.path.join(BASE_DIR, "database.db")


# ── 1. 데이터 로드 및 전처리 ───────────────────────────────
def load_raw_data(path: str) -> pd.DataFrame:
    """txt 파일을 DataFrame으로 로드"""
    df = pd.read_csv(path, sep="\t", names=["rating", "review"], encoding="utf-8")

    # 결측치 및 빈 리뷰 제거
    df = df.dropna()
    df = df[df["review"].str.strip() != ""]

    # 별점 기반 감성 레이블 생성 (4~5=긍정, 1~2=부정, 3=중립)
    def rating_to_sentiment(r):
        if r >= 4:
            return "긍정"
        elif r <= 2:
            return "부정"
        else:
            return "중립"

    df["sentiment"] = df["rating"].apply(rating_to_sentiment)

    print(f"✅ 데이터 로드 완료: {len(df):,}건")
    print(f"   감성 분포:\n{df['sentiment'].value_counts().to_string()}")
    return df


# ── 2. 날짜 시뮬레이션 ─────────────────────────────────────
def assign_simulated_dates(df: pd.DataFrame, days: int = 90) -> pd.DataFrame:
    """
    90일치 날짜를 랜덤 배정하여 '시간 흐름에 따른 리뷰 유입'을 시뮬레이션
    - 최근 날짜에 더 많은 리뷰가 몰리도록 가중치 적용
    """
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)

    date_range = pd.date_range(start=start_date, end=end_date, freq="D")

    # 최근일수록 가중치 높게 (지수 분포 사용)
    weights = np.exp(np.linspace(0, 2, len(date_range)))
    weights = weights / weights.sum()

    assigned_dates = np.random.choice(date_range, size=len(df), p=weights)
    df["review_date"] = pd.to_datetime(assigned_dates).normalize()
    df["review_date"] = df["review_date"].dt.strftime("%Y-%m-%d")

    print(f"✅ 날짜 시뮬레이션 완료: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    return df


# ── 3. DB 생성 및 적재 ─────────────────────────────────────
def create_tables(conn: sqlite3.Connection):
    """DB 테이블 생성"""
    cursor = conn.cursor()

    # 리뷰 원본 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            rating      INTEGER NOT NULL,
            review      TEXT NOT NULL,
            sentiment   TEXT NOT NULL,
            review_date TEXT NOT NULL,
            is_analyzed INTEGER DEFAULT 0,  -- 0: 미분석, 1: 분석완료
            created_at  TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # Claude 분석 결과 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id       INTEGER NOT NULL,
            aspects         TEXT,       -- 감지된 속성 (JSON 형태 문자열)
            issues          TEXT,       -- 핵심 이슈 요약
            summary         TEXT,       -- 한줄 요약
            analyzed_at     TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (review_id) REFERENCES reviews(id)
        )
    """)

    # 알림 이력 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_date  TEXT NOT NULL,
            alert_type  TEXT NOT NULL,  -- 'negative_spike', 'keyword_surge' 등
            message     TEXT NOT NULL,
            is_sent     INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.commit()
    print("✅ DB 테이블 생성 완료")


def save_to_db(df: pd.DataFrame, conn: sqlite3.Connection, chunk_size: int = 5000):
    """DataFrame을 청크 단위로 DB에 저장"""
    total = len(df)
    saved = 0

    for i in range(0, total, chunk_size):
        chunk = df.iloc[i:i + chunk_size][["rating", "review", "sentiment", "review_date"]]
        chunk.to_sql("reviews", conn, if_exists="append", index=False)
        saved += len(chunk)
        print(f"   저장 중... {saved:,}/{total:,}건", end="\r")

    print(f"\n✅ DB 저장 완료: {saved:,}건")


# ── 4. 샘플 데이터 조회 ────────────────────────────────────
def check_db(conn: sqlite3.Connection):
    """저장된 데이터 확인"""
    cursor = conn.cursor()

    total = cursor.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    by_sentiment = cursor.execute(
        "SELECT sentiment, COUNT(*) FROM reviews GROUP BY sentiment"
    ).fetchall()
    by_date_sample = cursor.execute(
        "SELECT review_date, COUNT(*) as cnt FROM reviews GROUP BY review_date ORDER BY review_date DESC LIMIT 5"
    ).fetchall()

    print(f"\n📊 DB 저장 현황")
    print(f"   전체 리뷰: {total:,}건")
    print(f"   감성별 분포:")
    for sentiment, count in by_sentiment:
        print(f"     {sentiment}: {count:,}건")
    print(f"   최근 5일 데이터:")
    for date, count in by_date_sample:
        print(f"     {date}: {count:,}건")


# ── 메인 실행 ─────────────────────────────────────────────
def main():
    print("=" * 50)
    print("🚀 리뷰 모니터링 시스템 - 데이터 적재 시작")
    print("=" * 50)

    # 1. 원본 데이터 로드
    df = load_raw_data(RAW_DATA_PATH)

    # 2. 날짜 시뮬레이션 (90일치)
    df = assign_simulated_dates(df, days=90)

    # 3. DB 연결 및 테이블 생성
    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)

    # 4. DB 저장
    save_to_db(df, conn)

    # 5. 저장 확인
    check_db(conn)

    conn.close()
    print("\n✅ 데이터 적재 완료!")


if __name__ == "__main__":
    main()
