"""
Technical indicators calculator for ChartBeacon
"""

import pandas as pd
import pandas_ta as ta
from datetime import datetime
from typing import Dict
import logging
from sqlalchemy import create_engine, text
import os

logger = logging.getLogger(__name__)


class IndicatorCalculator:
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://chartbeacon:chartbeacon123@postgres:5432/chartbeacon",
        ).replace("postgresql+asyncpg://", "postgresql://")
        self.engine = create_engine(self.database_url)

    def get_candles(self, symbol_id: int, timeframe: str, limit: int = 200) -> pd.DataFrame:
        """Get candles from database"""
        query = text(
            """
            SELECT ts, open, high, low, close, volume
            FROM candles_raw
            WHERE symbol_id = :symbol_id AND timeframe = :timeframe
            ORDER BY ts DESC
            LIMIT :limit
        """
        )

        with self.engine.connect() as conn:
            result = conn.execute(
                query, {"symbol_id": symbol_id, "timeframe": timeframe, "limit": limit}
            )

            # Convert to DataFrame
            data = []
            for row in result:
                data.append(
                    {
                        "ts": row[0],
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]),
                    }
                )

            df = pd.DataFrame(data)

            if not df.empty:
                df.set_index("ts", inplace=True)

        # Sort by time ascending for indicator calculation
        df = df.sort_index()
        return df

    def get_candles_with_continuity(
        self, symbol_id: int, timeframe: str, min_points: int = 50, max_points: int = 200
    ) -> pd.DataFrame:
        """Get candles with better continuity for indicator calculation"""

        # 시간간격 설정
        timeframe_minutes = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": 1440,
            "5d": 7200,  # 5일 = 1440 * 5
            "1mo": 43200,  # 1개월 = 1440 * 30
            "3mo": 129600,  # 3개월 = 1440 * 90
        }
        expected_interval = timeframe_minutes.get(timeframe, 5)

        # 타임프레임에 따른 데이터 수집 기간 설정
        if timeframe == "5m":
            data_period = "7 days"  # 5분봉: 7일
        elif timeframe == "1h":
            data_period = "30 days"  # 1시간봉: 30일
        elif timeframe == "1d":
            data_period = "1000 days"  # 1일봉: 1000일 (MA200 + 여유분)
        elif timeframe == "5d":
            data_period = "3000 days"  # 5일봉: 3000일 (MA200 확보)
        elif timeframe in ["1mo", "3mo"]:
            data_period = "5000 days"  # 월봉: 5000일 (충분한 기간)
        else:
            data_period = "30 days"  # 기본값

        # 더 많은 데이터를 가져와서 연속성 확인
        query = text(
            f"""
            SELECT ts, open, high, low, close, volume
            FROM candles_raw
            WHERE symbol_id = :symbol_id AND timeframe = :timeframe
            AND ts >= NOW() - INTERVAL '{data_period}'
            ORDER BY ts DESC
            LIMIT :limit
        """
        )

        with self.engine.connect() as conn:
            result = conn.execute(
                query, {"symbol_id": symbol_id, "timeframe": timeframe, "limit": max_points * 2}
            )

            # Convert to DataFrame
            data = []
            for row in result:
                data.append(
                    {
                        "ts": row[0],
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]),
                    }
                )

            df = pd.DataFrame(data)

            if not df.empty:
                df.set_index("ts", inplace=True)
                df = df.sort_index()

                # 연속성 기반으로 최적 구간 선택
                if len(df) > max_points:
                    # 최근에서부터 연속성이 좋은 구간 찾기
                    best_start = 0
                    best_score = 0

                    for start in range(0, len(df) - min_points, 10):
                        end = min(start + max_points, len(df))
                        subset = df.iloc[start:end]

                        # 이 구간의 연속성 점수 계산
                        time_diffs = subset.index.to_series().diff().dt.total_seconds() / 60
                        max_allowed_gap = expected_interval * 2
                        gaps = time_diffs[time_diffs > max_allowed_gap]
                        score = (len(subset) - len(gaps)) / len(subset)

                        if score > best_score:
                            best_score = score
                            best_start = start

                    # 최적 구간 선택
                    df = df.iloc[best_start : best_start + max_points]

        return df

    def calculate_oscillators(self, df: pd.DataFrame) -> Dict:
        """Calculate oscillator indicators"""
        indicators = {}

        try:
            # RSI (14)
            rsi = ta.rsi(df["close"], length=14)
            indicators["rsi14"] = float(rsi.iloc[-1]) if not rsi.empty else None

            # Stochastic (9, 6)
            stoch = ta.stoch(df["high"], df["low"], df["close"], k=9, d=6)
            if stoch is not None and not stoch.empty:
                indicators["stoch_k"] = float(stoch["STOCHk_9_6_3"].iloc[-1])
                indicators["stoch_d"] = float(stoch["STOCHd_9_6_3"].iloc[-1])
            else:
                indicators["stoch_k"] = None
                indicators["stoch_d"] = None

            # MACD (12, 26, 9)
            macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
            if macd is not None and not macd.empty:
                indicators["macd"] = float(macd["MACD_12_26_9"].iloc[-1])
                indicators["macd_signal"] = float(macd["MACDs_12_26_9"].iloc[-1])
            else:
                indicators["macd"] = None
                indicators["macd_signal"] = None

            # ADX (14)
            adx = ta.adx(df["high"], df["low"], df["close"], length=14)
            indicators["adx14"] = (
                float(adx["ADX_14"].iloc[-1]) if adx is not None and not adx.empty else None
            )

            # CCI (14)
            cci = ta.cci(df["high"], df["low"], df["close"], length=14)
            indicators["cci14"] = float(cci.iloc[-1]) if not cci.empty else None

            # ATR (14)
            atr = ta.atr(df["high"], df["low"], df["close"], length=14)
            indicators["atr14"] = float(atr.iloc[-1]) if not atr.empty else None

            # Highs/Lows (14) - 최고가와 최저가의 차이
            high14 = df["high"].rolling(14).max()
            low14 = df["low"].rolling(14).min()
            indicators["highlow14"] = (
                float(high14.iloc[-1] - low14.iloc[-1]) if len(df) >= 14 else None
            )

            # Ultimate Oscillator
            ultosc = ta.uo(df["high"], df["low"], df["close"])
            indicators["ultosc"] = (
                float(ultosc.iloc[-1]) if ultosc is not None and not ultosc.empty else None
            )

            # ROC (12)
            roc = ta.roc(df["close"], length=12)
            indicators["roc"] = float(roc.iloc[-1]) if not roc.empty else None

            # Bull/Bear Power (13)
            ema13 = ta.ema(df["close"], length=13)
            if ema13 is not None and not ema13.empty:
                bull_power = df["high"] - ema13
                bear_power = df["low"] - ema13
                indicators["bull_bear"] = float(bull_power.iloc[-1] + bear_power.iloc[-1])
            else:
                indicators["bull_bear"] = None

        except Exception as e:
            logger.error(f"Error calculating oscillators: {str(e)}")

        return indicators

    def calculate_moving_averages(self, df: pd.DataFrame) -> Dict:
        """Calculate moving averages"""
        mas = {}

        try:
            # Simple Moving Averages - 데이터가 충분할 때만 계산
            for period in [5, 10, 20, 50, 100, 200]:
                if len(df) >= period:
                    ma = ta.sma(df["close"], length=period)
                    mas[f"ma{period}"] = float(ma.iloc[-1]) if not ma.empty else None
                else:
                    mas[f"ma{period}"] = None
                    logger.info(f"Insufficient data for MA{period}: {len(df)} < {period}")

            # Exponential Moving Averages (only for 5, 10, 20)
            for period in [5, 10, 20]:
                if len(df) >= period:
                    ema = ta.ema(df["close"], length=period)
                    mas[f"ema{period}"] = float(ema.iloc[-1]) if not ema.empty else None
                else:
                    mas[f"ema{period}"] = None

            # Fill missing EMAs with None
            for period in [50, 100, 200]:
                mas[f"ema{period}"] = None

        except Exception as e:
            logger.error(f"Error calculating moving averages: {str(e)}")

        return mas

    def save_indicators(
        self, symbol_id: int, timeframe: str, ts: datetime, indicators: Dict
    ) -> bool:
        """Save indicators to database"""
        try:
            # 기본값으로 None 설정
            default_indicators = {
                "rsi14": None,
                "stoch_k": None,
                "stoch_d": None,
                "macd": None,
                "macd_signal": None,
                "adx14": None,
                "cci14": None,
                "atr14": None,
                "highlow14": None,
                "ultosc": None,
                "roc": None,
                "bull_bear": None,
            }
            default_indicators.update(indicators)

            with self.engine.begin() as conn:  # begin()으로 자동 commit
                # UPSERT indicators
                query = text(
                    """
                    INSERT INTO indicators (
                        symbol_id, timeframe, ts,
                        rsi14, stoch_k, stoch_d, macd, macd_signal,
                        adx14, cci14, atr14, highlow14, ultosc, roc, bull_bear
                    ) VALUES (
                        :symbol_id, :timeframe, :ts,
                        :rsi14, :stoch_k, :stoch_d, :macd, :macd_signal,
                        :adx14, :cci14, :atr14, :highlow14, :ultosc, :roc, :bull_bear
                    )
                    ON CONFLICT (symbol_id, timeframe, ts)
                    DO UPDATE SET
                        rsi14 = EXCLUDED.rsi14,
                        stoch_k = EXCLUDED.stoch_k,
                        stoch_d = EXCLUDED.stoch_d,
                        macd = EXCLUDED.macd,
                        macd_signal = EXCLUDED.macd_signal,
                        adx14 = EXCLUDED.adx14,
                        cci14 = EXCLUDED.cci14,
                        atr14 = EXCLUDED.atr14,
                        highlow14 = EXCLUDED.highlow14,
                        ultosc = EXCLUDED.ultosc,
                        roc = EXCLUDED.roc,
                        bull_bear = EXCLUDED.bull_bear,
                        calc_at = CURRENT_TIMESTAMP
                """
                )

                conn.execute(
                    query,
                    {
                        "symbol_id": symbol_id,
                        "timeframe": timeframe,
                        "ts": ts,
                        **default_indicators,
                    },
                )
                return True

        except Exception as e:
            logger.error(f"Error saving indicators: {str(e)}")
            return False

    def save_moving_averages(self, symbol_id: int, timeframe: str, ts: datetime, mas: Dict) -> bool:
        """Save moving averages to database"""
        try:
            # 기본값으로 None 설정
            default_mas = {
                "ma5": None,
                "ema5": None,
                "ma10": None,
                "ema10": None,
                "ma20": None,
                "ema20": None,
                "ma50": None,
                "ma100": None,
                "ma200": None,
            }
            default_mas.update(mas)

            with self.engine.begin() as conn:  # begin()으로 자동 commit
                # UPSERT moving averages
                query = text(
                    """
                    INSERT INTO moving_avgs (
                        symbol_id, timeframe, ts,
                        ma5, ema5, ma10, ema10, ma20, ema20,
                        ma50, ma100, ma200
                    ) VALUES (
                        :symbol_id, :timeframe, :ts,
                        :ma5, :ema5, :ma10, :ema10, :ma20, :ema20,
                        :ma50, :ma100, :ma200
                    )
                    ON CONFLICT (symbol_id, timeframe, ts)
                    DO UPDATE SET
                        ma5 = EXCLUDED.ma5,
                        ema5 = EXCLUDED.ema5,
                        ma10 = EXCLUDED.ma10,
                        ema10 = EXCLUDED.ema10,
                        ma20 = EXCLUDED.ma20,
                        ema20 = EXCLUDED.ema20,
                        ma50 = EXCLUDED.ma50,
                        ma100 = EXCLUDED.ma100,
                        ma200 = EXCLUDED.ma200,
                        calc_at = CURRENT_TIMESTAMP
                """
                )

                conn.execute(
                    query,
                    {"symbol_id": symbol_id, "timeframe": timeframe, "ts": ts, **default_mas},
                )
                return True

        except Exception as e:
            logger.error(f"Error saving moving averages: {str(e)}")
            return False

    def validate_data_continuity(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """Validate data continuity for reliable indicator calculation"""
        if df.empty:
            return {"valid": False, "reason": "No data"}

        # 시간간격 설정
        timeframe_minutes = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": 1440,
            "5d": 7200,  # 5일 = 1440 * 5
            "1mo": 43200,  # 1개월 = 1440 * 30
            "3mo": 129600,  # 3개월 = 1440 * 90
        }

        expected_interval = timeframe_minutes.get(timeframe, 5)

        # 데이터 간격 분석
        time_diffs = df.index.to_series().diff().dt.total_seconds() / 60

        # 허용 범위 (정상 간격의 3배까지 허용)
        max_allowed_gap = expected_interval * 3
        large_gaps = time_diffs[time_diffs > max_allowed_gap]

        # 연속성 점수 계산
        continuity_score = (len(df) - len(large_gaps)) / len(df) * 100

        return {
            "valid": continuity_score >= 70,  # 70% 이상 연속성 요구 (80%에서 완화)
            "continuity_score": round(continuity_score, 2),
            "large_gaps": len(large_gaps),
            "total_points": len(df),
            "recommendation": (
                "good"
                if continuity_score >= 90
                else "acceptable" if continuity_score >= 70 else "poor"
            ),
        }

    def calculate_and_save(self, ticker: str, timeframe: str) -> Dict:
        """Calculate and save all indicators"""
        try:
            # Get symbol_id
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT id FROM symbols WHERE ticker = :ticker"),
                    {"ticker": ticker},
                ).fetchone()

                if not result:
                    return {
                        "ticker": ticker,
                        "timeframe": timeframe,
                        "status": "symbol_not_found",
                    }

                symbol_id = result[0]

            # Get candles (longer timeframes need more data for MA200)
            if timeframe in ["1d", "5d", "1mo", "3mo"]:
                df = self.get_candles_with_continuity(
                    symbol_id, timeframe, min_points=50, max_points=300
                )
            else:
                df = self.get_candles_with_continuity(symbol_id, timeframe)
            if df.empty:
                return {
                    "ticker": ticker,
                    "timeframe": timeframe,
                    "status": "no_candles",
                }

            # Get latest timestamp
            latest_ts = df.index[-1]

            # Validate data continuity
            continuity_info = self.validate_data_continuity(df, timeframe)
            if not continuity_info["valid"]:
                logger.warning(
                    f"Data continuity issue for {ticker}-{timeframe}: "
                    f"score={continuity_info['continuity_score']}%, "
                    f"but proceeding with partial calculation"
                )
                # 연속성이 낮아도 부분적으로 계산 진행
                # return {
                #     "ticker": ticker,
                #     "timeframe": timeframe,
                #     "status": "data_continuity_issue",
                #     "reason": continuity_info.get("reason", "Low continuity"),
                #     "continuity_score": continuity_info["continuity_score"],
                #     "large_gaps": continuity_info["large_gaps"],
                #     "total_points": continuity_info["total_points"],
                #     "recommendation": continuity_info["recommendation"],
                # }

            # Calculate indicators
            indicators = self.calculate_oscillators(df)
            mas = self.calculate_moving_averages(df)

            # Save to database
            indicators_saved = self.save_indicators(symbol_id, timeframe, latest_ts, indicators)
            mas_saved = self.save_moving_averages(symbol_id, timeframe, latest_ts, mas)

            return {
                "ticker": ticker,
                "timeframe": timeframe,
                "status": "success",
                "latest_ts": latest_ts.isoformat(),
                "indicators_saved": indicators_saved,
                "mas_saved": mas_saved,
                "continuity_info": continuity_info,
            }

        except Exception as e:
            logger.error(f"Error in calculate_and_save for {ticker}: {str(e)}")
            return {
                "ticker": ticker,
                "timeframe": timeframe,
                "status": "error",
                "error": str(e),
            }


def calculate_indicators(ticker: str, timeframe: str, **context) -> Dict:
    """Airflow task function to calculate indicators"""
    calculator = IndicatorCalculator()
    return calculator.calculate_and_save(ticker, timeframe)
