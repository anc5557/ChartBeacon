import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from .database import engine, AsyncSessionLocal

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """거래 기록"""

    timestamp: datetime
    action: str  # "BUY" 또는 "SELL"
    price: float
    quantity: int
    reason: str  # 매매 이유 (예: "RSI_OVERSOLD", "MACD_SIGNAL")
    transaction_cost: float = 0.0  # 거래 비용


@dataclass
class BacktestResult:
    """백테스트 결과"""

    ticker: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return_pct: float
    buy_hold_return_pct: float  # 단순 보유 수익률
    alpha: float  # 초과 수익률 (전략 - 보유)
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float
    total_transaction_cost: float
    trades: List[Trade]


@dataclass
class BacktestConfig:
    """백테스트 설정"""

    transaction_cost_rate: float = 0.0015  # 거래비용 0.15%
    max_position_ratio: float = 0.95  # 최대 포지션 비율 95%
    stop_loss_ratio: float = 0.05  # 손절 비율 5%
    risk_free_rate: float = 0.03  # 무위험 수익률 3%


class BacktestEngine:
    """백테스트 엔진"""

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.engine = engine
        self.config = config or BacktestConfig()

    async def run_signal_backtest(
        self,
        ticker: str,
        timeframe: str = "1d",
        start_date: str = "2023-01-01",
        end_date: str = "2024-12-31",
        initial_capital: float = 100000,
        strategy: str = "technical_summary",
    ) -> BacktestResult:
        """
        시그널 기반 백테스트 실행

        Args:
            ticker: 종목 코드
            timeframe: 시간프레임
            start_date: 시작일
            end_date: 종료일
            initial_capital: 초기 자본
            strategy: 전략 ("technical_summary", "rsi", "macd")
        """
        logger.info(f"Starting backtest for {ticker} ({strategy})")

        async with AsyncSessionLocal() as session:
            # 데이터 조회
            candles_df = await self._get_candles_data(
                session, ticker, timeframe, start_date, end_date
            )
            indicators_df = await self._get_indicators_data(
                session, ticker, timeframe, start_date, end_date
            )
            summary_df = await self._get_summary_data(
                session, ticker, timeframe, start_date, end_date
            )

            # 데이터 검증
            self._validate_data(candles_df, ticker)

            # 데이터 병합
            merged_df = self._merge_backtest_data(candles_df, indicators_df, summary_df)

            # 전략별 시그널 생성
            if strategy == "technical_summary":
                signals_df = self._generate_summary_signals(merged_df)
            elif strategy == "rsi":
                signals_df = self._generate_rsi_signals(merged_df)
            elif strategy == "macd":
                signals_df = self._generate_macd_signals(merged_df)
            elif strategy == "trend_filtered":
                signals_df = self._generate_trend_filtered_signals(merged_df)
            elif strategy == "market_adaptive":
                signals_df = self._generate_market_adaptive_signals(merged_df)
            elif strategy == "buy_hold_first":
                signals_df = self._generate_buy_hold_first_signals(merged_df)
            elif strategy == "low_frequency":
                signals_df = self._generate_low_frequency_signals(merged_df)
            elif strategy == "adx_filtered":
                signals_df = self._generate_adx_filtered_signals(merged_df)
            elif strategy == "momentum_reversal":
                signals_df = self._generate_momentum_reversal_signals(merged_df)
            elif strategy == "position_sizing":
                signals_df = self._generate_position_sizing_signals(merged_df)
            else:
                raise ValueError(f"Unknown strategy: {strategy}")

            # 백테스트 실행
            result = self._execute_backtest(
                signals_df, ticker, initial_capital, start_date, end_date
            )

            return result

    def _validate_data(self, df: pd.DataFrame, ticker: str) -> None:
        """데이터 유효성 검증"""
        if df.empty:
            raise ValueError(f"No candle data found for {ticker}")

        if df["close"].isna().any():
            logger.warning(f"Missing price data detected for {ticker}")

        if len(df) < 30:
            logger.warning(f"Insufficient data points ({len(df)}) for reliable backtest")

        # 가격 데이터 이상치 체크
        price_cols = ["open", "high", "low", "close"]
        for col in price_cols:
            if (df[col] <= 0).any():
                raise ValueError(f"Invalid price data detected in {col}")

    async def _get_candles_data(
        self, session: AsyncSession, ticker: str, timeframe: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """캔들 데이터 조회"""
        query = text(
            """
            SELECT c.ts, c.open, c.high, c.low, c.close, c.volume
            FROM candles_raw c
            JOIN symbols s ON c.symbol_id = s.id
            WHERE s.ticker = :ticker 
            AND c.timeframe = :timeframe
            AND c.ts >= :start_date
            AND c.ts <= :end_date
            ORDER BY c.ts
        """
        )

        # 문자열 날짜를 datetime 객체로 변환
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        result = await session.execute(
            query,
            {
                "ticker": ticker,
                "timeframe": timeframe,
                "start_date": start_dt,
                "end_date": end_dt,
            },
        )

        rows = result.fetchall()
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"])
        df.set_index("ts", inplace=True)

        # 숫자 컬럼을 float로 변환 (Decimal 타입 처리)
        numeric_cols = ["open", "high", "low", "close", "volume"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    async def _get_indicators_data(
        self, session: AsyncSession, ticker: str, timeframe: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """지표 데이터 조회"""
        query = text(
            """
            SELECT i.ts, i.rsi14, i.macd, i.macd_signal, i.stoch_k, i.cci14, i.roc
            FROM indicators i
            JOIN symbols s ON i.symbol_id = s.id
            WHERE s.ticker = :ticker 
            AND i.timeframe = :timeframe
            AND i.ts >= :start_date
            AND i.ts <= :end_date
            ORDER BY i.ts
        """
        )

        # 문자열 날짜를 datetime 객체로 변환
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        result = await session.execute(
            query,
            {
                "ticker": ticker,
                "timeframe": timeframe,
                "start_date": start_dt,
                "end_date": end_dt,
            },
        )

        rows = result.fetchall()
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(
            rows,
            columns=["ts", "rsi14", "macd", "macd_signal", "stoch_k", "cci14", "roc"],
        )
        df["ts"] = pd.to_datetime(df["ts"])
        df.set_index("ts", inplace=True)

        # 숫자 컬럼을 float로 변환 (Decimal 타입 처리)
        numeric_cols = ["rsi14", "macd", "macd_signal", "stoch_k", "cci14", "roc"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    async def _get_summary_data(
        self, session: AsyncSession, ticker: str, timeframe: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """요약 데이터 조회"""
        query = text(
            """
            SELECT sm.ts, sm.level, sm.buy_cnt, sm.sell_cnt, sm.neutral_cnt
            FROM summary sm
            JOIN symbols s ON sm.symbol_id = s.id
            WHERE s.ticker = :ticker 
            AND sm.timeframe = :timeframe
            AND sm.ts >= :start_date
            AND sm.ts <= :end_date
            ORDER BY sm.ts
        """
        )

        # 문자열 날짜를 datetime 객체로 변환
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        result = await session.execute(
            query,
            {
                "ticker": ticker,
                "timeframe": timeframe,
                "start_date": start_dt,
                "end_date": end_dt,
            },
        )

        rows = result.fetchall()
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["ts", "level", "buy_cnt", "sell_cnt", "neutral_cnt"])
        df["ts"] = pd.to_datetime(df["ts"])
        df.set_index("ts", inplace=True)

        # 숫자 컬럼을 float로 변환 (Decimal 타입 처리)
        numeric_cols = ["buy_cnt", "sell_cnt", "neutral_cnt"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def _merge_backtest_data(
        self, candles: pd.DataFrame, indicators: pd.DataFrame, summary: pd.DataFrame
    ) -> pd.DataFrame:
        """백테스트용 데이터 병합"""
        # 캔들 데이터를 기준으로 병합
        merged = candles.copy()

        if not indicators.empty:
            merged = merged.join(indicators, how="left")

        if not summary.empty:
            merged = merged.join(summary, how="left")

        return merged.dropna(subset=["close"])

    def _generate_summary_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 요약 기반 시그널 생성"""
        signals = []

        for i, row in df.iterrows():
            signal = "HOLD"

            if pd.notna(row.get("level")):
                if row["level"] in ["STRONG_BUY", "BUY"]:
                    signal = "BUY"
                elif row["level"] in ["STRONG_SELL", "SELL"]:
                    signal = "SELL"

            signals.append(signal)

        df["signal"] = signals
        return df

    def _generate_rsi_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """RSI 기반 시그널 생성"""
        signals = []

        for i, row in df.iterrows():
            signal = "HOLD"

            if pd.notna(row.get("rsi14")):
                if row["rsi14"] < 30:
                    signal = "BUY"
                elif row["rsi14"] > 70:
                    signal = "SELL"

            signals.append(signal)

        df["signal"] = signals
        return df

    def _generate_macd_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """MACD 기반 시그널 생성"""
        signals = []

        # MACD와 Signal 라인 계산
        df_copy = df.copy()
        df_copy["macd_diff"] = df_copy["macd"] - df_copy["macd_signal"]
        df_copy["prev_macd_diff"] = df_copy["macd_diff"].shift(1)

        for i, row in df_copy.iterrows():
            signal = "HOLD"

            if pd.notna(row.get("macd_diff")) and pd.notna(row.get("prev_macd_diff")):
                # 골든 크로스: 이전이 음수에서 현재 양수로
                if row["prev_macd_diff"] <= 0 and row["macd_diff"] > 0:
                    signal = "BUY"
                # 데드 크로스: 이전이 양수에서 현재 음수로
                elif row["prev_macd_diff"] >= 0 and row["macd_diff"] < 0:
                    signal = "SELL"

            signals.append(signal)

        df["signal"] = signals
        return df

    def _generate_trend_filtered_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """트렌드 필터링된 시그널 생성 (상승 트렌드에서는 매도 금지)"""
        signals = []

        # 장기 이동평균으로 트렌드 판단 (50일)
        df_copy = df.copy()
        df_copy["ma50"] = df_copy["close"].rolling(window=50).mean()
        df_copy["ma200"] = df_copy["close"].rolling(window=200).mean()

        # 트렌드 강도 계산 (최근 20일 수익률)
        df_copy["trend_strength"] = df_copy["close"].pct_change(20)

        for i, row in df_copy.iterrows():
            signal = "HOLD"

            # 기본 시그널 (기술적 요약)
            if pd.notna(row.get("level")):
                base_signal = None
                if row["level"] in ["STRONG_BUY", "BUY"]:
                    base_signal = "BUY"
                elif row["level"] in ["STRONG_SELL", "SELL"]:
                    base_signal = "SELL"

                # 트렌드 필터링 적용
                if base_signal:
                    is_uptrend = (
                        pd.notna(row.get("ma50"))
                        and pd.notna(row.get("ma200"))
                        and row["close"] > row["ma50"]
                        and row["ma50"] > row["ma200"]
                    )

                    # 강한 상승 트렌드 체크 (최근 20일 10% 이상 상승)
                    strong_uptrend = (
                        pd.notna(row.get("trend_strength")) and row["trend_strength"] > 0.10
                    )

                    if base_signal == "BUY":
                        signal = "BUY"
                    elif base_signal == "SELL":
                        # 상승 트렌드에서는 매도 금지
                        if not (is_uptrend or strong_uptrend):
                            signal = "SELL"
                        # else: HOLD (매도 금지)

            signals.append(signal)

        df["signal"] = signals
        return df

    def _generate_market_adaptive_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """시장 적응형 시그널 생성"""
        signals = []

        df_copy = df.copy()

        # 시장 상황 분석 지표들
        df_copy["ma20"] = df_copy["close"].rolling(window=20).mean()
        df_copy["ma50"] = df_copy["close"].rolling(window=50).mean()
        df_copy["ma200"] = df_copy["close"].rolling(window=200).mean()

        # 변동성 (20일 표준편차)
        df_copy["volatility"] = df_copy["close"].pct_change().rolling(window=20).std()

        # 트렌드 강도 (50일 대비 현재가 위치)
        df_copy["trend_strength"] = (df_copy["close"] - df_copy["ma50"]) / df_copy["ma50"]

        for i, row in df_copy.iterrows():
            signal = "HOLD"

            # 시장 상황 판단
            is_strong_bull = (
                pd.notna(row.get("ma20"))
                and pd.notna(row.get("ma50"))
                and pd.notna(row.get("ma200"))
                and row["close"] > row["ma20"] > row["ma50"] > row["ma200"]
                and pd.notna(row.get("trend_strength"))
                and row["trend_strength"] > 0.15
            )

            is_bear_market = (
                pd.notna(row.get("ma50"))
                and pd.notna(row.get("ma200"))
                and row["close"] < row["ma50"]
                and row["ma50"] < row["ma200"]
            )

            # 기본 기술적 시그널
            if pd.notna(row.get("level")):
                base_signal = None
                if row["level"] in ["STRONG_BUY", "BUY"]:
                    base_signal = "BUY"
                elif row["level"] in ["STRONG_SELL", "SELL"]:
                    base_signal = "SELL"

                if base_signal:
                    if is_strong_bull:
                        # 강한 상승장: 매수만 허용, 매도 금지
                        if base_signal == "BUY":
                            signal = "BUY"
                        # 매도 신호 무시
                    elif is_bear_market:
                        # 하락장: 적극적 매매
                        signal = base_signal
                    else:
                        # 횡보장: 보수적 매매 (강한 신호만)
                        if row["level"] in ["STRONG_BUY", "STRONG_SELL"]:
                            signal = base_signal

            signals.append(signal)

        df["signal"] = signals
        return df

    def _generate_low_frequency_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        저빈도 트레이딩 전략
        - 신호 쿨다운 기간 적용 (매매 후 최소 N일 대기)
        - 강한 신호만 필터링
        - 추세 전환점에서만 매매
        """
        signals = []
        df_copy = df.copy()

        # 이동평균선으로 추세 정의
        df_copy["ma20"] = df_copy["close"].rolling(window=20).mean()
        df_copy["ma50"] = df_copy["close"].rolling(window=50).mean()

        # 추세 방향 계산
        df_copy["trend_up"] = df_copy["ma20"] > df_copy["ma50"]
        df_copy["trend_change"] = df_copy["trend_up"] != df_copy["trend_up"].shift(1)

        last_trade_idx = -float("inf")
        cooldown_period = 15  # 15일 쿨다운

        for i, (timestamp, row) in enumerate(df_copy.iterrows()):
            signal = "HOLD"

            # 쿨다운 체크
            if i - last_trade_idx < cooldown_period:
                signals.append(signal)
                continue

            # 강한 신호만 처리
            if pd.notna(row.get("level")) and row["level"] in ["STRONG_BUY", "STRONG_SELL"]:
                # 추세 전환 시점에서만 매매
                if row.get("trend_change", False):
                    if row["level"] == "STRONG_BUY" and row.get("trend_up", False):
                        signal = "BUY"
                        last_trade_idx = i
                    elif row["level"] == "STRONG_SELL" and not row.get("trend_up", True):
                        signal = "SELL"
                        last_trade_idx = i

            signals.append(signal)

        df["signal"] = signals
        return df

    def _generate_adx_filtered_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        ADX 기반 트렌드 강도 필터링 전략
        - ADX > 25일 때만 트렌드 추종
        - ADX < 20일 때는 매매 금지 (횡보)
        """
        signals = []
        df_copy = df.copy()

        # ADX 계산 (간단 버전)
        df_copy["high_low"] = df_copy["high"] - df_copy["low"]
        df_copy["high_close"] = abs(df_copy["high"] - df_copy["close"].shift(1))
        df_copy["low_close"] = abs(df_copy["low"] - df_copy["close"].shift(1))
        df_copy["tr"] = df_copy[["high_low", "high_close", "low_close"]].max(axis=1)
        df_copy["atr14"] = df_copy["tr"].rolling(window=14).mean()

        # 간단한 ADX 추정 (ATR 기반)
        df_copy["price_change"] = abs(df_copy["close"].pct_change())
        df_copy["adx_estimate"] = (
            df_copy["price_change"].rolling(window=14).mean() / df_copy["atr14"] * df_copy["close"]
        ) * 100

        for i, row in df_copy.iterrows():
            signal = "HOLD"

            # ADX 필터링
            adx = row.get("adx_estimate", 0)
            if pd.isna(adx):
                adx = 0

            # 강한 트렌드일 때만 매매
            if adx > 25:
                if pd.notna(row.get("level")):
                    if row["level"] in ["STRONG_BUY", "BUY"]:
                        signal = "BUY"
                    elif row["level"] in ["STRONG_SELL", "SELL"]:
                        signal = "SELL"
            # ADX < 20: 횡보 구간으로 판단, 매매 금지
            elif adx < 20:
                signal = "HOLD"

            signals.append(signal)

        df["signal"] = signals
        return df

    def _generate_momentum_reversal_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        모멘텀 반전 전략
        - 과매수/과매도 구간에서 반전 신호 포착
        - RSI, Stochastic, CCI 복합 활용
        """
        signals = []
        df_copy = df.copy()

        for i, row in df_copy.iterrows():
            signal = "HOLD"

            rsi = row.get("rsi14", 50)
            stoch = row.get("stoch_k", 50)
            cci = row.get("cci14", 0)

            # 극단적 과매도 (강한 매수 신호)
            extreme_oversold = (
                pd.notna(rsi)
                and rsi < 25
                and pd.notna(stoch)
                and stoch < 20
                and pd.notna(cci)
                and cci < -150
            )

            # 극단적 과매수 (강한 매도 신호)
            extreme_overbought = (
                pd.notna(rsi)
                and rsi > 75
                and pd.notna(stoch)
                and stoch > 80
                and pd.notna(cci)
                and cci > 150
            )

            if extreme_oversold:
                signal = "BUY"
            elif extreme_overbought:
                signal = "SELL"

            signals.append(signal)

        df["signal"] = signals
        return df

    def _generate_position_sizing_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        포지션 사이징 전략
        - 신호 강도에 따른 차등 매매
        - 변동성 기반 포지션 조절
        """
        signals = []
        position_sizes = []
        df_copy = df.copy()

        # 변동성 계산
        df_copy["volatility"] = df_copy["close"].pct_change().rolling(window=20).std()

        for i, row in df_copy.iterrows():
            signal = "HOLD"
            position_size = 1.0  # 기본값 설정

            if pd.notna(row.get("level")):
                volatility = row.get("volatility", 0.02)

                # 변동성 역비례 포지션 사이징
                base_position = min(1.0, 0.02 / max(volatility, 0.01))

                if row["level"] == "STRONG_BUY":
                    signal = "BUY"
                    position_size = base_position * 1.0  # 100%
                elif row["level"] == "BUY":
                    signal = "BUY"
                    position_size = base_position * 0.6  # 60%
                elif row["level"] == "STRONG_SELL":
                    signal = "SELL"
                    position_size = base_position * 1.0  # 100%
                elif row["level"] == "SELL":
                    signal = "SELL"
                    position_size = base_position * 0.6  # 60%

            signals.append(signal)
            position_sizes.append(position_size)

        df["signal"] = signals
        # 포지션 사이즈 정보도 추가
        df["position_size"] = position_sizes

        return df

    def _generate_buy_hold_first_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        바이앤홀드 우선 전략
        - 첫 매수 후 장기 보유 우선
        - 명확한 약세 신호에서만 매도
        """
        signals = []
        df_copy = df.copy()

        # 장기 추세 판단
        df_copy["ma200"] = df_copy["close"].rolling(window=200).mean()
        df_copy["below_ma200"] = df_copy["close"] < df_copy["ma200"] * 0.9  # 10% 이하

        position_held = False

        for i, row in df_copy.iterrows():
            signal = "HOLD"

            if not position_held:
                # 포지션이 없을 때: 매수 기회 포착
                if pd.notna(row.get("level")) and row["level"] in ["STRONG_BUY", "BUY"]:
                    signal = "BUY"
                    position_held = True
            else:
                # 포지션 보유 중: 매도는 매우 제한적
                if (
                    pd.notna(row.get("level"))
                    and row["level"] == "STRONG_SELL"
                    and row.get("below_ma200", False)
                ):
                    signal = "SELL"
                    position_held = False

            signals.append(signal)

        df["signal"] = signals
        return df

    def _execute_backtest(
        self, df: pd.DataFrame, ticker: str, initial_capital: float, start_date: str, end_date: str
    ) -> BacktestResult:
        """백테스트 실행"""
        capital = initial_capital
        position = 0  # 보유 주식 수
        entry_price = 0.0  # 진입 가격
        trades = []
        portfolio_values = []
        total_transaction_cost = 0.0

        for timestamp, row in df.iterrows():
            current_price = row["close"]
            signal = row["signal"]

            # 손절 체크
            if position > 0 and current_price <= entry_price * (1 - self.config.stop_loss_ratio):
                signal = "SELL"
                reason = "STOP_LOSS"
            else:
                reason = signal

            # 매수 신호
            if signal == "BUY" and position == 0:
                # 최대 투자 가능 금액 계산
                max_investment = capital * self.config.max_position_ratio
                quantity = int(max_investment // current_price)

                if quantity > 0:
                    gross_cost = quantity * current_price
                    transaction_cost = gross_cost * self.config.transaction_cost_rate
                    total_cost = gross_cost + transaction_cost

                    if capital >= total_cost:
                        capital -= total_cost
                        position = quantity
                        entry_price = current_price
                        total_transaction_cost += transaction_cost

                        trades.append(
                            Trade(
                                timestamp=timestamp,
                                action="BUY",
                                price=current_price,
                                quantity=quantity,
                                reason=reason,
                                transaction_cost=transaction_cost,
                            )
                        )

            # 매도 신호
            elif signal == "SELL" and position > 0:
                gross_revenue = position * current_price
                transaction_cost = gross_revenue * self.config.transaction_cost_rate
                net_revenue = gross_revenue - transaction_cost

                capital += net_revenue
                total_transaction_cost += transaction_cost

                trades.append(
                    Trade(
                        timestamp=timestamp,
                        action="SELL",
                        price=current_price,
                        quantity=position,
                        reason=reason,
                        transaction_cost=transaction_cost,
                    )
                )

                position = 0
                entry_price = 0.0

            # 포트폴리오 가치 계산
            portfolio_value = capital + (position * current_price)
            portfolio_values.append(portfolio_value)

        # 마지막에 보유 주식이 있으면 매도
        if position > 0:
            final_price = df["close"].iloc[-1]
            gross_revenue = position * final_price
            transaction_cost = gross_revenue * self.config.transaction_cost_rate
            net_revenue = gross_revenue - transaction_cost

            capital += net_revenue
            total_transaction_cost += transaction_cost

            trades.append(
                Trade(
                    timestamp=df.index[-1],
                    action="SELL",
                    price=final_price,
                    quantity=position,
                    reason="FINAL_SELL",
                    transaction_cost=transaction_cost,
                )
            )

        # 성과 지표 계산
        final_capital = capital
        total_return_pct = ((final_capital - initial_capital) / initial_capital) * 100

        # Buy & Hold 수익률 계산
        buy_hold_return_pct = self._calculate_buy_hold_return(df, initial_capital)
        alpha = total_return_pct - buy_hold_return_pct

        # 개선된 승률 계산
        winning_trades, losing_trades = self._calculate_win_loss_trades(trades)
        win_rate = (winning_trades / max(1, winning_trades + losing_trades)) * 100

        # 최대 낙폭 계산
        max_drawdown = self._calculate_max_drawdown(portfolio_values)

        # 개선된 샤프 비율 계산
        sharpe_ratio = self._calculate_sharpe_ratio(portfolio_values)

        # 거래 쌍 수 계산 (매수-매도가 한 세트)
        completed_trades = min(
            len([t for t in trades if t.action == "BUY"]),
            len([t for t in trades if t.action == "SELL"]),
        )

        return BacktestResult(
            ticker=ticker,
            start_date=datetime.fromisoformat(start_date),
            end_date=datetime.fromisoformat(end_date),
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return_pct=total_return_pct,
            buy_hold_return_pct=buy_hold_return_pct,
            alpha=alpha,
            total_trades=completed_trades,  # 완성된 거래 쌍만 카운트
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            total_transaction_cost=total_transaction_cost,
            trades=trades,
        )

    def _calculate_win_loss_trades(self, trades: List[Trade]) -> tuple[int, int]:
        """승패 거래 계산 (개선된 버전)"""
        winning_trades = 0
        losing_trades = 0

        buy_stack = []  # FIFO 방식으로 매수 관리

        for trade in trades:
            if trade.action == "BUY":
                buy_stack.append(trade)
            elif trade.action == "SELL" and buy_stack:
                # 가장 오래된 매수와 매칭 (FIFO)
                buy_trade = buy_stack.pop(0)

                # 순수익 계산 (거래비용 포함)
                buy_cost = buy_trade.price * buy_trade.quantity + buy_trade.transaction_cost
                sell_revenue = trade.price * trade.quantity - trade.transaction_cost

                if sell_revenue > buy_cost:
                    winning_trades += 1
                else:
                    losing_trades += 1

        return winning_trades, losing_trades

    def _calculate_max_drawdown(self, portfolio_values: List[float]) -> float:
        """최대 낙폭 계산"""
        if not portfolio_values:
            return 0.0

        portfolio_df = pd.DataFrame({"value": portfolio_values})
        portfolio_df["cummax"] = portfolio_df["value"].cummax()
        portfolio_df["drawdown"] = (portfolio_df["value"] - portfolio_df["cummax"]) / portfolio_df[
            "cummax"
        ]

        return portfolio_df["drawdown"].min() * 100

    def _calculate_sharpe_ratio(self, portfolio_values: List[float]) -> float:
        """샤프 비율 계산 (무위험 수익률 고려)"""
        if len(portfolio_values) < 2:
            return 0.0

        returns = pd.Series(portfolio_values).pct_change().dropna()

        if returns.std() == 0:
            return 0.0

        # 일일 무위험 수익률 계산
        daily_risk_free_rate = self.config.risk_free_rate / 252

        excess_returns = returns - daily_risk_free_rate
        sharpe_ratio = excess_returns.mean() / returns.std() * np.sqrt(252)

        return sharpe_ratio

    def _calculate_buy_hold_return(self, df: pd.DataFrame, initial_capital: float) -> float:
        """Buy & Hold 수익률 계산"""
        if df.empty:
            return 0.0

        start_price = df["close"].iloc[0]
        end_price = df["close"].iloc[-1]

        # 거래비용 고려하여 매수할 수 있는 주식 수 계산
        transaction_cost = initial_capital * self.config.transaction_cost_rate
        available_capital = initial_capital - transaction_cost
        shares = available_capital // start_price

        if shares <= 0:
            return 0.0

        # 매도 시 거래비용 차감
        final_value = shares * end_price
        final_transaction_cost = final_value * self.config.transaction_cost_rate
        final_capital = final_value - final_transaction_cost

        return ((final_capital - initial_capital) / initial_capital) * 100
