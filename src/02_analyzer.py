"""
02_analyzer.py
DB에서 미분석 리뷰를 가져와 Claude Sonnet으로 분석 후 결과를 저장하는 스크립트

분석 항목:
- 속성(aspects): 배송, 품질, 가격, 고객서비스, 디자인, 기능, 기타
- 핵심 이슈(issues): 부정 리뷰의 주요 문제점
- 한줄 요약(summary): 리뷰 핵심 내용 요약
"""

import sqlite3
import json
import os
import time
import anthropic
from dotenv import load_dotenv

# ── 환경변수 로드 ──────────────────────────────────────────
load_dotenv()

# ── 경로 설정 ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database.db")

# ── Claude 클라이언트 초기화 ───────────────────────────────
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ── 1. 미분석 리뷰 가져오기 ────────────────────────────────
def get_unanalyzed_reviews(conn: sqlite3.Connection, limit: int = 10) -> list:
    """is_analyzed=0인 리뷰를 limit 건수만큼 가져옴"""
    cursor = conn.cursor()
    rows = cursor.execute("""
        SELECT id, rating, review, sentiment, review_date
        FROM reviews
        WHERE is_analyzed = 0
        ORDER BY review_date DESC
        LIMIT ?
    """, (limit,)).fetchall()

    return [
        {"id": r[0], "rating": r[1], "review": r[2], "sentiment": r[3], "review_date": r[4]}
        for r in rows
    ]


# ── 2. Claude Sonnet으로 분석 ──────────────────────────────
def analyze_reviews_with_claude(reviews: list) -> list:
    """
    리뷰 목록을 Claude Sonnet에게 보내 분석 결과를 받아옴
    배치로 처리하여 API 호출 횟수를 최소화
    """

    # 리뷰 목록을 텍스트로 변환
    reviews_text = "\n".join([
        f"[ID:{r['id']}] 별점:{r['rating']}점 | {r['review']}"
        for r in reviews
    ])

    prompt = f"""다음은 네이버 쇼핑 상품 리뷰들입니다. 각 리뷰를 분석하여 JSON 형식으로 반환해주세요.

리뷰 목록:
{reviews_text}

각 리뷰에 대해 아래 항목을 분석해주세요:
1. aspects: 언급된 속성 목록 (배송, 품질, 가격, 고객서비스, 디자인, 기능, 사이즈, 기타 중 해당하는 것)
2. issues: 부정적인 경우 핵심 문제점 (없으면 null)
3. summary: 리뷰 핵심 내용 한줄 요약 (15자 이내)

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요:
[
  {{
    "id": 리뷰ID,
    "aspects": ["속성1", "속성2"],
    "issues": "핵심 문제점 또는 null",
    "summary": "한줄 요약"
  }},
  ...
]"""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    # 응답 파싱
    response_text = message.content[0].text.strip()

    # JSON 파싱 (코드블록 제거)
    if "```" in response_text:
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]

    results = json.loads(response_text)
    return results


# ── 3. 분석 결과 DB 저장 ───────────────────────────────────
def save_analysis_results(conn: sqlite3.Connection, results: list):
    """분석 결과를 analysis_results 테이블에 저장하고 reviews 테이블 업데이트"""
    cursor = conn.cursor()

    for result in results:
        review_id = result["id"]
        aspects = json.dumps(result.get("aspects", []), ensure_ascii=False)
        issues = result.get("issues")
        summary = result.get("summary", "")

        # analysis_results 저장
        cursor.execute("""
            INSERT INTO analysis_results (review_id, aspects, issues, summary)
            VALUES (?, ?, ?, ?)
        """, (review_id, aspects, issues, summary))

        # reviews 테이블 분석 완료 표시
        cursor.execute("""
            UPDATE reviews SET is_analyzed = 1 WHERE id = ?
        """, (review_id,))

    conn.commit()


# ── 4. 분석 현황 출력 ─────────────────────────────────────
def print_progress(conn: sqlite3.Connection):
    cursor = conn.cursor()
    total = cursor.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    analyzed = cursor.execute("SELECT COUNT(*) FROM reviews WHERE is_analyzed = 1").fetchone()[0]
    remaining = total - analyzed
    print(f"\n📊 분석 현황: {analyzed:,}/{total:,}건 완료 (남은 건수: {remaining:,}건)")


# ── 메인 실행 ─────────────────────────────────────────────
def main(batch_size: int = 30, num_batches: int = 667):
    """
    batch_size: 한 번에 분석할 리뷰 수
    num_batches: 실행할 배치 횟수 (30 × 667 = 약 2만건)
    """
    print("=" * 50)
    print("🤖 Claude Sonnet 리뷰 분석 시작")
    print("=" * 50)

    conn = sqlite3.connect(DB_PATH)

    for batch_num in range(1, num_batches + 1):
        print(f"\n[배치 {batch_num}/{num_batches}]")

        # 미분석 리뷰 가져오기
        reviews = get_unanalyzed_reviews(conn, limit=batch_size)

        if not reviews:
            print("✅ 모든 리뷰 분석 완료!")
            break

        print(f"  분석 대상: {len(reviews)}건")

        # Claude 분석 (Rate limit 재시도 포함)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                results = analyze_reviews_with_claude(reviews)
                print(f"  Claude 응답 수신: {len(results)}건")

                # 결과 저장
                save_analysis_results(conn, results)
                print(f"  DB 저장 완료 ✅")

                # 샘플 출력 (첫 배치만)
                if batch_num == 1:
                    print(f"\n  📝 분석 샘플:")
                    for r in results[:2]:
                        print(f"    ID {r['id']} | 속성: {r['aspects']} | 요약: {r['summary']}")
                        if r.get('issues'):
                            print(f"           이슈: {r['issues']}")
                break  # 성공하면 재시도 루프 탈출

            except anthropic.RateLimitError:
                wait_time = 10 * (attempt + 1)  # 10초, 20초, 30초
                print(f"  ⚠️ Rate limit 도달, {wait_time}초 대기 후 재시도... ({attempt+1}/{max_retries})")
                time.sleep(wait_time)

            except json.JSONDecodeError as e:
                print(f"  ⚠️ JSON 파싱 오류, 재시도... ({attempt+1}/{max_retries}): {e}")
                time.sleep(2)

            except Exception as e:
                print(f"  ❌ 오류 발생: {e}")
                break

        # API 호출 간격 (대기시간 0.5초)
        if batch_num < num_batches:
            time.sleep(0.5)

    print_progress(conn)
    conn.close()
    print("\n✅ 분석 완료!")


if __name__ == "__main__":
    main(batch_size=30, num_batches=42)