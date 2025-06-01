from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal
import math


class SymbolBase(BaseModel):
    ticker: str
    name: str


class SymbolCreate(SymbolBase):
    active: bool = True


class SymbolUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None


class Symbol(SymbolBase):
    id: int
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandleBase(BaseModel):
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    volume: Optional[Decimal] = None

    @field_validator("open", "high", "low", "close", "volume", mode="before")
    @classmethod
    def validate_decimal(cls, v):
        if v is None:
            return None
        try:
            if isinstance(v, Decimal):
                if v.is_nan() or v.is_infinite():
                    return None
            elif isinstance(v, (int, float)):
                if math.isnan(v) or math.isinf(v):
                    return None
            # 문자열로 된 'NaN' 체크
            elif isinstance(v, str) and v.lower() in ["nan", "inf", "-inf"]:
                return None
        except Exception:
            return None
        return v


class Candle(CandleBase):
    ts: datetime

    model_config = ConfigDict(from_attributes=True)


class IndicatorResponse(BaseModel):
    ts: datetime
    rsi14: Optional[Decimal]
    stoch_k: Optional[Decimal]
    stoch_d: Optional[Decimal]
    macd: Optional[Decimal]
    macd_signal: Optional[Decimal]
    adx14: Optional[Decimal]
    cci14: Optional[Decimal]
    atr14: Optional[Decimal]
    willr14: Optional[Decimal]
    highlow14: Optional[Decimal]
    ultosc: Optional[Decimal]
    roc: Optional[Decimal]
    bull_bear: Optional[Decimal]

    model_config = ConfigDict(from_attributes=True)


class MovingAvgResponse(BaseModel):
    ts: datetime
    ma5: Optional[Decimal]
    ema5: Optional[Decimal]
    ma10: Optional[Decimal]
    ema10: Optional[Decimal]
    ma20: Optional[Decimal]
    ema20: Optional[Decimal]
    ma50: Optional[Decimal]
    ma100: Optional[Decimal]
    ma200: Optional[Decimal]

    model_config = ConfigDict(from_attributes=True)


class SummaryResponse(BaseModel):
    ticker: str
    timeframe: str
    ts: datetime
    buy_cnt: int
    sell_cnt: int
    neutral_cnt: int
    level: str
    scored_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    database: str


class DataFillRequest(BaseModel):
    """데이터 채우기 요청"""

    timeframes: Optional[List[str]] = None
    period: str = "2y"


class DataFillResponse(BaseModel):
    """데이터 채우기 시작 응답"""

    ticker: Optional[str] = None
    tickers: Optional[List[str]] = None
    timeframes: List[str]
    period: str
    status: str
    message: str


class DataStatusTimeframe(BaseModel):
    """타임프레임별 데이터 상태"""

    candles: Dict[str, Any]  # count, latest
    indicators: Dict[str, Any]  # latest
    moving_averages: Dict[str, Any]  # latest
    summary: Dict[str, Any]  # latest, level


class DataStatusResponse(BaseModel):
    """데이터 상태 확인 응답"""

    ticker: str
    status: Dict[str, DataStatusTimeframe]


class DataResetResponse(BaseModel):
    """데이터 초기화 응답"""

    ticker: Optional[str] = None
    tickers: Optional[List[str]] = None
    deleted_count: int
    status: str
    message: str


# 백테스트 관련 스키마
class BacktestRequest(BaseModel):
    """백테스트 요청"""

    ticker: str
    timeframe: str = "1d"
    start_date: str = "2023-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = 100000
    strategy: str = "technical_summary"  # "technical_summary", "rsi", "macd"


class TradeResult(BaseModel):
    """거래 결과"""

    timestamp: datetime
    action: str
    price: float
    quantity: int
    reason: str


class BacktestResponse(BaseModel):
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
    total_transaction_cost: float  # 총 거래 비용
    trades: List[TradeResult]


class IndicatorWithSignalResponse(BaseModel):
    ts: datetime
    rsi14: Optional[float] = None
    rsi14_signal: Optional[str] = None
    stoch_k: Optional[float] = None
    stoch_k_signal: Optional[str] = None
    stoch_d: Optional[float] = None
    macd: Optional[float] = None
    macd_signal_line: Optional[float] = None
    macd_signal: Optional[str] = None
    adx14: Optional[float] = None
    adx14_signal: Optional[str] = None
    cci14: Optional[float] = None
    cci14_signal: Optional[str] = None
    atr14: Optional[float] = None
    willr14: Optional[float] = None
    highlow14: Optional[float] = None
    ultosc: Optional[float] = None
    ultosc_signal: Optional[str] = None
    roc: Optional[float] = None
    roc_signal: Optional[str] = None
    bull_bear: Optional[float] = None


class MovingAvgWithSignalResponse(BaseModel):
    ts: datetime
    close: Optional[float] = None
    ma5: Optional[float] = None
    ma5_signal: Optional[str] = None
    ema5: Optional[float] = None
    ema5_signal: Optional[str] = None
    ma10: Optional[float] = None
    ma10_signal: Optional[str] = None
    ema10: Optional[float] = None
    ema10_signal: Optional[str] = None
    ma20: Optional[float] = None
    ma20_signal: Optional[str] = None
    ema20: Optional[float] = None
    ema20_signal: Optional[str] = None
    ma50: Optional[float] = None
    ma50_signal: Optional[str] = None
    ma100: Optional[float] = None
    ma100_signal: Optional[str] = None
    ma200: Optional[float] = None
    ma200_signal: Optional[str] = None


class TechnicalSignalSummaryResponse(BaseModel):
    ticker: str
    timeframe: str
    ts: datetime
    oscillator_signals: Dict[str, str]  # {"rsi14": "BUY", "macd": "SELL", ...}
    ma_signals: Dict[str, str]  # {"ma5": "BUY", "ma20": "SELL", ...}
    buy_count: int
    sell_count: int
    neutral_count: int
    unavailable_count: int  # 계산 불가능한 지표 개수
    total_indicators: int  # 전체 지표 개수
    overall_signal: str  # "BUY", "SELL", "NEUTRAL"
