from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, func
from typing import Optional, List
import logging

from .models import Symbol, CandleRaw, Indicator, MovingAvg, Summary
from .schemas import SymbolCreate, SymbolUpdate

# 로거 설정
logger = logging.getLogger(__name__)


async def get_symbol_by_ticker(db: AsyncSession, ticker: str) -> Optional[Symbol]:
    """Get symbol by ticker"""
    result = await db.execute(select(Symbol).where(Symbol.ticker == ticker))
    return result.scalar_one_or_none()


async def get_symbols(db: AsyncSession, active_only: bool = False) -> List[Symbol]:
    """Get all symbols, optionally only active ones"""
    logger.info(f"get_symbols called with active_only={active_only}")
    query = select(Symbol)
    if active_only:
        logger.info("Adding active filter to query")
        query = query.where(Symbol.active)
    query = query.order_by(Symbol.ticker)

    logger.info(f"Executing query: {query}")
    result = await db.execute(query)
    symbols = list(result.scalars().all())
    logger.info(f"Query returned {len(symbols)} symbols")

    return symbols


async def get_active_symbols_list(db: AsyncSession) -> List[str]:
    """Get list of active symbol tickers"""
    result = await db.execute(select(Symbol.ticker).where(Symbol.active).order_by(Symbol.ticker))
    return [row[0] for row in result.fetchall()]


async def create_symbol(db: AsyncSession, symbol: SymbolCreate) -> Symbol:
    """Create new symbol"""
    db_symbol = Symbol(**symbol.model_dump())
    db.add(db_symbol)
    await db.commit()
    await db.refresh(db_symbol)
    return db_symbol


async def update_symbol(
    db: AsyncSession, ticker: str, symbol_update: SymbolUpdate
) -> Optional[Symbol]:
    """Update symbol"""
    # Get existing symbol
    db_symbol = await get_symbol_by_ticker(db, ticker)
    if not db_symbol:
        return None

    # Update fields
    update_data = symbol_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_symbol, field, value)

    await db.commit()
    await db.refresh(db_symbol)
    return db_symbol


async def activate_symbol(db: AsyncSession, ticker: str) -> Optional[Symbol]:
    """Activate a symbol"""
    return await update_symbol(db, ticker, SymbolUpdate(active=True))


async def deactivate_symbol(db: AsyncSession, ticker: str) -> Optional[Symbol]:
    """Deactivate a symbol"""
    return await update_symbol(db, ticker, SymbolUpdate(active=False))


