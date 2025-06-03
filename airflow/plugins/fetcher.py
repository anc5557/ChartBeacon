"""
Yahoo Finance data fetcher for ChartBeacon
"""

import yfinance as yf
import pandas as pd
from typing import Dict
import logging
from sqlalchemy import create_engine, text
import os

logger = logging.getLogger(__name__)


class DataFetcher:
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://chartbeacon:chartbeacon123@postgres:5432/chartbeacon",
        ).replace("postgresql+asyncpg://", "postgresql://")
        self.engine = create_engine(self.database_url)

    def get_last_timestamp(self, symbol_id: int, timeframe: str):
        """Get the last timestamp for a symbol and timeframe"""
        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT MAX(ts) 
                    FROM candles_raw 
                    WHERE symbol_id = :symbol_id AND timeframe = :timeframe
                """
                ),
                {"symbol_id": symbol_id, "timeframe": timeframe},
            ).fetchone()

            return result[0] if result and result[0] else None

    def calculate_missing_period(self, last_ts, timeframe: str) -> str:
        """Calculate the appropriate period to fetch missing data"""
        from datetime import datetime

        if not last_ts:
            # 첫 번째 데이터 수집
            if timeframe == "5m":
                return "7d"  # 7일
            elif timeframe == "1h":
                return "1mo"  # 1달
            elif timeframe == "1d":
                return "3mo"  # 3달
            elif timeframe == "5d":
                return "1y"  # 1년
            elif timeframe in ["1mo", "3mo"]:
                return "10y"  # 10년

        now = datetime.now()
        if isinstance(last_ts, str):
            last_ts = pd.to_datetime(last_ts)

        # 마지막 데이터 이후 경과 시간
        gap = now - last_ts.replace(tzinfo=None)

        if timeframe == "5m":
            if gap.days > 7:
                return "7d"  # 최대 7일
            elif gap.days > 1:
                return f"{gap.days}d"
            else:
                return "1d"
        elif timeframe == "1h":
            if gap.days > 30:
                return "1mo"  # 최대 1달
            elif gap.days > 5:
                return f"{gap.days}d"
            else:
                return "5d"
        elif timeframe == "1d":
            if gap.days > 90:
                return "3mo"  # 최대 3달
            elif gap.days > 30:
                return f"{gap.days}d"
            else:
                return "1mo"
        elif timeframe == "5d":
            if gap.days > 365:
                return "1y"  # 최대 1년
            elif gap.days > 90:
                return f"{gap.days}d"
            else:
                return "3mo"
        elif timeframe in ["1mo", "3mo"]:
            if gap.days > 3650:  # 10년
                return "10y"
            elif gap.days > 365:
                return f"{gap.days//30}mo"
            else:
                return "1y"

        return "1d"  # 기본값

    def fetch_candles(self, ticker: str, timeframe: str, period: str = None) -> pd.DataFrame:
        """Fetch OHLCV data from Yahoo Finance"""
        try:
            # period가 지정되지 않으면 기본값 사용
            if not period:
                if timeframe == "5m":
                    period = "1d"
                    interval = "5m"
                elif timeframe == "1h":
                    period = "5d"
                    interval = "1h"
                elif timeframe == "1d":
                    period = "1mo"
                    interval = "1d"
                elif timeframe == "5d":
                    period = "3mo"
                    interval = "5d"
                elif timeframe == "1mo":
                    period = "1y"
                    interval = "1mo"
                elif timeframe == "3mo":
                    period = "5y"
                    interval = "3mo"
                else:
                    raise ValueError(f"Unsupported timeframe: {timeframe}")
            else:
                # period가 지정된 경우 interval 매핑
                if timeframe == "5m":
                    interval = "5m"
                elif timeframe == "1h":
                    interval = "1h"
                elif timeframe == "1d":
                    interval = "1d"
                elif timeframe == "5d":
                    interval = "5d"
                elif timeframe == "1mo":
                    interval = "1mo"
                elif timeframe == "3mo":
                    interval = "3mo"
                else:
                    raise ValueError(f"Unsupported timeframe: {timeframe}")

            # Yahoo Finance에서 데이터 가져오기
            ticker_obj = yf.Ticker(ticker)
            df = ticker_obj.history(period=period, interval=interval)

            if df.empty:
                logger.warning(f"No data fetched for {ticker} {timeframe}")
                return pd.DataFrame()

            # 타임존 처리: yfinance가 반환하는 aware DatetimeIndex를 그대로 사용
            # 다음 라인들은 제거 또는 주석 처리:
            # if df.index.tz is not None:
            #     df.index = df.index.tz_convert("UTC")
            # df.index = pd.to_datetime(df.index).tz_localize(None)

            # pd.to_datetime을 호출하여 DatetimeIndex 타입을 확실히 하고, yfinance가 반환한 원본 시간대 유지
            df.index = pd.to_datetime(df.index)

            # 컬럼명 정리
            df = df.rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )

            # 필요한 컬럼만 선택
            df = df[["open", "high", "low", "close", "volume"]]

            logger.info(f"Fetched {len(df)} candles for {ticker} {timeframe} (period: {period})")
            return df

        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {str(e)}")
            return pd.DataFrame()

    def ensure_symbol_exists(self, ticker: str, name: str = None) -> int:
        """Ensure symbol exists in database and return symbol_id"""
        with self.engine.connect() as conn:
            # Check if symbol exists
            result = conn.execute(
                text("SELECT id FROM symbols WHERE ticker = :ticker"),
                {"ticker": ticker},
            ).fetchone()

            if result:
                return result[0]

            # Create new symbol
            if not name:
                # Try to get company name from yfinance
                try:
                    info = yf.Ticker(ticker).info
                    name = info.get("longName", info.get("shortName", ticker))
                except:  # noqa: E722
                    name = ticker

            with self.engine.begin() as trans_conn:
                result = trans_conn.execute(
                    text(
                        """
                        INSERT INTO symbols (ticker, name) 
                        VALUES (:ticker, :name) 
                        RETURNING id
                    """
                    ),
                    {"ticker": ticker, "name": name},
                )
                return result.fetchone()[0]

    def save_candles(self, ticker: str, timeframe: str, df: pd.DataFrame) -> int:
        """Save candles to database using UPSERT"""
        if df.empty:
            return 0

        # Get symbol_id
        symbol_id = self.ensure_symbol_exists(ticker)

        # Prepare data for insertion
        df_copy = df.copy()
        df_copy["symbol_id"] = symbol_id
        df_copy["timeframe"] = timeframe
        df_copy["ts"] = df_copy.index

        # Convert to records
        records = df_copy.to_dict("records")

        with self.engine.begin() as conn:
            # Use PostgreSQL UPSERT with executemany for better performance
            stmt = text(
                """
                INSERT INTO candles_raw (symbol_id, timeframe, ts, open, high, low, close, volume)
                VALUES (:symbol_id, :timeframe, :ts, :open, :high, :low, :close, :volume)
                ON CONFLICT (symbol_id, timeframe, ts) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    ingested_at = CURRENT_TIMESTAMP
            """
            )
            conn.execute(stmt, records)

            logger.info(f"Saved {len(records)} candles for {ticker} {timeframe}")
            return len(records)

    def fetch_and_save(self, ticker: str, timeframe: str, force_period: str = None) -> Dict:
        """Fetch data and save to database with automatic backfill"""
        logger.info(f"Starting fetch for {ticker} {timeframe}")

        # Get symbol_id first
        symbol_id = self.ensure_symbol_exists(ticker)

        # Always get last timestamp for backfill detection
        last_ts = self.get_last_timestamp(symbol_id, timeframe)

        # Determine period - check for missing data unless force_period is specified
        if force_period:
            period = force_period
            logger.info(f"Using forced period: {period}")
        else:
            # Check last timestamp to see if we need backfill
            period = self.calculate_missing_period(last_ts, timeframe)

        if last_ts:
            from datetime import datetime

            gap_days = (datetime.now() - last_ts.replace(tzinfo=None)).days
            logger.info(f"Last data: {last_ts}, Gap: {gap_days} days, Using period: {period}")
        else:
            logger.info(f"No existing data, fetching initial period: {period}")

        # Fetch data
        df = self.fetch_candles(ticker, timeframe, period)

        if df.empty:
            return {
                "ticker": ticker,
                "timeframe": timeframe,
                "status": "no_data",
                "records_saved": 0,
                "period_used": period,
            }

        # Save to database
        records_saved = self.save_candles(ticker, timeframe, df)

        return {
            "ticker": ticker,
            "timeframe": timeframe,
            "status": "success",
            "records_saved": records_saved,
            "latest_ts": df.index[-1].isoformat(),
            "period_used": period,
            "backfill_detected": last_ts is not None and period != "1d",
        }


def fetch_ticker_data(ticker: str, timeframe: str, **context) -> Dict:
    """Airflow task function to fetch data for a single ticker"""
    fetcher = DataFetcher()
    return fetcher.fetch_and_save(ticker, timeframe)
