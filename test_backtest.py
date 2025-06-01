#!/usr/bin/env python3
"""
백테스트 기능 테스트 스크립트
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# 현재 디렉토리를 Python path에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.backtest import BacktestEngine


async def test_backtest():
    """백테스트 테스트"""
    print("=== 백테스트 기능 테스트 ===")

    engine = BacktestEngine()

    # 테스트 종목들
    test_cases = [
        {
            "ticker": "005930.KS",
            "timeframe": "1d",
            "start_date": "2023-01-01",
            "end_date": "2024-06-30",
            "strategy": "technical_summary",
            "initial_capital": 1000000,
        },
        {
            "ticker": "AAPL",
            "timeframe": "1d",
            "start_date": "2023-01-01",
            "end_date": "2024-06-30",
            "strategy": "rsi",
            "initial_capital": 10000,
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- 테스트 케이스 {i}: {test_case['ticker']} ({test_case['strategy']}) ---")

        try:
            result = await engine.run_signal_backtest(
                ticker=test_case["ticker"],
                timeframe=test_case["timeframe"],
                start_date=test_case["start_date"],
                end_date=test_case["end_date"],
                initial_capital=test_case["initial_capital"],
                strategy=test_case["strategy"],
            )

            print(f"✅ 백테스트 완료: {result.ticker}")
            print(f"📊 기간: {result.start_date.date()} ~ {result.end_date.date()}")
            print(f"💰 초기 자본: {result.initial_capital:,.0f}원")
            print(f"💰 최종 자본: {result.final_capital:,.0f}원")
            print(f"📈 수익률: {result.total_return_pct:.2f}%")
            print(f"🔄 총 거래 수: {result.total_trades}")
            print(f"✅ 수익 거래: {result.winning_trades}")
            print(f"❌ 손실 거래: {result.losing_trades}")
            print(f"🎯 승률: {result.win_rate:.1f}%")
            print(f"📉 최대 낙폭: {result.max_drawdown:.2f}%")
            print(f"📊 샤프 비율: {result.sharpe_ratio:.3f}")

            # 최근 5개 거래 내역 출력
            if result.trades:
                print(f"\n최근 거래 내역 (최대 5개):")
                for trade in result.trades[-5:]:
                    print(
                        f"  {trade.timestamp.strftime('%Y-%m-%d %H:%M')} "
                        f"{trade.action} {trade.quantity}주 @ {trade.price:.2f} ({trade.reason})"
                    )

        except Exception as e:
            print(f"❌ 백테스트 실패: {str(e)}")
            import traceback

            traceback.print_exc()

    print("\n=== 백테스트 테스트 완료 ===")


async def test_strategy_comparison():
    """전략 비교 테스트"""
    print("\n=== 전략 비교 테스트 ===")

    engine = BacktestEngine()
    ticker = "005930.KS"
    strategies = ["technical_summary", "rsi", "macd"]
    results = {}

    for strategy in strategies:
        print(f"\n🔄 {strategy} 전략 테스트...")
        try:
            result = await engine.run_signal_backtest(
                ticker=ticker,
                timeframe="1d",
                start_date="2023-01-01",
                end_date="2024-06-30",
                initial_capital=1000000,
                strategy=strategy,
            )
            results[strategy] = result
            print(f"✅ 완료: 수익률 {result.total_return_pct:.2f}%, 승률 {result.win_rate:.1f}%")
        except Exception as e:
            print(f"❌ 실패: {str(e)}")

    # 결과 비교
    if results:
        print(f"\n📊 {ticker} 전략 비교 결과:")
        print("-" * 80)
        print(f"{'전략':<20} {'수익률(%)':<12} {'승률(%)':<10} {'거래수':<8} {'샤프비율':<10}")
        print("-" * 80)

        for strategy, result in results.items():
            print(
                f"{strategy:<20} {result.total_return_pct:<12.2f} "
                f"{result.win_rate:<10.1f} {result.total_trades:<8} "
                f"{result.sharpe_ratio:<10.3f}"
            )

        # 최고 성과 전략
        best_strategy = max(results.items(), key=lambda x: x[1].total_return_pct)
        print(
            f"\n🏆 최고 성과 전략: {best_strategy[0]} "
            f"(수익률: {best_strategy[1].total_return_pct:.2f}%)"
        )


if __name__ == "__main__":
    asyncio.run(test_backtest())
    asyncio.run(test_strategy_comparison())
