"""
Technical indicators scorer for ChartBeacon
"""

from datetime import datetime
from typing import Dict, Tuple, Optional
import logging
from sqlalchemy import create_engine, text
import os

logger = logging.getLogger(__name__)


class IndicatorScorer:
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://chartbeacon:chartbeacon123@postgres:5432/chartbeacon",
        ).replace("postgresql+asyncpg://", "postgresql://")
        self.engine = create_engine(self.database_url)

    def get_indicator_data(self, symbol_id: int, timeframe: str, ts: datetime) -> Dict:
        """Get indicator and moving average data for scoring"""
        with self.engine.connect() as conn:
            # Get indicators
            indicator_query = text(
                """
                SELECT * FROM indicators
                WHERE symbol_id = :symbol_id 
                AND timeframe = :timeframe
                AND ts = :ts
                LIMIT 1
            """
            )

            indicator_result = conn.execute(
                indicator_query,
                {"symbol_id": symbol_id, "timeframe": timeframe, "ts": ts},
            ).fetchone()

            # Get moving averages
            ma_query = text(
                """
                SELECT * FROM moving_avgs
                WHERE symbol_id = :symbol_id 
                AND timeframe = :timeframe
                AND ts = :ts
                LIMIT 1
            """
            )

            ma_result = conn.execute(
                ma_query, {"symbol_id": symbol_id, "timeframe": timeframe, "ts": ts}
            ).fetchone()

            # Get latest close price
            price_query = text(
                """
                SELECT close FROM candles_raw
                WHERE symbol_id = :symbol_id 
                AND timeframe = :timeframe
                AND ts = :ts
                LIMIT 1
            """
            )

            price_result = conn.execute(
                price_query, {"symbol_id": symbol_id, "timeframe": timeframe, "ts": ts}
            ).fetchone()

        return {
            "indicators": dict(indicator_result) if indicator_result else {},
            "moving_avgs": dict(ma_result) if ma_result else {},
            "close_price": float(price_result[0]) if price_result else None,
        }

    def score_oscillator(self, name: str, value: Optional[float]) -> str:
        """Score individual oscillator indicator"""
        if value is None:
            return "NEUTRAL"

        # RSI (14)
        if name == "rsi14":
            if value > 70:
                return "SELL"
            elif value < 30:
                return "BUY"
            else:
                return "NEUTRAL"

        # Stochastic %K
        elif name == "stoch_k":
            if value > 80:
                return "SELL"
            elif value < 20:
                return "BUY"
            else:
                return "NEUTRAL"

        # MACD vs Signal
        elif name == "macd_vs_signal":
            # value is (macd - signal)
            if value > 0:
                return "BUY"
            else:
                return "SELL"

        # ADX with DI
        elif name == "adx":
            # For ADX, we need additional DI values
            # Simplified: if ADX > 20, trend is strong
            if value < 20:
                return "NEUTRAL"
            else:
                # This is simplified - in real implementation,
                # we'd need +DI and -DI values
                return "NEUTRAL"

        # Williams %R
        elif name == "williams_r":
            if value > -20:
                return "SELL"
            elif value < -80:
                return "BUY"
            else:
                return "NEUTRAL"

        # CCI (14)
        elif name == "cci14":
            if value > 100:
                return "SELL"
            elif value < -100:
                return "BUY"
            else:
                return "NEUTRAL"

        # Highs/Lows
        elif name == "highlow14":
            if value > 0:
                return "BUY"
            elif value < 0:
                return "SELL"
            else:
                return "NEUTRAL"

        # Ultimate Oscillator
        elif name == "ultosc":
            if value > 70:
                return "SELL"
            elif value < 30:
                return "BUY"
            else:
                return "NEUTRAL"

        # ROC
        elif name == "roc":
            if value > 0:
                return "BUY"
            else:
                return "SELL"

        # Bull/Bear Power
        elif name == "bull_bear":
            if value > 0:
                return "BUY"
            else:
                return "SELL"

        else:
            return "NEUTRAL"

    def score_moving_average(self, ma_value: Optional[float], close_price: float) -> str:
        """Score moving average signal"""
        if ma_value is None or close_price is None:
            return "NEUTRAL"

        if close_price > ma_value:
            return "BUY"
        else:
            return "SELL"

    def calculate_scores(self, data: Dict) -> Tuple[int, int, int]:
        """Calculate buy, sell, neutral counts from indicators"""
        buy_count = 0
        sell_count = 0
        neutral_count = 0

        indicators = data.get("indicators", {})
        moving_avgs = data.get("moving_avgs", {})
        close_price = data.get("close_price")

        # Score oscillators
        oscillator_scores = []

        # RSI
        if "rsi14" in indicators:
            score = self.score_oscillator("rsi14", indicators["rsi14"])
            oscillator_scores.append(score)

        # Stochastic %K
        if "stoch_k" in indicators:
            score = self.score_oscillator("stoch_k", indicators["stoch_k"])
            oscillator_scores.append(score)

        # MACD vs Signal
        if "macd" in indicators and "macd_signal" in indicators:
            macd_diff = None
            if indicators["macd"] is not None and indicators["macd_signal"] is not None:
                macd_diff = float(indicators["macd"]) - float(indicators["macd_signal"])
            score = self.score_oscillator("macd_vs_signal", macd_diff)
            oscillator_scores.append(score)

        # CCI
        if "cci14" in indicators:
            score = self.score_oscillator("cci14", indicators["cci14"])
            oscillator_scores.append(score)

        # ROC
        if "roc" in indicators:
            score = self.score_oscillator("roc", indicators["roc"])
            oscillator_scores.append(score)

        # Bull/Bear Power
        if "bull_bear" in indicators:
            score = self.score_oscillator("bull_bear", indicators["bull_bear"])
            oscillator_scores.append(score)

        # Ultimate Oscillator
        if "ultosc" in indicators:
            score = self.score_oscillator("ultosc", indicators["ultosc"])
            oscillator_scores.append(score)

        # Count oscillator scores
        for score in oscillator_scores:
            if score == "BUY":
                buy_count += 1
            elif score == "SELL":
                sell_count += 1
            else:
                neutral_count += 1

        # Score moving averages
        ma_periods = {
            "ma5": "ma5",
            "ema5": "ema5",
            "ma10": "ma10",
            "ema10": "ema10",
            "ma20": "ma20",
            "ema20": "ema20",
            "ma50": "ma50",
            "ma100": "ma100",
            "ma200": "ma200",
        }

        for ma_key in ma_periods:
            if ma_key in moving_avgs and close_price:
                ma_value = moving_avgs[ma_key]
                if ma_value is not None:
                    score = self.score_moving_average(float(ma_value), close_price)
                    if score == "BUY":
                        buy_count += 1
                    elif score == "SELL":
                        sell_count += 1
                    else:
                        neutral_count += 1

        return buy_count, sell_count, neutral_count

    def determine_level(self, buy_cnt: int, sell_cnt: int, neutral_cnt: int) -> str:
        """Determine overall technical level"""
        total = buy_cnt + sell_cnt + neutral_cnt
        if total == 0:
            return "NEUTRAL"

        # Strong signals when >= 2/3 of indicators agree
        if buy_cnt >= (2 * total / 3):
            return "STRONG_BUY"
        elif sell_cnt >= (2 * total / 3):
            return "STRONG_SELL"
        elif buy_cnt > sell_cnt:
            return "BUY"
        elif sell_cnt > buy_cnt:
            return "SELL"
        else:
            return "NEUTRAL"

    def save_summary(
        self,
        symbol_id: int,
        timeframe: str,
        ts: datetime,
        buy_cnt: int,
        sell_cnt: int,
        neutral_cnt: int,
        level: str,
    ) -> bool:
        """Save summary to database"""
        try:
            with self.engine.connect() as conn:
                query = text(
                    """
                    INSERT INTO summary (
                        symbol_id, timeframe, ts,
                        buy_cnt, sell_cnt, neutral_cnt, level
                    ) VALUES (
                        :symbol_id, :timeframe, :ts,
                        :buy_cnt, :sell_cnt, :neutral_cnt, :level
                    )
                    ON CONFLICT (symbol_id, timeframe, ts)
                    DO UPDATE SET
                        buy_cnt = EXCLUDED.buy_cnt,
                        sell_cnt = EXCLUDED.sell_cnt,
                        neutral_cnt = EXCLUDED.neutral_cnt,
                        level = EXCLUDED.level,
                        scored_at = CURRENT_TIMESTAMP
                """
                )

                conn.execute(
                    query,
                    {
                        "symbol_id": symbol_id,
                        "timeframe": timeframe,
                        "ts": ts,
                        "buy_cnt": buy_cnt,
                        "sell_cnt": sell_cnt,
                        "neutral_cnt": neutral_cnt,
                        "level": level,
                    },
                )
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error saving summary: {str(e)}")
            return False

    def score_and_save(self, ticker: str, timeframe: str) -> Dict:
        """Score indicators and save summary"""
        try:
            # Get symbol_id and latest timestamp
            with self.engine.connect() as conn:
                # Get symbol
                symbol_result = conn.execute(
                    text("SELECT id FROM symbols WHERE ticker = :ticker"),
                    {"ticker": ticker},
                ).fetchone()

                if not symbol_result:
                    return {
                        "ticker": ticker,
                        "timeframe": timeframe,
                        "status": "symbol_not_found",
                    }

                symbol_id = symbol_result[0]

                # Get latest indicator timestamp
                ts_result = conn.execute(
                    text(
                        """
                        SELECT MAX(ts) FROM indicators
                        WHERE symbol_id = :symbol_id AND timeframe = :timeframe
                    """
                    ),
                    {"symbol_id": symbol_id, "timeframe": timeframe},
                ).fetchone()

                if not ts_result or not ts_result[0]:
                    return {
                        "ticker": ticker,
                        "timeframe": timeframe,
                        "status": "no_indicators",
                    }

                latest_ts = ts_result[0]

            # Get indicator data
            data = self.get_indicator_data(symbol_id, timeframe, latest_ts)

            # Calculate scores
            buy_cnt, sell_cnt, neutral_cnt = self.calculate_scores(data)

            # Determine level
            level = self.determine_level(buy_cnt, sell_cnt, neutral_cnt)

            # Save summary
            saved = self.save_summary(
                symbol_id, timeframe, latest_ts, buy_cnt, sell_cnt, neutral_cnt, level
            )

            return {
                "ticker": ticker,
                "timeframe": timeframe,
                "status": "success",
                "latest_ts": latest_ts.isoformat(),
                "buy_cnt": buy_cnt,
                "sell_cnt": sell_cnt,
                "neutral_cnt": neutral_cnt,
                "level": level,
                "saved": saved,
            }

        except Exception as e:
            logger.error(f"Error in score_and_save for {ticker}: {str(e)}")
            return {
                "ticker": ticker,
                "timeframe": timeframe,
                "status": "error",
                "error": str(e),
            }


def score_indicators(ticker: str, timeframe: str, **context) -> Dict:
    """Airflow task function to score indicators"""
    scorer = IndicatorScorer()
    return scorer.score_and_save(ticker, timeframe)
