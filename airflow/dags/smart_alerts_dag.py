import pendulum
import logging
import os
import requests  # Discord webhook
from typing import List, Dict, Any
import pandas as pd

from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.exceptions import AirflowSkipException

logger = logging.getLogger(__name__)

# --- Environment Variables & Settings ---
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
POSTGRES_CONN_ID = "postgres_default"  # Airflow UI Connection ID

# Alert Conditions
PRICE_CHANGE_THRESHOLD_PERCENT = 3.0  # %
VOLUME_SPIKE_FACTOR = 2.0  # Times average volume
VOLUME_AVG_PERIOD = 20  # Number of candles for volume average

# Bollinger Bands Settings
BBANDS_PERIOD = 20
BBANDS_STD_DEV = 2

# Support/Resistance Settings
SR_LOOKBACK_PERIOD = 50  # Number of candles to look back for dynamic S/R

# Longer Timeframe Analysis Settings
LONG_TIMEFRAME = "1h"
LONG_TIMEFRAME_CANDLES_LIMIT = 65  # EMA60 계산 등을 위해 충분히
LONG_EMA_SHORT_PERIOD = 20
LONG_EMA_LONG_PERIOD = 60

# Discord Embed Colors
COLOR_GREEN = 3066993  # 상승 관련
COLOR_RED = 15158332  # 하락 관련
COLOR_BLUE = 3447003  # 정보/중립 (거래량, S/R 터치 등)
COLOR_ORANGE = 15105652  # 주의
COLOR_PURPLE = 10181046  # BBands
COLOR_GOLD = 15844367  # 강화된 신호
COLOR_SILVER = 12370112  # 중립/정보성 신호
COLOR_BRONZE = 10040115  # 약한 신호 또는 주의

# --- Helper Functions for Longer Timeframe Analysis ---


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    return prices.ewm(span=period, adjust=False).mean()


