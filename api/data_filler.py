"""
데이터 채우기 모듈
Yahoo Finance에서 데이터를 가져와서 캔들, 지표, 요약 데이터를 계산하고 저장
"""

import yfinance as yf
import pandas as pd
import pandas_ta as ta
import asyncpg
from datetime import datetime, timezone
from typing import List, Optional
import logging
import os

# 로거 설정
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# 데이터베이스 연결 설정 (asyncpg 직접 연결용)
# 환경에 따른 DATABASE_URL 설정
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
if ENVIRONMENT == "production" or os.getenv("DOCKER_ENV"):
    # 도커 환경에서는 postgres 호스트명 사용
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://chartbeacon:chartbeacon123@postgres:5432/chartbeacon"
    )
else:
    # 로컬 개발환경에서는 localhost 사용
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://chartbeacon:chartbeacon123@localhost:5432/chartbeacon"
    )
# asyncpg 직접 연결을 위해 prefix 제거
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def fill_historical_data(ticker: str, timeframes: List[str] = None, period: str = "max"):
    """
    특정 종목의 과거 데이터를 채우는 메인 함수

    Args:
        ticker: 종목 코드
        timeframes: 타임프레임 리스트 ['5m', '1h', '1d', '5d', '1mo', '3mo']
        period: 데이터 기간 (max = 최대한 긴 기간으로 MA200 등 충분한 데이터 확보)
    """
    if timeframes is None:
        timeframes = ["5m", "1h", "1d", "5d", "1mo", "3mo"]

    logger.info(f"🚀 Starting data fill for {ticker}, timeframes: {timeframes}, period: {period}")

    try:
        # 데이터베이스 연결
        conn = await asyncpg.connect(DATABASE_URL)

        # 심볼 ID 조회
        symbol_id = await get_symbol_id(conn, ticker)
        if not symbol_id:
            logger.error(f"Symbol {ticker} not found in database")
            return

        for timeframe in timeframes:
            logger.info(f"Processing {ticker} - {timeframe}")

            # 1. Yahoo Finance에서 데이터 가져오기
            df = fetch_yahoo_data(ticker, timeframe, period)
            if df is None or df.empty:
                logger.warning(f"No data found for {ticker} - {timeframe}")
                continue

            # 2. 캔들 데이터 저장
            await save_candle_data(conn, symbol_id, timeframe, df)

            # 3. 지표 계산 및 저장
            await calculate_and_save_indicators(conn, symbol_id, timeframe, df)

            # 4. 이동평균 계산 및 저장
            await calculate_and_save_moving_averages(conn, symbol_id, timeframe, df)

            # 5. 요약 계산 및 저장
            await calculate_and_save_summary(conn, symbol_id, timeframe, df)

            logger.info(f"Completed processing {ticker} - {timeframe}")

        await conn.close()
        logger.info(f"✅ Data fill completed for {ticker}")

    except Exception as e:
        logger.error(f"❌ Error filling data for {ticker}: {str(e)}")
        raise


