import requests
import json
import time

def get_kurly_reviews(contents_product_no: str, total_pages: int = 10):
    """
    컬리 리뷰 API 직접 호출 (Playwright 불필요!)
    """
    base_url = f"https://api.kurly.com/product-review/v3/contents-products/{contents_product_no}/reviews"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://www.kurly.com/goods/{contents_product_no}",
        "Accept": "application/json",
    }
    
    all_reviews = []
    page = 1
    
    while True:
        params = {
            "sortType": "RECENTLY",  # RECENTLY or RECOMMEND
            "size": 40,              # 한 번에 최대 40개
            "page": page,
            "onlyImage": "false",
            "filters": ""
        }
        
        try:
            resp = requests.get(base_url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            reviews = data.get("data", [])
            if not reviews:
                print(f"페이지 {page}: 리뷰 없음, 종료")
                break
            
            all_reviews.extend(reviews)
            print(f"페이지 {page}: {len(reviews)}개 수집 (누적 {len(all_reviews)}개)")
            
            if page >= total_pages:
                break
                
            page += 1
            time.sleep(0.5)  # 너무 빠른 요청 방지
            
        except Exception as e:
            print(f"에러: {e}")
            break
    
    return all_reviews


def save_reviews(reviews: list, filename: str = "kurly_reviews.json"):
    """리뷰를 JSON으로 저장"""
    # 필요한 필드만 추출
    cleaned = []
    for r in reviews:
        cleaned.append({
            "no": r.get("no"),
            "type": r.get("type"),
            "contents": r.get("contents"),
            "ownerName": r.get("ownerName"),
            "ownerGrade": r.get("ownerGrade"),
            "registeredAt": r.get("registeredAt"),
            "likeCount": r.get("likeCount"),
            "imageCount": len(r.get("images", [])),
        })
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 저장 완료: {filename} ({len(cleaned)}개)")
    return cleaned


# ===== 실행 =====
if __name__ == "__main__":
    PRODUCT_NO = "1001107503"
    
    # 전체 리뷰 수 확인
    count_url = f"https://api.kurly.com/product-review/v1/contents-products/{PRODUCT_NO}/count"
    count_resp = requests.get(count_url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://www.kurly.com/goods/{PRODUCT_NO}"
    })
    total = count_resp.json()["data"]["count"]
    total_pages = (total // 40) + 1
    print(f"총 리뷰 수: {total}개 ({total_pages}페이지)\n")
    
    # 수집
    reviews = get_kurly_reviews(PRODUCT_NO, total_pages=total_pages)
    save_reviews(reviews)