def get_longer_timeframe_data_sync(
    ticker: str, timeframe: str, pg_hook: PostgresHook, limit: int
) -> pd.DataFrame:
    """지정된 상위 시간봉의 OHLCV 및 주요 지표를 동기적으로 가져옵니다."""
    sql = """
    SELECT ts, open, high, low, close, volume
    FROM candles_raw c
    JOIN symbols s ON c.symbol_id = s.id
    WHERE s.ticker = %(ticker)s AND c.timeframe = %(timeframe)s
    ORDER BY c.ts DESC
    LIMIT %(limit)s;
    """
    try:
        records = pg_hook.get_records(
            sql, parameters={"ticker": ticker, "timeframe": timeframe, "limit": limit}
        )
        if not records or len(records) < 1:
            return pd.DataFrame()

        df = pd.DataFrame(records, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df.dropna(
            subset=["open", "high", "low", "close"], inplace=True
        )  # 주요 가격 데이터 없는 행 제거
        df = df.iloc[::-1].reset_index(drop=True)

        if not df.empty and len(df) >= LONG_EMA_SHORT_PERIOD:  # 최소 EMA 계산 가능 조건
            df[f"ema{LONG_EMA_SHORT_PERIOD}"] = calculate_ema(df["close"], LONG_EMA_SHORT_PERIOD)
            if len(df) >= LONG_EMA_LONG_PERIOD:
                df[f"ema{LONG_EMA_LONG_PERIOD}"] = calculate_ema(df["close"], LONG_EMA_LONG_PERIOD)
        return df
    except Exception as e:
        logger.error(f"DB error fetching {timeframe} data for {ticker}: {e}", exc_info=True)
        return pd.DataFrame()


def analyze_long_term_context_for_signal(
    short_term_signal_type: str,
    short_term_price: float,  # 5분봉 알림 발생 시점의 가격
    long_tf_df: pd.DataFrame,
) -> Dict[str, Any]:
    """상위 시간봉 데이터를 기반으로 단기 신호의 컨텍스트를 분석합니다."""
    context_summary = {
        "signal_strength": "neutral",
        "message": "상위 시간봉 데이터 부족 또는 분석 불가",
        "color": COLOR_SILVER,
    }

    if (
        long_tf_df.empty
        or len(long_tf_df) < 1
        or f"ema{LONG_EMA_SHORT_PERIOD}" not in long_tf_df.columns
    ):
        return context_summary

    latest_long_tf_candle = long_tf_df.iloc[-1]
    long_ema_short = latest_long_tf_candle.get(f"ema{LONG_EMA_SHORT_PERIOD}")
    long_ema_long = latest_long_tf_candle.get(f"ema{LONG_EMA_LONG_PERIOD}")  # 없을 수도 있음
    long_close = latest_long_tf_candle.get("close")

    long_term_trend_is_up = None
    trend_desc = "혼조세"
    if long_close is not None and long_ema_short is not None:
        if long_ema_long is not None:  # 긴 EMA도 있을 경우
            if long_close > long_ema_short and long_ema_short > long_ema_long:
                long_term_trend_is_up = True
                trend_desc = (
                    f"명확한 상승 추세 (종가>{LONG_EMA_SHORT_PERIOD}EMA>{LONG_EMA_LONG_PERIOD}EMA)"
                )
            elif long_close < long_ema_short and long_ema_short < long_ema_long:
                long_term_trend_is_up = False
                trend_desc = (
                    f"명확한 하락 추세 (종가<{LONG_EMA_SHORT_PERIOD}EMA<{LONG_EMA_LONG_PERIOD}EMA)"
                )
            elif long_close > long_ema_short:  # 교차는 없지만 단기 EMA 위
                long_term_trend_is_up = "moderate_up"
                trend_desc = f"단기 상승 우위 (종가>{LONG_EMA_SHORT_PERIOD}EMA)"
            elif long_close < long_ema_short:  # 교차는 없지만 단기 EMA 아래
                long_term_trend_is_up = "moderate_down"
                trend_desc = f"단기 하락 우위 (종가<{LONG_EMA_SHORT_PERIOD}EMA)"
        else:  # 짧은 EMA만 있을 경우
            if long_close > long_ema_short:
                long_term_trend_is_up = "moderate_up"
                trend_desc = f"단기 상승 우위 (종가>{LONG_EMA_SHORT_PERIOD}EMA)"
            elif long_close < long_ema_short:
                long_term_trend_is_up = "moderate_down"
                trend_desc = f"단기 하락 우위 (종가<{LONG_EMA_SHORT_PERIOD}EMA)"

    base_message = f"{LONG_TIMEFRAME.upper()} 기준: {trend_desc}."

    is_bullish_signal = (
        short_term_signal_type.endswith("_bullish")
        or "upper_break" in short_term_signal_type
        or "support_touch" in short_term_signal_type
    )
    is_bearish_signal = (
        short_term_signal_type.endswith("_bearish")
        or "lower_break" in short_term_signal_type
        or "resistance_touch" in short_term_signal_type
    )

    if is_bullish_signal:
        if long_term_trend_is_up is True:
            context_summary["signal_strength"] = "strong"
            context_summary["message"] = f"🔥 {base_message} 5분봉 매수 관련 신호와 일치!"
            context_summary["color"] = COLOR_GOLD
        elif long_term_trend_is_up == "moderate_up":
            context_summary["signal_strength"] = "moderate"
            context_summary["message"] = f"👍 {base_message} 5분봉 매수 관련 신호와 부합."
            context_summary["color"] = COLOR_GREEN
        elif long_term_trend_is_up is False or long_term_trend_is_up == "moderate_down":
            context_summary["signal_strength"] = "weak"
            context_summary["message"] = f"⚠️ {base_message} 5분봉 매수 관련 신호와 반대! 주의 필요."
            context_summary["color"] = COLOR_BRONZE
        else:  # neutral
            context_summary["message"] = f"➡️ {base_message} 신중한 접근 필요."
            context_summary["color"] = COLOR_SILVER

    elif is_bearish_signal:
        if long_term_trend_is_up is False:
            context_summary["signal_strength"] = "strong"
            context_summary["message"] = f"🔥 {base_message} 5분봉 매도 관련 신호와 일치!"
            context_summary["color"] = COLOR_GOLD
        elif long_term_trend_is_up == "moderate_down":
            context_summary["signal_strength"] = "moderate"
            context_summary["message"] = f"👎 {base_message} 5분봉 매도 관련 신호와 부합."
            context_summary["color"] = COLOR_RED
        elif long_term_trend_is_up is True or long_term_trend_is_up == "moderate_up":
            context_summary["signal_strength"] = "weak"
            context_summary["message"] = f"⚠️ {base_message} 5분봉 매도 관련 신호와 반대! 주의 필요."
            context_summary["color"] = COLOR_BRONZE
        else:  # neutral
            context_summary["message"] = f"➡️ {base_message} 신중한 접근 필요."
            context_summary["color"] = COLOR_SILVER

    elif short_term_signal_type == "volume_spike":
        context_summary["signal_strength"] = "info"
        vol_message_parts = [base_message]
        if "volume" in long_tf_df.columns and len(long_tf_df["volume"]) >= 5:
            avg_long_vol = (
                long_tf_df["volume"].iloc[-6:-1].mean() if len(long_tf_df["volume"]) > 1 else 0
            )
            curr_long_vol = long_tf_df["volume"].iloc[-1]
            if avg_long_vol > 0 and curr_long_vol > avg_long_vol * 1.5:
                vol_message_parts.append(
                    f"{LONG_TIMEFRAME.upper()}에서도 거래량 증가세 관찰됨 (현재 {curr_long_vol:,.0f} vs 평균 {avg_long_vol:,.0f})."
                )
            elif avg_long_vol > 0:
                vol_message_parts.append(
                    f"{LONG_TIMEFRAME.upper()} 거래량은 평이함 (현재 {curr_long_vol:,.0f} vs 평균 {avg_long_vol:,.0f})."
                )
            else:
                vol_message_parts.append(f"{LONG_TIMEFRAME.upper()} 거래량 데이터 분석 중.")
        context_summary["message"] = " ".join(vol_message_parts)
        context_summary["color"] = COLOR_BLUE  # 거래량은 중립적 파란색

    # S/R의 경우, 해당 레벨이 장기 EMA와 가까운지 등으로 강화 가능
    if "sr_" in short_term_signal_type and (
        long_ema_short is not None or long_ema_long is not None
    ):
        sr_level_proximity_message = ""
        if (
            long_ema_short and abs(short_term_price - long_ema_short) / short_term_price < 0.005
        ):  # 0.5% 이내
            sr_level_proximity_message = f"해당 레벨은 {LONG_TIMEFRAME.upper()} EMA{LONG_EMA_SHORT_PERIOD}({long_ema_short:,.2f})과 근접."
        if long_ema_long and abs(short_term_price - long_ema_long) / short_term_price < 0.005:
            proximity_detail = f"{LONG_TIMEFRAME.upper()} EMA{LONG_EMA_LONG_PERIOD}({long_ema_long:,.2f})과도 근접."
            sr_level_proximity_message += (
                f" ({'또한 ' if sr_level_proximity_message else ''}{proximity_detail})"
            )

        if sr_level_proximity_message:
            context_summary["message"] += f" {sr_level_proximity_message}"
            if (
                context_summary["signal_strength"] == "neutral"
                or context_summary["signal_strength"] == "info"
            ):  # 추세 중립이어도 강화
                context_summary["signal_strength"] = "moderate"
                # 색상은 기존 bullish/bearish 판단에 따르거나, S/R은 BLUE 유지

    return context_summary


# --- 기존 알림 확인 함수들 수정 (각 함수 내부에 컨텍스트 분석 로직 추가) ---


def get_active_symbols_task() -> List[str]:
    """Fetches active stock tickers from the database."""
    pg_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    sql = "SELECT ticker FROM symbols WHERE active = TRUE;"
    try:
        records = pg_hook.get_records(sql)
    except Exception as e:
        logger.error(f"Failed to fetch active symbols from DB: {e}", exc_info=True)
        return []  # Return empty list on DB error to prevent downstream failures

    if not records:
        logger.info("No active symbols found.")
        return []

    active_tickers = [record[0] for record in records]
    logger.info(f"Active symbols: {active_tickers}")
    return active_tickers


def send_discord_alert(payload: Dict[str, Any], ticker: str, alert_type: str):
    """Sends an alert to Discord via webhook."""
    if not DISCORD_WEBHOOK_URL or DISCORD_WEBHOOK_URL == "YOUR_DISCORD_WEBHOOK_URL_HERE":
        logger.warning(
            f"DISCORD_WEBHOOK_URL is not set or is a placeholder. Skipping Discord notification for {ticker} ({alert_type})."
        )
        return

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(
            f"Discord alert sent for {ticker} ({alert_type}). Status: {response.status_code}"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Discord alert for {ticker} ({alert_type}): {e}")


def check_price_alert_for_symbol(ticker: str, pg_hook: PostgresHook):
    """Checks for significant price changes for a given ticker."""
    sql = """
    SELECT c.ts, c.close
    FROM candles_raw c
    JOIN symbols s ON c.symbol_id = s.id
    WHERE s.ticker = %(ticker)s AND c.timeframe = '5m'
    ORDER BY c.ts DESC
    LIMIT 2;
    """
    try:
        candles = pg_hook.get_records(sql, parameters={"ticker": ticker})
    except Exception as e:
        logger.error(f"DB error fetching candles for price alert ({ticker}): {e}", exc_info=True)
        return

    if not candles or len(candles) < 2:
        logger.info(
            f"Not enough 5m candle data for {ticker} to check price alert (found {len(candles) if candles else 0})."
        )
        return

    latest_candle_ts, latest_close = candles[0]
    previous_candle_ts, previous_close = candles[1]

    try:
        latest_close = float(latest_close)
        previous_close = float(previous_close)
    except (ValueError, TypeError) as e:
        logger.error(
            f"Invalid price data for {ticker}: {e}. Latest: {latest_close}, Previous: {previous_close}"
        )
        return

    if previous_close == 0:
        logger.warning(
            f"Previous close price is 0 for {ticker} at {previous_candle_ts}. Cannot calculate change."
        )
        return

    price_change_percent = ((latest_close - previous_close) / previous_close) * 100

    alert_trigger = None
    alert_description_prefix = ""
    color = COLOR_ORANGE  # Default color

    if price_change_percent >= PRICE_CHANGE_THRESHOLD_PERCENT:
        alert_trigger = "급등"
        alert_description_prefix = f"🚀 **가격 급등! {price_change_percent:+.2f}%**"
        color = COLOR_GREEN
    elif price_change_percent <= -PRICE_CHANGE_THRESHOLD_PERCENT:
        alert_trigger = "급락"
        alert_description_prefix = f"📉 **가격 급락! {price_change_percent:+.2f}%**"
        color = COLOR_RED

    if alert_trigger:
        long_tf_df = get_longer_timeframe_data_sync(
            ticker, LONG_TIMEFRAME, pg_hook, LONG_TIMEFRAME_CANDLES_LIMIT
        )
        short_term_signal_type = f"price_{'bullish' if alert_trigger == '급등' else 'bearish'}"
        context_analysis = analyze_long_term_context_for_signal(
            short_term_signal_type, latest_close, long_tf_df
        )

        logger.info(
            f"PRICE ALERT for {ticker}: {alert_trigger} ({price_change_percent:+.2f}%) Price: {latest_close}, Prev: {previous_close}"
        )

        candle_time_str = pendulum.instance(latest_candle_ts).strftime("%Y-%m-%d %H:%M:%S UTC")

        explanation = ""
        action_suggestion = ""
        if alert_trigger == "급등":
            explanation = "단기적으로 매수세가 강하게 유입되었음을 의미할 수 있습니다."
            action_suggestion = "추격 매수보다는 조정 시 매수 또는 단기 저항선 확인."
        elif alert_trigger == "급락":
            explanation = "단기적으로 매도세가 강하게 나타났음을 의미할 수 있습니다."
            action_suggestion = "섣부른 매수보다는 지지 확인 후 접근 또는 단기 반등 노리기."

        payload = {
            "username": f"ChartBeacon Price Alert ({context_analysis.get('signal_strength','N/A').upper()})",
            "embeds": [
                {
                    "title": f"🚨 [{ticker}] 5분봉 가격 변동: {alert_trigger}",
                    "description": alert_description_prefix,
                    "color": context_analysis.get("color", color),
                    "fields": [
                        {"name": "현재가", "value": f"{latest_close:,.2f}", "inline": True},
                        {
                            "name": "변동률",
                            "value": f"{price_change_percent:+.2f}%",
                            "inline": True,
                        },
                        {"name": "기준 시간 (5분봉)", "value": candle_time_str, "inline": False},
                        {
                            "name": f"📊 {LONG_TIMEFRAME.upper()} 컨텍스트",
                            "value": context_analysis.get("message", "분석 정보 없음"),
                            "inline": False,
                        },
                        {"name": "💡 5분봉 의미", "value": explanation, "inline": False},
                        {"name": "🤔 대응 전략 제안", "value": action_suggestion, "inline": False},
                        {
                            "name": "🔍 추가 확인",
                            "value": "일봉 차트에서 현재 추세 및 주요 지지/저항선을 함께 확인하세요.",
                            "inline": False,
                        },
                    ],
                    "timestamp": pendulum.now("UTC").to_iso8601_string(),
                    "footer": {"text": "투자는 항상 신중하게! 본 정보는 참고용입니다."},
                }
            ],
        }
        send_discord_alert(payload, ticker, f"Price {alert_trigger}")
    else:
        logger.debug(
            f"No significant 5m price change for {ticker}. Change: {price_change_percent:.2f}%"
        )


def check_volume_alert_for_symbol(ticker: str, pg_hook: PostgresHook):
    """Checks for significant volume spikes for a given ticker."""
    sql = """
    SELECT c.ts, c.volume
    FROM candles_raw c
    JOIN symbols s ON c.symbol_id = s.id
    WHERE s.ticker = %(ticker)s AND c.timeframe = '5m'
    ORDER BY c.ts DESC
    LIMIT %(limit)s;
    """
    try:
        candles = pg_hook.get_records(
            sql, parameters={"ticker": ticker, "limit": VOLUME_AVG_PERIOD + 1}
        )
    except Exception as e:
        logger.error(f"DB error fetching candles for volume alert ({ticker}): {e}", exc_info=True)
        return

    if (
        not candles or len(candles) < VOLUME_AVG_PERIOD + 1
    ):  # Need at least one current and enough for average
        logger.info(
            f"Not enough 5m candle data for {ticker} to check volume alert (found {len(candles) if candles else 0}, need {VOLUME_AVG_PERIOD + 1})."
        )
        return

    latest_candle_ts, latest_volume_val = candles[0]
    previous_volumes_val = [candle[1] for candle in candles[1:]]

    try:
        latest_volume = float(latest_volume_val)
        previous_volumes = [float(v) for v in previous_volumes_val]
    except (ValueError, TypeError) as e:
        logger.error(
            f"Invalid volume data for {ticker}: {e}. Latest: {latest_volume_val}, Previous: {previous_volumes_val}"
        )
        return

    if not previous_volumes:
        logger.info(f"Not enough previous 5m volume data for {ticker} to calculate average.")
        return

    avg_volume = sum(previous_volumes) / len(previous_volumes)
    volume_factor = 0.0

    if avg_volume == 0:
        if latest_volume > 0:
            volume_factor = float("inf")  # Represent as a very large spike
            logger.info(
                f"Average 5m volume is 0 for {ticker}, current volume is {latest_volume}. Treating as a spike."
            )
        else:
            logger.debug(f"Average 5m volume and current volume are 0 for {ticker}. No spike.")
            return  # No alert if both are zero
    else:
        volume_factor = latest_volume / avg_volume

    alert_trigger = None
    if volume_factor >= VOLUME_SPIKE_FACTOR:
        alert_trigger = "거래량 급증"

    if alert_trigger:
        long_tf_df = get_longer_timeframe_data_sync(
            ticker, LONG_TIMEFRAME, pg_hook, LONG_TIMEFRAME_CANDLES_LIMIT
        )
        context_analysis = analyze_long_term_context_for_signal(
            "volume_spike", latest_volume, long_tf_df
        )

        logger.info(
            f"VOLUME ALERT for {ticker}: Factor {volume_factor:.2f}, Current: {latest_volume}, Avg: {avg_volume:.2f}"
        )
        desc_detail = f"{volume_factor:.2f}배 증가" + (
            " (평균 0 대비)" if avg_volume == 0 and latest_volume > 0 else ""
        )
        desc_main = f"📈 **{alert_trigger}! {desc_detail}**"
        explanation = (
            "평소보다 많은 관심 또는 특정 주체의 거래 발생 가능성. 가격 변동 신뢰도 증가/감소 요인."
        )
        action_suggestion = (
            "거래량 증가 방향으로의 추세 지속 또는 반전 가능성 염두. 가격 움직임과 함께 판단."
        )
        candle_time_str = pendulum.instance(latest_candle_ts).strftime("%Y-%m-%d %H:%M:%S UTC")

        payload = {
            "username": "ChartBeacon Volume Alert",
            "embeds": [
                {
                    "title": f"📊 [{ticker}] 5분봉 {alert_trigger}",
                    "description": desc_main,
                    "color": context_analysis.get("color", COLOR_BLUE),
                    "fields": [
                        {"name": "현재 거래량", "value": f"{latest_volume:,.0f}", "inline": True},
                        {
                            "name": f"{VOLUME_AVG_PERIOD}봉 평균",
                            "value": f"{avg_volume:,.0f}",
                            "inline": True,
                        },
                        {"name": "기준 시간 (5분봉)", "value": candle_time_str, "inline": False},
                        {
                            "name": f"📊 {LONG_TIMEFRAME.upper()} 컨텍스트",
                            "value": context_analysis.get("message", "분석 정보 없음"),
                            "inline": False,
                        },
                        {"name": "💡 5분봉 의미", "value": explanation, "inline": False},
                        {"name": "🤔 대응 전략 제안", "value": action_suggestion, "inline": False},
                    ],
                    "timestamp": pendulum.now("UTC").to_iso8601_string(),
                    "footer": {"text": "투자는 항상 신중하게! 본 정보는 참고용입니다."},
                }
            ],
        }
        send_discord_alert(payload, ticker, "Volume spike")
    else:
        logger.debug(
            f"No significant 5m volume spike for {ticker}. Factor: {volume_factor:.2f if avg_volume > 0 else 'N/A'}"
        )


def check_bollinger_band_alert_for_symbol(ticker: str, pg_hook: PostgresHook):
    """Checks for Bollinger Band breakouts for a given ticker."""
    sql = """
    SELECT c.ts, c.close
    FROM candles_raw c
    JOIN symbols s ON c.symbol_id = s.id
    WHERE s.ticker = %(ticker)s AND c.timeframe = '5m'
    ORDER BY c.ts DESC
    LIMIT %(limit)s;
    """
    try:
        candles_records = pg_hook.get_records(
            sql, parameters={"ticker": ticker, "limit": BBANDS_PERIOD + 5}
        )
    except Exception as e:
        logger.error(f"DB error fetching candles for BBands alert ({ticker}): {e}", exc_info=True)
        return

    if not candles_records or len(candles_records) < BBANDS_PERIOD:
        logger.info(
            f"Not enough 5m candle data for {ticker} to calculate BBands (found {len(candles_records) if candles_records else 0}, need {BBANDS_PERIOD})."
        )
        return

    # Convert to DataFrame, newest first
    df = pd.DataFrame(candles_records, columns=["ts", "close"])
    df["ts"] = pd.to_datetime(df["ts"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df.dropna(subset=["close"], inplace=True)  # Drop rows where close is NaN after conversion

    if len(df) < BBANDS_PERIOD:  # Check again after dropping NaNs
        logger.info(
            f"Not enough valid 5m candle data for {ticker} after NaN drop (found {len(df)}, need {BBANDS_PERIOD})."
        )
        return

    # Data is newest first, reverse for typical TA calculations (oldest first)
    df = df.iloc[::-1].reset_index(drop=True)

    # Calculate Bollinger Bands
    df["sma"] = df["close"].rolling(window=BBANDS_PERIOD).mean()
    df["stddev"] = df["close"].rolling(window=BBANDS_PERIOD).std()
    df["upper_band"] = df["sma"] + (BBANDS_STD_DEV * df["stddev"])
    df["lower_band"] = df["sma"] - (BBANDS_STD_DEV * df["stddev"])

    if (
        df.empty
        or len(df) < 1
        or pd.isna(df.iloc[-1]["close"])
        or pd.isna(df.iloc[-1]["upper_band"])
        or pd.isna(df.iloc[-1]["lower_band"])
    ):
        logger.info(
            f"Could not calculate BBands for {ticker}, possibly due to insufficient data or NaNs in recent bands."
        )
        return

    latest_candle = df.iloc[-1]  # Current candle (most recent)
    # Previous candle's relation to bands can be checked with df.iloc[-2] if needed for "breakout from within" logic

    latest_ts = latest_candle["ts"]
    latest_close = latest_candle["close"]
    upper_band = latest_candle["upper_band"]
    lower_band = latest_candle["lower_band"]
    sma = latest_candle["sma"]

    alert_type = None
    description = None
    color = COLOR_PURPLE

    # Check for breakout: current close is outside the bands.
    # More robust: check if *previous* close was inside, and current is outside.
    # For now, simple "outside" check for the latest point.
    if latest_close > upper_band:
        alert_type = "BB 상단 돌파"
        description = "📈 **볼린저밴드 상단 돌파!**"
        color = COLOR_GREEN
    elif latest_close < lower_band:
        alert_type = "BB 하단 돌파"
        description = "📉 **볼린저밴드 하단 돌파!**"
        color = COLOR_RED

    if alert_type:
        long_tf_df = get_longer_timeframe_data_sync(
            ticker, LONG_TIMEFRAME, pg_hook, LONG_TIMEFRAME_CANDLES_LIMIT
        )
        short_term_signal_type = (
            f"bb_{'upper_break' if alert_type == 'BB 상단 돌파' else 'lower_break'}"
        )
        context_analysis = analyze_long_term_context_for_signal(
            short_term_signal_type, latest_close, long_tf_df
        )

        logger.info(
            f"BBANDS ALERT for {ticker}: {alert_type}. Price: {latest_close:.2f}, Upper: {upper_band:.2f}, Lower: {lower_band:.2f}"
        )

        candle_time_str = pendulum.instance(latest_ts).strftime("%Y-%m-%d %H:%M:%S UTC")

        explanation = ""
        action_suggestion = ""
        if alert_type == "BB 상단 돌파":
            explanation = "가격이 단기적으로 과매수 구간에 진입했거나, 강한 상승 추세의 시작일 수 있습니다. 변동성 확대를 의미합니다."
            action_suggestion = "돌파 후 지지 확인 또는 추세 추종."
        elif alert_type == "BB 하단 돌파":
            explanation = "가격이 단기적으로 과매도 구간에 진입했거나, 강한 하락 추세의 시작일 수 있습니다. 변동성 확대를 의미합니다."
            action_suggestion = "돌파 후 저항 확인 또는 기술적 반등 고려."

        payload = {
            "username": f"ChartBeacon BB Alert ({context_analysis.get('signal_strength','N/A').upper()})",
            "embeds": [
                {
                    "title": f"🟣 [{ticker}] 5분봉 {alert_type}",
                    "description": description,
                    "color": context_analysis.get("color", color),
                    "fields": [
                        {"name": "현재가", "value": f"{latest_close:,.2f}", "inline": True},
                        {"name": "상단밴드", "value": f"{upper_band:,.2f}", "inline": True},
                        {"name": "하단밴드", "value": f"{lower_band:,.2f}", "inline": True},
                        {"name": "중심선(SMA)", "value": f"{sma:,.2f}", "inline": True},
                        {"name": "기준 시간 (5분봉)", "value": candle_time_str, "inline": False},
                        {
                            "name": f"📊 {LONG_TIMEFRAME.upper()} 컨텍스트",
                            "value": context_analysis.get("message", "분석 정보 없음"),
                            "inline": False,
                        },
                        {"name": "💡 5분봉 의미", "value": explanation, "inline": False},
                        {"name": "🤔 대응 전략 제안", "value": action_suggestion, "inline": False},
                    ],
                    "timestamp": pendulum.now("UTC").to_iso8601_string(),
                    "footer": {"text": "투자는 항상 신중하게! 본 정보는 참고용입니다."},
                }
            ],
        }
        send_discord_alert(payload, ticker, alert_type)
    else:
        logger.debug(
            f"No BBands breakout for {ticker}. Price: {latest_close:.2f}, Upper: {upper_band:.2f}, Lower: {lower_band:.2f}"
        )


def check_support_resistance_alert_for_symbol(ticker: str, pg_hook: PostgresHook):
    """Checks for touches or breaks of dynamic support/resistance levels."""
    sql = """
    SELECT c.ts, c.high, c.low, c.close -- Added close for context
    FROM candles_raw c
    JOIN symbols s ON c.symbol_id = s.id
    WHERE s.ticker = %(ticker)s AND c.timeframe = '5m'
    ORDER BY c.ts DESC
    LIMIT %(limit)s;
    """
    try:
        # Fetch SR_LOOKBACK_PERIOD for S/R calculation, and one more (current candle)
        candles_records = pg_hook.get_records(
            sql, parameters={"ticker": ticker, "limit": SR_LOOKBACK_PERIOD + 1}
        )
    except Exception as e:
        logger.error(f"DB error fetching candles for S/R alert ({ticker}): {e}", exc_info=True)
        return

    if not candles_records or len(candles_records) <= 1:  # Need at least current and some history
        logger.info(
            f"Not enough 5m candle data for {ticker} to check S/R (found {len(candles_records) if candles_records else 0}, need >1)."
        )
        return

    df = pd.DataFrame(candles_records, columns=["ts", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"])
    for col in ["high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.dropna(inplace=True)

    if len(df) <= 1:  # Need current and some lookback data
        logger.info(
            f"Not enough valid 5m candle data for {ticker} after NaN drop for S/R (found {len(df)})."
        )
        return

    latest_candle = df.iloc[0]  # Newest candle is at the top of the records from DB
    historical_candles = df.iloc[
        1 : SR_LOOKBACK_PERIOD + 1
    ]  # The lookback period, excluding the current one for S/R calculation

    if historical_candles.empty:
        logger.info(f"Not enough historical data for S/R calculation for {ticker} (after latest).")
        return

    dynamic_support = historical_candles["low"].min()
    dynamic_resistance = historical_candles["high"].max()

    latest_ts = latest_candle["ts"]
    latest_high = latest_candle["high"]
    latest_low = latest_candle["low"]
    latest_close = latest_candle["close"]

    alert_type = None
    description = None
    level_touched = None
    color = COLOR_BLUE

    # Check for touch/break. Alert if current low hits/breaks support OR current high hits/breaks resistance.
    # Could add a small tolerance (e.g., within 0.1% of the level)
    if latest_low <= dynamic_support:
        alert_type = "지지선 터치/이탈"
        description = f"🛡️ **지지선({dynamic_support:,.2f}) 터치 또는 하향 이탈!**"
        level_touched = f"지지 {dynamic_support:,.2f}"
        color = COLOR_RED  # Potentially bearish
    elif latest_high >= dynamic_resistance:
        alert_type = "저항선 터치/돌파"
        description = f"⚔️ **저항선({dynamic_resistance:,.2f}) 터치 또는 상향 돌파!**"
        level_touched = f"저항 {dynamic_resistance:,.2f}"
        color = COLOR_GREEN  # Potentially bullish

    if alert_type:
        long_tf_df = get_longer_timeframe_data_sync(
            ticker, LONG_TIMEFRAME, pg_hook, LONG_TIMEFRAME_CANDLES_LIMIT
        )
        short_term_signal_type = (
            f"sr_{'support_touch' if '지지선' in alert_type else 'resistance_touch'}"
        )
        context_analysis = analyze_long_term_context_for_signal(
            short_term_signal_type, latest_close, long_tf_df
        )

        logger.info(
            f"S/R ALERT for {ticker}: {alert_type}. Low: {latest_low:.2f}, High: {latest_high:.2f}, Support: {dynamic_support:.2f}, Resistance: {dynamic_resistance:.2f}"
        )

        candle_time_str = pendulum.instance(latest_ts).strftime("%Y-%m-%d %H:%M:%S UTC")

        explanation = ""
        action_suggestion = ""
        if "지지선" in alert_type:
            explanation = f"최근 {SR_LOOKBACK_PERIOD}개 봉의 최저가({dynamic_support:,.2f}) 부근에 도달했습니다. 단기적 반등 가능성이 있거나, 이탈 시 추가 하락이 나올 수 있습니다."
            action_suggestion = (
                "지지 여부 확인 (꼬리, 거래량). 이탈 시 손절 또는 관망. 반등 시 단기 매수 고려."
            )
        elif "저항선" in alert_type:
            explanation = f"최근 {SR_LOOKBACK_PERIOD}개 봉의 최고가({dynamic_resistance:,.2f}) 부근에 도달했습니다. 단기적 조정 가능성이 있거나, 돌파 시 추가 상승이 나올 수 있습니다."
            action_suggestion = (
                "저항 돌파 여부 확인 (거래량 동반). 돌파 시 추격 매수 고려, 실패 시 매도 또는 관망."
            )

        payload = {
            "username": f"ChartBeacon S/R Alert ({context_analysis.get('signal_strength','N/A').upper()})",
            "embeds": [
                {
                    "title": f"🛡️⚔️ [{ticker}] 5분봉 {alert_type}",
                    "description": description,
                    "color": context_analysis.get("color", color),
                    "fields": [
                        {"name": "현재 저가", "value": f"{latest_low:,.2f}", "inline": True},
                        {"name": "현재 고가", "value": f"{latest_high:,.2f}", "inline": True},
                        {"name": "현재 종가", "value": f"{latest_close:,.2f}", "inline": True},
                        {"name": "감지된 레벨", "value": level_touched, "inline": True},
                        {"name": "기준 시간 (5분봉)", "value": candle_time_str, "inline": False},
                        {
                            "name": f"📊 {LONG_TIMEFRAME.upper()} 컨텍스트",
                            "value": context_analysis.get("message", "분석 정보 없음"),
                            "inline": False,
                        },
                        {"name": "💡 5분봉 의미", "value": explanation, "inline": False},
                        {"name": "🤔 대응 전략 제안", "value": action_suggestion, "inline": False},
                    ],
                    "timestamp": pendulum.now("UTC").to_iso8601_string(),
                    "footer": {"text": "투자는 항상 신중하게! 본 정보는 참고용입니다."},
                }
            ],
        }
        send_discord_alert(payload, ticker, alert_type)
    else:
        logger.debug(
            f"No S/R touch/break for {ticker}. Low: {latest_low:.2f}, High: {latest_high:.2f}, Support: {dynamic_support:.2f}, Resistance: {dynamic_resistance:.2f}"
        )


def process_alerts_for_tickers_task(ti, alert_check_function_name_str: str, task_name_suffix: str):
    """Generic task to process alerts for a list of tickers using a specific check function by name."""
    active_tickers = ti.xcom_pull(task_ids="get_active_symbols_task_id")
    if not active_tickers:
        logger.info(f"No active symbols to process for {task_name_suffix} alerts.")
        raise AirflowSkipException(f"No active symbols found for {task_name_suffix}.")

    pg_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)

    # 문자열로 받은 함수 이름을 실제 함수 객체로 매핑
    alert_function_map = {
        "check_price_alert_for_symbol": check_price_alert_for_symbol,
        "check_volume_alert_for_symbol": check_volume_alert_for_symbol,
        "check_bollinger_band_alert_for_symbol": check_bollinger_band_alert_for_symbol,
        "check_support_resistance_alert_for_symbol": check_support_resistance_alert_for_symbol,
    }
    alert_check_function = alert_function_map.get(alert_check_function_name_str)

    if not alert_check_function:
        logger.error(f"Unknown alert check function name: {alert_check_function_name_str}")
        return

    for ticker in active_tickers:
        try:
            alert_check_function(ticker, pg_hook)  # pg_hook 전달
        except Exception as e:
            logger.error(
                f"Error processing {task_name_suffix} alert for {ticker}: {e}", exc_info=True
            )


with DAG(
    dag_id="smart_alerts_5m_v1",
    start_date=pendulum.datetime(2024, 1, 1, tz="Asia/Seoul"),
    schedule="*/5 * * * *",
    catchup=False,
    tags=["smart-alerts", "filtered", "5m", "1h-context"],
    doc_md="""
    ### 스마트 알림 DAG (5분 주기, 1시간봉 컨텍스트 필터링)
    - **목표**: 활성 심볼에 대해 5분봉 기준 주요 변동 사항을 감지하고, 1시간봉 데이터를 통해 컨텍스트를 분석하여 필터링된 알림을 Discord로 전송.
    - **실행 주기**: 매 5분.
    - **주요 로직**:
        1.  `get_active_symbols_task_id`: DB에서 활성 심볼 목록 조회.
        2.  각 심볼에 대해 5분봉 알림 조건 확인 (가격, 거래량, BB, S/R).
        3.  조건 발생 시, 해당 심볼의 1시간봉 데이터 (OHLCV, EMA20, EMA60) 조회.
        4.  1시간봉 컨텍스트(추세, 주요 이평선과의 관계)를 분석하여 5분봉 신호의 강도 평가.
        5.  필터링된 (또는 강화/약화 정보가 추가된) 알림을 Discord로 전송.
    - **알림 채널**: Discord (환경변수 `DISCORD_WEBHOOK_URL` 필요).
    - **DB 연결**: Airflow Connection `postgres_default`.
    """,
) as dag:

    get_active_symbols_op = PythonOperator(
        task_id="get_active_symbols_task_id",
        python_callable=get_active_symbols_task,
    )

    process_price_alerts_op = PythonOperator(
        task_id="process_price_alerts_task_id",
        python_callable=process_alerts_for_tickers_task,
        op_kwargs={
            "alert_check_function_name_str": "check_price_alert_for_symbol",
            "task_name_suffix": "price",
        },
        provide_context=True,
    )

    process_volume_alerts_op = PythonOperator(
        task_id="process_volume_alerts_task_id",
        python_callable=process_alerts_for_tickers_task,
        op_kwargs={
            "alert_check_function_name_str": "check_volume_alert_for_symbol",
            "task_name_suffix": "volume",
        },
        provide_context=True,
    )

    process_bbands_alerts_op = PythonOperator(
        task_id="process_bbands_alerts_task_id",
        python_callable=process_alerts_for_tickers_task,
        op_kwargs={
            "alert_check_function_name_str": "check_bollinger_band_alert_for_symbol",
            "task_name_suffix": "bbands",
        },
        provide_context=True,
    )

    process_sr_alerts_op = PythonOperator(
        task_id="process_sr_alerts_task_id",
        python_callable=process_alerts_for_tickers_task,
        op_kwargs={
            "alert_check_function_name_str": "check_support_resistance_alert_for_symbol",
            "task_name_suffix": "sr",
        },
        provide_context=True,
    )

    get_active_symbols_op >> [
        process_price_alerts_op,
        process_volume_alerts_op,
        process_bbands_alerts_op,
        process_sr_alerts_op,
    ]