async def get_latest_summary(
    db: AsyncSession, ticker: str, timeframe: str = "5m"
) -> Optional[Summary]:
    """Get latest summary for a symbol and timeframe"""
    result = await db.execute(
        select(Summary)
        .join(Symbol)
        .where(and_(Symbol.ticker == ticker, Summary.timeframe == timeframe))
        .order_by(desc(Summary.ts))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_summary_history(
    db: AsyncSession, ticker: str, timeframe: str = "5m", limit: int = 100
) -> List[Summary]:
    """Get summary history for a symbol and timeframe"""
    result = await db.execute(
        select(Summary)
        .join(Symbol)
        .where(and_(Symbol.ticker == ticker, Summary.timeframe == timeframe))
        .order_by(desc(Summary.ts))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_candles(
    db: AsyncSession, ticker: str, timeframe: str, limit: int = 1000
) -> List[CandleRaw]:
    """Get candles for a symbol and timeframe"""
    result = await db.execute(
        select(CandleRaw)
        .join(Symbol)
        .where(and_(Symbol.ticker == ticker, CandleRaw.timeframe == timeframe))
        .order_by(desc(CandleRaw.ts))
        .limit(limit)
    )

    candles = list(result.scalars().all())

    # Python에서 NaN 값을 가진 캔들 필터링
    valid_candles = []
    for candle in candles:
        try:
            # Decimal NaN 또는 None 체크
            if (
                candle.open is not None
                and not (hasattr(candle.open, "is_nan") and candle.open.is_nan())
                and candle.high is not None
                and not (hasattr(candle.high, "is_nan") and candle.high.is_nan())
                and candle.low is not None
                and not (hasattr(candle.low, "is_nan") and candle.low.is_nan())
                and candle.close is not None
                and not (hasattr(candle.close, "is_nan") and candle.close.is_nan())
            ):
                valid_candles.append(candle)
        except Exception:
            # NaN 체크에서 예외 발생시 해당 캔들은 제외
            continue

    return valid_candles


async def get_latest_indicators(
    db: AsyncSession, ticker: str, timeframe: str
) -> Optional[Indicator]:
    """Get latest indicators for a symbol and timeframe"""
    result = await db.execute(
        select(Indicator)
        .join(Symbol)
        .where(and_(Symbol.ticker == ticker, Indicator.timeframe == timeframe))
        .order_by(desc(Indicator.ts))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_moving_avgs(
    db: AsyncSession, ticker: str, timeframe: str
) -> Optional[MovingAvg]:
    """Get latest moving averages for a symbol and timeframe"""
    result = await db.execute(
        select(MovingAvg)
        .join(Symbol)
        .where(and_(Symbol.ticker == ticker, MovingAvg.timeframe == timeframe))
        .order_by(desc(MovingAvg.ts))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_candle(db: AsyncSession, ticker: str, timeframe: str) -> Optional[CandleRaw]:
    """Get latest candle for a symbol and timeframe"""
    result = await db.execute(
        select(CandleRaw)
        .join(Symbol)
        .where(and_(Symbol.ticker == ticker, CandleRaw.timeframe == timeframe))
        .order_by(desc(CandleRaw.ts))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_candle_count(db: AsyncSession, ticker: str, timeframe: str) -> int:
    """Get candle count for a symbol and timeframe"""
    result = await db.execute(
        select(func.count(CandleRaw.id))
        .join(Symbol)
        .where(and_(Symbol.ticker == ticker, CandleRaw.timeframe == timeframe))
    )
    return result.scalar() or 0


async def delete_ticker_data(db: AsyncSession, ticker: str) -> bool:
    """Delete all data for a specific ticker"""
    symbol = await get_symbol_by_ticker(db, ticker)
    if not symbol:
        return False

    # 각 테이블에서 해당 심볼 데이터 삭제
    from sqlalchemy import delete

    # Summary 삭제
    await db.execute(delete(Summary).where(Summary.symbol_id == symbol.id))
    # Indicators 삭제
    await db.execute(delete(Indicator).where(Indicator.symbol_id == symbol.id))
    # MovingAvg 삭제
    await db.execute(delete(MovingAvg).where(MovingAvg.symbol_id == symbol.id))
    # CandleRaw 삭제
    await db.execute(delete(CandleRaw).where(CandleRaw.symbol_id == symbol.id))

    await db.commit()
    logger.info(f"Deleted all data for ticker: {ticker}")
    return True


async def delete_all_active_data(db: AsyncSession) -> List[str]:
    """Delete all data for active symbols"""
    active_symbols = await get_symbols(db, active_only=True)
    deleted_tickers = []

    from sqlalchemy import delete

    for symbol in active_symbols:
        # 각 테이블에서 해당 심볼 데이터 삭제
        await db.execute(delete(Summary).where(Summary.symbol_id == symbol.id))
        await db.execute(delete(Indicator).where(Indicator.symbol_id == symbol.id))
        await db.execute(delete(MovingAvg).where(MovingAvg.symbol_id == symbol.id))
        await db.execute(delete(CandleRaw).where(CandleRaw.symbol_id == symbol.id))
        deleted_tickers.append(symbol.ticker)

    await db.commit()
    logger.info(f"Deleted all data for active symbols: {deleted_tickers}")
    return deleted_tickers
