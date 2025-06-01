#!/usr/bin/env python3
"""
API를 통해 모든 활성 종목 데이터 채우기 테스트
"""

import requests
import json
import time
import sys

BASE_URL = "http://localhost:8000"


def test_fill_all_data_with_all_timeframes():
    """모든 활성 종목에 대해 'all' 타임프레임으로 데이터 채우기"""
    print("🚀 Testing fill all data with 'all' timeframes...")

    url = f"{BASE_URL}/fill-data/all"
    payload = {"timeframes": ["all"], "period": "max"}

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()

        result = response.json()
        print("✅ Request started successfully!")
        print(f"📊 Response: {json.dumps(result, indent=2, ensure_ascii=False)}")

        return result

    except requests.exceptions.RequestException as e:
        print(f"❌ API request failed: {e}")
        if hasattr(e, "response") and e.response:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return None


def test_reset_and_fill_all():
    """모든 데이터 리셋 후 다시 채우기"""
    print("\n🔄 Testing reset and refill all data...")

    url = f"{BASE_URL}/reset-data/all"
    payload = {"timeframes": ["all"], "period": "max"}

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()

        result = response.json()
        print("✅ Reset and refill started successfully!")
        print(f"📊 Response: {json.dumps(result, indent=2, ensure_ascii=False)}")

        return result

    except requests.exceptions.RequestException as e:
        print(f"❌ API request failed: {e}")
        if hasattr(e, "response") and e.response:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return None


def check_data_status(ticker: str):
    """특정 종목의 데이터 상태 확인"""
    print(f"\n📈 Checking data status for {ticker}...")

    url = f"{BASE_URL}/fill-data/status/{ticker}"

    try:
        response = requests.get(url)
        response.raise_for_status()

        result = response.json()
        print(f"📊 Data status for {ticker}:")

        for timeframe, status in result["status"].items():
            candles = status.get("candles", {})
            indicators = status.get("indicators", {})
            summary = status.get("summary", {})

            print(f"  {timeframe}:")
            print(
                f"    Candles: {candles.get('count', 0)} records, latest: {candles.get('latest', 'N/A')}"
            )
            print(f"    Indicators: latest: {indicators.get('latest', 'N/A')}")
            print(
                f"    Summary: latest: {summary.get('latest', 'N/A')}, level: {summary.get('level', 'N/A')}"
            )

        return result

    except requests.exceptions.RequestException as e:
        print(f"❌ Status check failed: {e}")
        return None


def wait_and_check_progress(tickers, max_wait_minutes=10):
    """데이터 채우기 진행상황 모니터링"""
    print(f"\n⏳ Monitoring progress for {max_wait_minutes} minutes...")

    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60

    while time.time() - start_time < max_wait_seconds:
        print(f"\n🔍 Checking progress... ({int((time.time() - start_time) / 60)} minutes elapsed)")

        for ticker in tickers[:3]:  # 처음 3개만 체크
            status = check_data_status(ticker)
            if status:
                time.sleep(2)  # API 호출 간격

        print("\n⏰ Waiting 30 seconds before next check...")
        time.sleep(30)

    print(f"\n✅ Monitoring completed after {max_wait_minutes} minutes")


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🎯 ChartBeacon Data Fill API Test")
    print("=" * 60)

    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        # 리셋 옵션
        result = test_reset_and_fill_all()
    else:
        # 일반 채우기
        result = test_fill_all_data_with_all_timeframes()

    if not result:
        print("❌ Failed to start data fill process")
        return

    # 결과에서 티커 목록 추출
    tickers = result.get("tickers", [])
    if not tickers:
        print("⚠️ No tickers found in response")
        return

    print(f"\n📋 Processing {len(tickers)} tickers: {', '.join(tickers)}")

    # 사용자에게 모니터링 여부 확인
    monitor = input("\n❓ Do you want to monitor progress? (y/N): ").lower().strip()
    if monitor in ["y", "yes"]:
        wait_and_check_progress(tickers)

    print("\n🎉 Test completed!")
    print("\n💡 You can check individual ticker status using:")
    for ticker in tickers[:3]:
        print(f"   curl {BASE_URL}/fill-data/status/{ticker}")


if __name__ == "__main__":
    main()