def fetch_yahoo_data(ticker: str, timeframe: str, period: str = "max") -> Optional[pd.DataFrame]:
    """
    Yahoo Finance에서 데이터 가져오기
    시간대 처리: 거래소별 현지 시간으로 받아서 UTC로 변환하여 DB에 저장
    """
    try:
        # 타임프레임별 interval 매핑
        interval_map = {
            "5m": "5m",
            "1h": "1h",
            "1d": "1d",
            "5d": "5d",
            "1mo": "1mo",
            "3mo": "3mo",
        }

        interval = interval_map.get(timeframe)
        if not interval:
            logger.error(f"Unsupported timeframe: {timeframe}")
            return None

        # 단기 데이터는 기간 제한이 있음, 장기 데이터는 충분한 기간 확보
        if timeframe == "5m":
            period = "60d"  # 5분: 최대 60일
        elif timeframe == "1h":
            period = "730d"  # 1시간: 최대 730일
        elif timeframe in ["5d", "1mo", "3mo"]:
            # 장기 데이터는 더 긴 기간 사용하여 MA200까지 충분히 확보
            if timeframe == "5d":
                period = "10y"  # 5일봉: 10년 (MA200 확보)
            elif timeframe == "1mo":
                period = "max"  # 1월봉: 최대 기간 (MA200 확보)
            elif timeframe == "3mo":
                period = "max"  # 3월봉: 최대 기간 (MA50, MA200 확보)
        elif timeframe == "1d":
            # 1일봉도 충분한 기간 확보
            if period == "max":
                period = "max"
            else:
                period = "5y"  # 기본적으로 5년

        logger.info(f"Fetching {ticker} data: interval={interval}, period={period}")

        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)

        if df.empty:
            logger.warning(f"No data returned for {ticker}")
            return None

        # 시간대 처리: Yahoo Finance는 거래소별 현지 시간으로 제공
        # 모든 데이터를 UTC로 통일하여 DB에 저장
        logger.info(f"Processing timezone for {ticker} - Original timezone: {df.index.tz}")
        logger.info(f"Index sample: {df.index[:3].tolist() if len(df.index) > 0 else 'Empty'}")

        try:
            # Yahoo Finance 데이터의 시간대 처리
            if df.index.tz is not None:
                # 이미 timezone 정보가 있으면 UTC로 변환
                logger.info(f"Converting from {df.index.tz} to UTC")
                df.index = df.index.tz_convert("UTC")
            else:
                # timezone 정보가 없는 경우 거래소별로 추정
                if ticker.endswith(".KS"):
                    # 한국 주식: KST(Asia/Seoul)로 가정하고 UTC로 변환
                    logger.info("Korean stock: Localizing to Asia/Seoul then converting to UTC")
                    df.index = df.index.tz_localize("Asia/Seoul").tz_convert("UTC")
                else:
                    # 기타 주식: NYSE/NASDAQ 등은 대부분 EST/EDT로 가정
                    # 하지만 실제로는 Yahoo Finance가 이미 적절한 시간대로 제공하므로 UTC로 가정
                    logger.info("Non-Korean stock: Localizing to UTC")
                    df.index = df.index.tz_localize("UTC")

            logger.info(f"After timezone processing - Index timezone: {df.index.tz}")

        except Exception as tz_error:
            logger.error(f"Timezone conversion error for {ticker}: {tz_error}")
            logger.error(f"Error type: {type(tz_error)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

            # 에러 발생 시 fallback: timezone 정보 제거하고 UTC로 설정
            try:
                if hasattr(df.index, "tz_localize"):
                    df.index = df.index.tz_localize(None).tz_localize("UTC")
                    logger.info("Fallback: Removed timezone and re-localized to UTC")
                else:
                    df.index = pd.to_datetime(df.index, utc=True)
                    logger.info("Fallback: Converted to UTC using pd.to_datetime")
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                logger.warning("Proceeding without timezone conversion")

        df.columns = df.columns.str.lower()
        df = df.reset_index()

        # 디버깅: 실제 컬럼명 확인
        logger.info(f"DataFrame columns after reset_index: {list(df.columns)}")

        # 인덱스 컬럼명이 다를 수 있으므로 확인 후 변경
        if "date" in df.columns:
            df.rename(columns={"date": "ts"}, inplace=True)
        elif "datetime" in df.columns:
            df.rename(columns={"datetime": "ts"}, inplace=True)
        elif "Datetime" in df.columns:
            df.rename(columns={"Datetime": "ts"}, inplace=True)
        else:
            # 첫 번째 컬럼이 시간 컬럼일 가능성
            first_col = df.columns[0]
            logger.warning(
                f"Expected 'date' or 'datetime' column not found. Using first column: {first_col}"
            )
            df.rename(columns={first_col: "ts"}, inplace=True)

        # 한국 주식의 경우 정규장 시간만 필터링 (5분, 1시간봉만)
        if ticker.endswith(".KS") and timeframe in ["5m", "1h"]:
            logger.info(f"Filtering regular trading hours for Korean stock {ticker}")

            # ts 컬럼이 이미 UTC 시간이므로 KST로 변환해서 필터링
            ts_series = pd.to_datetime(df["ts"])
            
            # UTC에서 KST(+9시간)로 변환
            if ts_series.dt.tz is not None:
                df_ts_kst = ts_series.dt.tz_convert("Asia/Seoul")
            else:
                df_ts_kst = ts_series.dt.tz_localize("UTC").dt.tz_convert("Asia/Seoul")

            df["hour"] = df_ts_kst.dt.hour
            df["minute"] = df_ts_kst.dt.minute

            # 한국 정규장 시간: 09:00 ~ 15:30 (15:30 포함)
            regular_hours = (
                ((df["hour"] == 9) & (df["minute"] >= 0))
                | ((df["hour"] >= 10) & (df["hour"] <= 14))
                | ((df["hour"] == 15) & (df["minute"] <= 30))
            )

            original_count = len(df)
            df = df[regular_hours].drop(["hour", "minute"], axis=1)
            filtered_count = len(df)

            logger.info(f"Regular hours filtering: {original_count} -> {filtered_count} records")

            if filtered_count == 0:
                logger.warning("All data filtered out! This might indicate timezone issues.")

        logger.info(f"Final DataFrame columns: {list(df.columns)}")
        logger.info(f"Fetched {len(df)} records for {ticker} - {timeframe}")
        return df

    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {str(e)}")
        return None


async def get_symbol_id(conn: asyncpg.Connection, ticker: str) -> Optional[int]:
    """
    심볼 ID 조회
    """
    result = await conn.fetchrow("SELECT id FROM symbols WHERE ticker = $1", ticker)
    return result["id"] if result else None


async def save_candle_data(
    conn: asyncpg.Connection, symbol_id: int, timeframe: str, df: pd.DataFrame
):
    """
    캔들 데이터를 데이터베이스에 저장 (UPSERT)
    """
    logger.info(f"Saving {len(df)} candle records for symbol_id={symbol_id}, timeframe={timeframe}")

    # 배치 insert를 위한 데이터 준비
    records = []
    for _, row in df.iterrows():
        records.append(
            (
                symbol_id,
                timeframe,
                row["ts"],
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                float(row["volume"]),
                datetime.now(timezone.utc),  # ingested_at은 현재 UTC 시간
            )
        )

    # UPSERT 쿼리
    query = """
        INSERT INTO candles_raw (symbol_id, timeframe, ts, open, high, low, close, volume, ingested_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (symbol_id, timeframe, ts) 
        DO UPDATE SET 
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            ingested_at = EXCLUDED.ingested_at
    """

    await conn.executemany(query, records)
    logger.info(f"Saved {len(records)} candle records")


async def calculate_and_save_indicators(
    conn: asyncpg.Connection, symbol_id: int, timeframe: str, df: pd.DataFrame
):
    """
    기술적 지표 계산 및 저장
    """
    logger.info(f"Calculating indicators for symbol_id={symbol_id}, timeframe={timeframe}")

    # 데이터 길이 확인
    if len(df) < 30:
        logger.warning(f"Insufficient data for indicators calculation: {len(df)} rows")
        return

    # 지표 계산 (안전한 처리)
    try:
        # RSI
        df["rsi14"] = ta.rsi(df["close"], length=14)

        # Stochastic
        stoch = ta.stoch(df["high"], df["low"], df["close"], k=9, d=6)
        if stoch is not None and not stoch.empty:
            df["stoch_k"] = stoch.get("STOCHk_9_6_3", pd.Series(index=df.index, dtype=float))
            df["stoch_d"] = stoch.get("STOCHd_9_6_3", pd.Series(index=df.index, dtype=float))
        else:
            df["stoch_k"] = pd.Series(index=df.index, dtype=float)
            df["stoch_d"] = pd.Series(index=df.index, dtype=float)

        # MACD
        macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            df["macd"] = macd.get("MACD_12_26_9", pd.Series(index=df.index, dtype=float))
            df["macd_signal"] = macd.get("MACDs_12_26_9", pd.Series(index=df.index, dtype=float))
        else:
            df["macd"] = pd.Series(index=df.index, dtype=float)
            df["macd_signal"] = pd.Series(index=df.index, dtype=float)

        # ADX
        adx = ta.adx(df["high"], df["low"], df["close"], length=14)
        if adx is not None and not adx.empty:
            df["adx14"] = adx.get("ADX_14", pd.Series(index=df.index, dtype=float))
        else:
            df["adx14"] = pd.Series(index=df.index, dtype=float)

        # CCI
        df["cci14"] = ta.cci(df["high"], df["low"], df["close"], length=14)
        if df["cci14"] is None:
            df["cci14"] = pd.Series(index=df.index, dtype=float)

        # ATR
        df["atr14"] = ta.atr(df["high"], df["low"], df["close"], length=14)
        if df["atr14"] is None:
            df["atr14"] = pd.Series(index=df.index, dtype=float)

        # Williams %R
        df["willr14"] = ta.willr(df["high"], df["low"], df["close"], length=14)
        if df["willr14"] is None:
            df["willr14"] = pd.Series(index=df.index, dtype=float)

        # Ultimate Oscillator
        df["ultosc"] = ta.uo(df["high"], df["low"], df["close"])
        if df["ultosc"] is None:
            df["ultosc"] = pd.Series(index=df.index, dtype=float)

        # ROC
        df["roc"] = ta.roc(df["close"], length=12)
        if df["roc"] is None:
            df["roc"] = pd.Series(index=df.index, dtype=float)

        # Bull/Bear Power
        ema13 = ta.ema(df["close"], length=13)
        if ema13 is not None:
            df["bull_bear"] = df["high"] - ema13
        else:
            df["bull_bear"] = pd.Series(index=df.index, dtype=float)

        # 높은/낮은 지표 (High - Low)
        df["highlow14"] = df["high"].rolling(14).max() - df["low"].rolling(14).min()

    except Exception as e:
        logger.error(f"Error calculating indicators: {str(e)}")
        # 실패 시 빈 Series로 채우기
        for col in [
            "rsi14",
            "stoch_k",
            "stoch_d",
            "macd",
            "macd_signal",
            "adx14",
            "cci14",
            "atr14",
            "willr14",
            "ultosc",
            "roc",
            "bull_bear",
            "highlow14",
        ]:
            if col not in df.columns:
                df[col] = pd.Series(index=df.index, dtype=float)

    # 데이터 저장
    records = []
    for _, row in df.iterrows():
        if pd.isna(row["rsi14"]):  # 초기 몇 개 행은 지표가 계산되지 않음
            continue

        records.append(
            (
                symbol_id,
                timeframe,
                row["ts"],
                safe_float(row.get("rsi14")),
                safe_float(row.get("stoch_k")),
                safe_float(row.get("stoch_d")),
                safe_float(row.get("macd")),
                safe_float(row.get("macd_signal")),
                safe_float(row.get("adx14")),
                safe_float(row.get("cci14")),
                safe_float(row.get("atr14")),
                safe_float(row.get("willr14")),
                safe_float(row.get("highlow14")),
                safe_float(row.get("ultosc")),
                safe_float(row.get("roc")),
                safe_float(row.get("bull_bear")),
                datetime.now(timezone.utc),  # calc_at은 현재 UTC 시간
            )
        )

    if records:
        query = """
            INSERT INTO indicators (
                symbol_id, timeframe, ts, rsi14, stoch_k, stoch_d, 
                macd, macd_signal, adx14, cci14, atr14, willr14, highlow14, 
                ultosc, roc, bull_bear, calc_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
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
                willr14 = EXCLUDED.willr14,
                highlow14 = EXCLUDED.highlow14,
                ultosc = EXCLUDED.ultosc,
                roc = EXCLUDED.roc,
                bull_bear = EXCLUDED.bull_bear,
                calc_at = EXCLUDED.calc_at
        """

        await conn.executemany(query, records)
        logger.info(f"Saved {len(records)} indicator records")


async def calculate_and_save_moving_averages(
    conn: asyncpg.Connection, symbol_id: int, timeframe: str, df: pd.DataFrame
):
    """
    이동평균 계산 및 저장
    """
    logger.info(f"Calculating moving averages for symbol_id={symbol_id}, timeframe={timeframe}")

    # 이동평균 계산
    df["ma5"] = ta.sma(df["close"], length=5)
    df["ema5"] = ta.ema(df["close"], length=5)
    df["ma10"] = ta.sma(df["close"], length=10)
    df["ema10"] = ta.ema(df["close"], length=10)
    df["ma20"] = ta.sma(df["close"], length=20)
    df["ema20"] = ta.ema(df["close"], length=20)
    df["ma50"] = ta.sma(df["close"], length=50)
    df["ma100"] = ta.sma(df["close"], length=100)
    df["ma200"] = ta.sma(df["close"], length=200)

    # 데이터 저장
    records = []
    for _, row in df.iterrows():
        if pd.isna(row["ma5"]):  # 초기 몇 개 행은 이동평균이 계산되지 않음
            continue

        records.append(
            (
                symbol_id,
                timeframe,
                row["ts"],
                safe_float(row.get("ma5")),
                safe_float(row.get("ema5")),
                safe_float(row.get("ma10")),
                safe_float(row.get("ema10")),
                safe_float(row.get("ma20")),
                safe_float(row.get("ema20")),
                safe_float(row.get("ma50")),
                safe_float(row.get("ma100")),
                safe_float(row.get("ma200")),
                datetime.now(timezone.utc),  # calc_at은 현재 UTC 시간
            )
        )

    if records:
        query = """
            INSERT INTO moving_avgs (
                symbol_id, timeframe, ts, ma5, ema5, ma10, ema10, 
                ma20, ema20, ma50, ma100, ma200, calc_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
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
                calc_at = EXCLUDED.calc_at
        """

        await conn.executemany(query, records)
        logger.info(f"Saved {len(records)} moving average records")


async def calculate_and_save_summary(
    conn: asyncpg.Connection, symbol_id: int, timeframe: str, df: pd.DataFrame
):
    """
    요약 점수 계산 및 저장
    """
    logger.info(f"Calculating summary for symbol_id={symbol_id}, timeframe={timeframe}")

    # 최신 200개 행만 처리 (충분한 데이터가 있는 구간)
    df_recent = df.tail(200).copy()

    records = []
    for _, row in df_recent.iterrows():
        # 지표 기반 시그널 계산
        signals = calculate_signals(row)

        buy_cnt = sum(1 for s in signals if s == "BUY")
        sell_cnt = sum(1 for s in signals if s == "SELL")
        neutral_cnt = sum(1 for s in signals if s == "NEUTRAL")

        # 최종 레벨 결정
        total_signals = buy_cnt + sell_cnt + neutral_cnt
        if total_signals == 0:
            level = "NEUTRAL"
        elif buy_cnt >= (total_signals * 2 // 3):
            level = "STRONG_BUY"
        elif buy_cnt > sell_cnt:
            level = "BUY"
        elif sell_cnt >= (total_signals * 2 // 3):
            level = "STRONG_SELL"
        elif sell_cnt > buy_cnt:
            level = "SELL"
        else:
            level = "NEUTRAL"

        records.append(
            (
                symbol_id,
                timeframe,
                row["ts"],
                buy_cnt,
                sell_cnt,
                neutral_cnt,
                level,
                datetime.now(timezone.utc),  # scored_at은 현재 UTC 시간
            )
        )

    if records:
        query = """
            INSERT INTO summary (
                symbol_id, timeframe, ts, buy_cnt, sell_cnt, 
                neutral_cnt, level, scored_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (symbol_id, timeframe, ts) 
            DO UPDATE SET 
                buy_cnt = EXCLUDED.buy_cnt,
                sell_cnt = EXCLUDED.sell_cnt,
                neutral_cnt = EXCLUDED.neutral_cnt,
                level = EXCLUDED.level,
                scored_at = EXCLUDED.scored_at
        """

        await conn.executemany(query, records)
        logger.info(f"Saved {len(records)} summary records")


def calculate_signals(row) -> List[str]:
    """
    개별 행의 지표 값을 기반으로 시그널 계산
    """
    signals = []

    # RSI
    if pd.notna(row.get("rsi14")):
        if row["rsi14"] > 70:
            signals.append("SELL")
        elif row["rsi14"] < 30:
            signals.append("BUY")
        else:
            signals.append("NEUTRAL")

    # Stochastic
    if pd.notna(row.get("stoch_k")):
        if row["stoch_k"] > 80:
            signals.append("SELL")
        elif row["stoch_k"] < 20:
            signals.append("BUY")
        else:
            signals.append("NEUTRAL")

    # MACD
    if pd.notna(row.get("macd")) and pd.notna(row.get("macd_signal")):
        if row["macd"] > row["macd_signal"]:
            signals.append("BUY")
        elif row["macd"] < row["macd_signal"]:
            signals.append("SELL")
        else:
            signals.append("NEUTRAL")

    # CCI
    if pd.notna(row.get("cci14")):
        if row["cci14"] > 100:
            signals.append("BUY")
        elif row["cci14"] < -100:
            signals.append("SELL")
        else:
            signals.append("NEUTRAL")

    # Williams %R
    if pd.notna(row.get("willr14")):
        if row["willr14"] > -20:
            signals.append("SELL")
        elif row["willr14"] < -80:
            signals.append("BUY")
        else:
            signals.append("NEUTRAL")

    # ROC
    if pd.notna(row.get("roc")):
        if row["roc"] > 0:
            signals.append("BUY")
        elif row["roc"] < 0:
            signals.append("SELL")
        else:
            signals.append("NEUTRAL")

    # 이동평균 시그널들
    ma_signals = []
    for ma_col in ["ma5", "ema5", "ma10", "ema10", "ma20", "ema20", "ma50", "ma100", "ma200"]:
        if pd.notna(row.get(ma_col)) and pd.notna(row.get("close")):
            if row["close"] > row[ma_col]:
                ma_signals.append("BUY")
            elif row["close"] < row[ma_col]:
                ma_signals.append("SELL")
            else:
                ma_signals.append("NEUTRAL")

    signals.extend(ma_signals)
    return signals


def safe_float(value) -> Optional[float]:
    """
    안전한 float 변환 (NaN 처리)
    """
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
