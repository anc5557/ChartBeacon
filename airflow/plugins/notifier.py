"""
Discord notifier for ChartBeacon
"""

import requests
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from sqlalchemy import create_engine, text
import os

logger = logging.getLogger(__name__)


class DiscordNotifier:
    def __init__(self, webhook_url: str = None, database_url: str = None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://chartbeacon:chartbeacon123@postgres:5432/chartbeacon",
        ).replace("postgresql+asyncpg://", "postgresql://")
        self.engine = create_engine(self.database_url)

        # Discord embed colors
        self.colors = {
            "STRONG_BUY": 3066993,  # Green
            "BUY": 3447003,  # Light Green
            "NEUTRAL": 9807270,  # Gray
            "SELL": 15158332,  # Orange
            "STRONG_SELL": 10038562,  # Red
        }

    def get_level_changes(self, ticker: str, timeframe: str) -> Optional[Dict]:
        """Check if level has changed compared to previous summary"""
        with self.engine.connect() as conn:
            # Get the last two summaries
            query = text(
                """
                SELECT s.ts, s.level, s.buy_cnt, s.sell_cnt, s.neutral_cnt, sym.ticker
                FROM summary s
                JOIN symbols sym ON s.symbol_id = sym.id
                WHERE sym.ticker = :ticker AND s.timeframe = :timeframe
                ORDER BY s.ts DESC
                LIMIT 2
            """
            )

            results = conn.execute(query, {"ticker": ticker, "timeframe": timeframe}).fetchall()

            if len(results) < 1:
                return None

            current = results[0]
            previous = results[1] if len(results) > 1 else None

            # Check if level changed
            if previous and current[1] != previous[1]:
                return {
                    "ticker": ticker,
                    "timeframe": timeframe,
                    "ts": current[0],
                    "current_level": current[1],
                    "previous_level": previous[1],
                    "buy_cnt": current[2],
                    "sell_cnt": current[3],
                    "neutral_cnt": current[4],
                }
            elif not previous:
                # First summary for this ticker/timeframe
                return {
                    "ticker": ticker,
                    "timeframe": timeframe,
                    "ts": current[0],
                    "current_level": current[1],
                    "previous_level": None,
                    "buy_cnt": current[2],
                    "sell_cnt": current[3],
                    "neutral_cnt": current[4],
                }

            return None

    def format_timeframe(self, timeframe: str) -> str:
        """Format timeframe for display"""
        tf_map = {"5m": "5분", "1h": "1시간", "1d": "1일"}
        return tf_map.get(timeframe, timeframe)

    def format_timestamp(self, ts: datetime) -> str:
        """Format an aware datetime object to KST string.
        Assumes the input 'ts' is an aware datetime object.
        """
        # KST 시간대 정의 (UTC+9)
        # Python 3.9+ 에서는 from zoneinfo import ZoneInfo; kst_tz = ZoneInfo("Asia/Seoul") 사용 권장
        kst_tz = timezone(timedelta(hours=9), name="KST")

        if ts.tzinfo is None:
            # 만약 어떤 이유로 naive datetime이 전달되면, UTC로 가정하고 KST로 변환 (이전 로직 유지)
            # 하지만 fetcher.py 수정으로 인해 DB에서 오는 값은 aware여야 함
            logger.warning(f"Received naive datetime in format_timestamp: {ts}. Assuming UTC.")
            aware_ts_utc = ts.replace(tzinfo=timezone.utc)
            ts_kst = aware_ts_utc.astimezone(kst_tz)
        else:
            # Aware datetime 객체를 KST로 변환
            ts_kst = ts.astimezone(kst_tz)

        return ts_kst.strftime("%Y-%m-%d %H:%M:%S KST")

    def send_notification(self, change_data: Dict) -> bool:
        """Send Discord notification for level change"""
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False

        try:
            ticker = change_data["ticker"]
            timeframe = self.format_timeframe(change_data["timeframe"])
            current_level = change_data["current_level"]
            previous_level = change_data["previous_level"]

            # Build title
            if previous_level:
                title = f"[{ticker}] {previous_level} → {current_level}"
            else:
                title = f"[{ticker}] {current_level} (첫 신호)"

            # Build embed
            embed = {
                "title": title,
                "color": self.colors.get(current_level, 9807270),
                "fields": [
                    {
                        "name": "Buy/Sell/Neutral",
                        "value": f"{change_data['buy_cnt']} / {change_data['sell_cnt']} / {change_data['neutral_cnt']}",
                        "inline": False,
                    },
                    {"name": "타임프레임", "value": timeframe, "inline": True},
                    {
                        "name": "시간",
                        "value": self.format_timestamp(change_data["ts"]),
                        "inline": True,
                    },
                ],
                "footer": {"text": "ChartBeacon Technical Analysis"},
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Send webhook
            payload = {"username": "Tech Alert", "embeds": [embed]}

            response = requests.post(self.webhook_url, json=payload, timeout=10)

            if response.status_code == 204:
                logger.info(f"Discord notification sent for {ticker} {current_level}")
                return True
            else:
                logger.error(f"Discord webhook failed: {response.status_code} {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error sending Discord notification: {str(e)}")
            return False

    def check_and_notify(self, ticker: str, timeframe: str) -> Dict:
        """Check for level changes and send notifications"""
        try:
            # Check for level changes
            change_data = self.get_level_changes(ticker, timeframe)

            if not change_data:
                return {"ticker": ticker, "timeframe": timeframe, "status": "no_change"}

            # Send notification
            sent = self.send_notification(change_data)

            return {
                "ticker": ticker,
                "timeframe": timeframe,
                "status": "notified" if sent else "notification_failed",
                "level_change": f"{change_data.get('previous_level', 'None')} → {change_data['current_level']}",
                "notification_sent": sent,
            }

        except Exception as e:
            logger.error(f"Error in check_and_notify for {ticker}: {str(e)}")
            return {
                "ticker": ticker,
                "timeframe": timeframe,
                "status": "error",
                "error": str(e),
            }


def check_and_notify_discord(ticker: str, timeframe: str, **context) -> Dict:
    """Airflow task function to check and notify level changes"""
    notifier = DiscordNotifier()
    return notifier.check_and_notify(ticker, timeframe)
