"""
Utility functions for ChartBeacon
"""

import os
import logging
from typing import List
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def get_active_symbols(database_url: str = None) -> List[str]:
    """Get list of active symbols from database"""
    database_url = database_url or os.getenv(
        "DATABASE_URL", "postgresql://chartbeacon:chartbeacon123@postgres:5432/chartbeacon"
    ).replace("postgresql+asyncpg://", "postgresql://")

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT ticker FROM symbols WHERE active = TRUE ORDER BY ticker")
            )
            tickers = [row[0] for row in result.fetchall()]

            if not tickers:
                # Fallback to environment variable if no symbols in DB
                logger.warning("No active symbols found in database, using environment variable")
                return os.getenv("TICKER_SYMBOLS", "005930.KS,AAPL,TSLA,SPY").split(",")

            logger.info(f"Found {len(tickers)} active symbols: {tickers}")
            return tickers

    except Exception as e:
        logger.error(f"Error getting active symbols from database: {str(e)}")
        # Fallback to environment variable
        return os.getenv("TICKER_SYMBOLS", "005930.KS,AAPL,TSLA,SPY").split(",")


def ensure_symbol_active(ticker: str, name: str = None, database_url: str = None) -> bool:
    """Ensure symbol exists and is active in database"""
    database_url = database_url or os.getenv(
        "DATABASE_URL", "postgresql://chartbeacon:chartbeacon123@postgres:5432/chartbeacon"
    ).replace("postgresql+asyncpg://", "postgresql://")

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            # Check if symbol exists
            result = conn.execute(
                text("SELECT id, active FROM symbols WHERE ticker = :ticker"), {"ticker": ticker}
            ).fetchone()

            if result:
                # Update to active if it exists but is inactive
                if not result[1]:  # if not active
                    conn.execute(
                        text("UPDATE symbols SET active = TRUE WHERE ticker = :ticker"),
                        {"ticker": ticker},
                    )
                    conn.commit()
                    logger.info(f"Activated existing symbol: {ticker}")
                return True
            else:
                # Create new active symbol
                if not name:
                    import yfinance as yf

                    try:
                        info = yf.Ticker(ticker).info
                        name = info.get("longName", info.get("shortName", ticker))
                    except:  # noqa: E722
                        name = ticker

                conn.execute(
                    text(
                        """
                        INSERT INTO symbols (ticker, name, active) 
                        VALUES (:ticker, :name, TRUE)
                    """
                    ),
                    {"ticker": ticker, "name": name},
                )
                conn.commit()
                logger.info(f"Created new active symbol: {ticker}")
                return True

    except Exception as e:
        logger.error(f"Error ensuring symbol {ticker} is active: {str(e)}")
        return False


def deactivate_symbol(ticker: str, database_url: str = None) -> bool:
    """Deactivate a symbol (stop tracking)"""
    database_url = database_url or os.getenv(
        "DATABASE_URL", "postgresql://chartbeacon:chartbeacon123@postgres:5432/chartbeacon"
    ).replace("postgresql+asyncpg://", "postgresql://")

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(
                text("UPDATE symbols SET active = FALSE WHERE ticker = :ticker"), {"ticker": ticker}
            )
            conn.commit()

            if result.rowcount > 0:
                logger.info(f"Deactivated symbol: {ticker}")
                return True
            else:
                logger.warning(f"Symbol not found: {ticker}")
                return False

    except Exception as e:
        logger.error(f"Error deactivating symbol {ticker}: {str(e)}")
        return False
