#!/usr/bin/env python3
"""
한국 종목 데이터 채우기 테스트 스크립트
"""

import asyncio
import sys
import os

# 현재 디렉토리를 Python path에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.data_filler import fill_historical_data


async def main():
    """삼성전자 데이터 채우기"""
    print("Starting data fill for 005930.KS (Samsung Electronics)")

    try:
        await fill_historical_data(
            ticker="005930.KS",
            timeframes=["5m", "1h", "1d", "5d", "1mo", "3mo"],
            period="60d",
        )
        print("✅ Data fill completed successfully!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
