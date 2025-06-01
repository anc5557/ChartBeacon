from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    TIMESTAMP,
    Numeric,
    String,
    SmallInteger,
    ForeignKey,
    CheckConstraint,
    Boolean,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Symbol(Base):
    __tablename__ = "symbols"

    id = Column(BigInteger, primary_key=True)
    ticker = Column(Text, nullable=False, unique=True)
    name = Column(Text, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())

    # Relationships
    candles = relationship("CandleRaw", back_populates="symbol", cascade="all, delete-orphan")
    indicators = relationship("Indicator", back_populates="symbol", cascade="all, delete-orphan")
    moving_avgs = relationship("MovingAvg", back_populates="symbol", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="symbol", cascade="all, delete-orphan")


class CandleRaw(Base):
    __tablename__ = "candles_raw"
    __table_args__ = (
        CheckConstraint(
            "timeframe IN ('5m', '1h', '1d', '5d', '1mo', '3mo')", name="check_timeframe"
        ),
        {"postgresql_partition_by": "RANGE (ts)"},  # For future partitioning
    )

    id = Column(BigInteger, primary_key=True)
    symbol_id = Column(BigInteger, ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False)
    timeframe = Column(String(10), nullable=False)
    ts = Column(TIMESTAMP(timezone=True), nullable=False)
    open = Column(Numeric(18, 4), nullable=False)
    high = Column(Numeric(18, 4), nullable=False)
    low = Column(Numeric(18, 4), nullable=False)
    close = Column(Numeric(18, 4), nullable=False)
    volume = Column(Numeric(18, 0), nullable=False)
    ingested_at = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())

    # Relationship
    symbol = relationship("Symbol", back_populates="candles")


class Indicator(Base):
    __tablename__ = "indicators"
    __table_args__ = (
        CheckConstraint(
            "timeframe IN ('5m', '1h', '1d', '5d', '1mo', '3mo')", name="check_timeframe"
        ),
    )

    id = Column(BigInteger, primary_key=True)
    symbol_id = Column(BigInteger, ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False)
    timeframe = Column(String(10), nullable=False)
    ts = Column(TIMESTAMP(timezone=True), nullable=False)
    rsi14 = Column(Numeric(10, 4))
    stoch_k = Column(Numeric(10, 4))
    stoch_d = Column(Numeric(10, 4))
    macd = Column(Numeric(12, 4))
    macd_signal = Column(Numeric(12, 4))
    adx14 = Column(Numeric(10, 4))
    cci14 = Column(Numeric(12, 4))
    atr14 = Column(Numeric(14, 4))
    willr14 = Column(Numeric(10, 4))
    highlow14 = Column(Numeric(12, 4))
    ultosc = Column(Numeric(10, 4))
    roc = Column(Numeric(10, 4))
    bull_bear = Column(Numeric(14, 4))
    calc_at = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())

    # Relationship
    symbol = relationship("Symbol", back_populates="indicators")


class MovingAvg(Base):
    __tablename__ = "moving_avgs"
    __table_args__ = (
        CheckConstraint(
            "timeframe IN ('5m', '1h', '1d', '5d', '1mo', '3mo')", name="check_timeframe"
        ),
    )

    id = Column(BigInteger, primary_key=True)
    symbol_id = Column(BigInteger, ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False)
    timeframe = Column(String(10), nullable=False)
    ts = Column(TIMESTAMP(timezone=True), nullable=False)
    ma5 = Column(Numeric(18, 4))
    ema5 = Column(Numeric(18, 4))
    ma10 = Column(Numeric(18, 4))
    ema10 = Column(Numeric(18, 4))
    ma20 = Column(Numeric(18, 4))
    ema20 = Column(Numeric(18, 4))
    ma50 = Column(Numeric(18, 4))
    ma100 = Column(Numeric(18, 4))
    ma200 = Column(Numeric(18, 4))
    calc_at = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())

    # Relationship
    symbol = relationship("Symbol", back_populates="moving_avgs")


class Summary(Base):
    __tablename__ = "summary"
    __table_args__ = (
        CheckConstraint(
            "timeframe IN ('5m', '1h', '1d', '5d', '1mo', '3mo')", name="check_timeframe"
        ),
        CheckConstraint(
            "level IN ('STRONG_BUY', 'BUY', 'NEUTRAL', 'SELL', 'STRONG_SELL')",
            name="check_level",
        ),
    )

    id = Column(BigInteger, primary_key=True)
    symbol_id = Column(BigInteger, ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False)
    timeframe = Column(String(10), nullable=False)
    ts = Column(TIMESTAMP(timezone=True), nullable=False)
    buy_cnt = Column(SmallInteger, nullable=False, default=0)
    sell_cnt = Column(SmallInteger, nullable=False, default=0)
    neutral_cnt = Column(SmallInteger, nullable=False, default=0)
    level = Column(String(20), nullable=False)
    scored_at = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())

    # Relationship
    symbol = relationship("Symbol", back_populates="summaries")
