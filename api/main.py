from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import logging

from . import crud
from . import schemas
from .database import get_db
from .data_filler import fill_historical_data
from .backtest import BacktestEngine

# 로그 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ChartBeacon API",
    description="Technical indicators dashboard API",
    version="1.0.0",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=schemas.HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc),
        "database": "connected",
    }


@app.get("/symbols", response_model=List[schemas.Symbol])
async def get_symbols(active_only: bool = False, db: AsyncSession = Depends(get_db)):
    """Get all symbols, optionally only active ones"""
    logger.info(f"Getting symbols with active_only={active_only}")
    symbols = await crud.get_symbols(db, active_only=active_only)
    logger.info(f"Found {len(symbols)} symbols")
    for symbol in symbols:
        logger.info(f"Symbol: {symbol.ticker}, active: {symbol.active}")
    return symbols


@app.get("/symbols/active", response_model=List[str])
async def get_active_symbols(db: AsyncSession = Depends(get_db)):
    """Get list of active symbol tickers"""
    return await crud.get_active_symbols_list(db)


@app.post("/symbols", response_model=schemas.Symbol)
async def create_symbol(
    symbol: schemas.SymbolCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Create a new symbol and automatically fill its data"""
    # 중복 검사
    existing = await crud.get_symbol_by_ticker(db, symbol.ticker)
    if existing:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol.ticker} already exists")

    # 종목 생성
    created_symbol = await crud.create_symbol(db, symbol)

    # 백그라운드에서 데이터 자동 채우기
    if created_symbol.active:
        timeframes = ["5m", "1h", "1d", "5d", "1mo", "3mo"]
        background_tasks.add_task(
            fill_historical_data, ticker=created_symbol.ticker, timeframes=timeframes, period="2y"
        )
        logger.info(f"Data filling started for new symbol: {created_symbol.ticker}")

    return created_symbol


@app.put("/symbols/{ticker}", response_model=schemas.Symbol)
async def update_symbol(
    ticker: str, symbol_update: schemas.SymbolUpdate, db: AsyncSession = Depends(get_db)
):
    """Update symbol"""
    symbol = await crud.update_symbol(db, ticker, symbol_update)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")
    return symbol


@app.post("/symbols/{ticker}/activate", response_model=schemas.Symbol)
async def activate_symbol(
    ticker: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)
):
    """Activate a symbol for tracking and fill its data"""
    symbol = await crud.activate_symbol(db, ticker)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")

    # 백그라운드에서 데이터 자동 채우기
    timeframes = ["5m", "1h", "1d", "5d", "1mo", "3mo"]
    background_tasks.add_task(
        fill_historical_data, ticker=symbol.ticker, timeframes=timeframes, period="500d"
    )
    logger.info(f"Data filling started for activated symbol: {symbol.ticker}")

    return symbol


@app.post("/symbols/{ticker}/deactivate", response_model=schemas.Symbol)
async def deactivate_symbol(ticker: str, db: AsyncSession = Depends(get_db)):
    """Deactivate a symbol (stop tracking)"""
    symbol = await crud.deactivate_symbol(db, ticker)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")
    return symbol


@app.get("/summary/{ticker}", response_model=schemas.SummaryResponse)
async def get_summary(ticker: str, timeframe: str = "5m", db: AsyncSession = Depends(get_db)):
    """Get latest technical summary for a ticker"""
    # 티커 검증
    symbol = await crud.get_symbol_by_ticker(db, ticker)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")

    # 최신 요약 조회
    summary = await crud.get_latest_summary(db, ticker, timeframe)
    if not summary:
        raise HTTPException(
            status_code=404,
            detail=f"No summary found for {ticker} on {timeframe} timeframe",
        )

    return {
        "ticker": ticker,
        "timeframe": timeframe,
        "ts": summary.ts,
        "buy_cnt": summary.buy_cnt,
        "sell_cnt": summary.sell_cnt,
        "neutral_cnt": summary.neutral_cnt,
        "level": summary.level,
        "scored_at": summary.scored_at,
    }


@app.get("/summary/history/{ticker}", response_model=List[schemas.SummaryResponse])
async def get_summary_history(
    ticker: str, timeframe: str = "5m", limit: int = 100, db: AsyncSession = Depends(get_db)
):
    """Get summary history for a ticker and timeframe"""
    # 티커 검증
    symbol = await crud.get_symbol_by_ticker(db, ticker)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")

    # 요약 히스토리 조회
    summaries = await crud.get_summary_history(db, ticker, timeframe, limit)
    if not summaries:
        raise HTTPException(
            status_code=404,
            detail=f"No summary history found for {ticker} on {timeframe} timeframe",
        )

    return [
        {
            "ticker": ticker,
            "timeframe": timeframe,
            "ts": summary.ts,
            "buy_cnt": summary.buy_cnt,
            "sell_cnt": summary.sell_cnt,
            "neutral_cnt": summary.neutral_cnt,
            "level": summary.level,
            "scored_at": summary.scored_at,
        }
        for summary in summaries
    ]


@app.get("/candles/{ticker}/{timeframe}", response_model=List[schemas.Candle])
async def get_candles(
    ticker: str, timeframe: str, limit: int = 1000, db: AsyncSession = Depends(get_db)
):
    """Get OHLCV candles for a ticker and timeframe"""
    try:
        # 티커 검증
        symbol = await crud.get_symbol_by_ticker(db, ticker)
        if not symbol:
            raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")

        # 캔들 데이터 조회
        candles = await crud.get_candles(db, ticker, timeframe, limit)
        if not candles:
            raise HTTPException(
                status_code=404,
                detail=f"No candle data found for {ticker} on {timeframe} timeframe",
            )

        return candles
    except HTTPException:
        # HTTPException은 그대로 재발생
        raise
    except Exception as e:
        # 다른 모든 예외는 500 오류로 처리
        logger.error(f"Error getting candles for {ticker}/{timeframe}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error while fetching candle data for {ticker}"
        )


@app.get("/indicators/{ticker}/{timeframe}", response_model=schemas.IndicatorResponse)
async def get_indicators(ticker: str, timeframe: str, db: AsyncSession = Depends(get_db)):
    """Get latest indicators for a ticker and timeframe"""
    # 티커 검증
    symbol = await crud.get_symbol_by_ticker(db, ticker)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")

    # 최신 지표 조회
    indicators = await crud.get_latest_indicators(db, ticker, timeframe)
    if not indicators:
        raise HTTPException(
            status_code=404,
            detail=f"No indicators found for {ticker} on {timeframe} timeframe",
        )

    return indicators


@app.get("/moving-averages/{ticker}/{timeframe}", response_model=schemas.MovingAvgResponse)
async def get_moving_averages(ticker: str, timeframe: str, db: AsyncSession = Depends(get_db)):
    """Get latest moving averages for a ticker and timeframe"""
    # 티커 검증
    symbol = await crud.get_symbol_by_ticker(db, ticker)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")

    # 최신 이동평균 조회
    moving_avgs = await crud.get_latest_moving_avgs(db, ticker, timeframe)
    if not moving_avgs:
        raise HTTPException(
            status_code=404,
            detail=f"No moving averages found for {ticker} on {timeframe} timeframe",
        )

    return moving_avgs


@app.post("/fill-data/all", response_model=schemas.DataFillResponse)
async def fill_all_active_data(
    request: schemas.DataFillRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    모든 활성 종목의 데이터 채우기

    Args:
        request: 요청 바디 (timeframes, period)
    """
    # 활성 심볼 조회
    active_tickers = await crud.get_active_symbols_list(db)
    if not active_tickers:
        raise HTTPException(status_code=404, detail="No active symbols found")

    timeframes = request.timeframes or ["5m", "1h", "1d", "5d", "1mo", "3mo"]
    period = request.period or "max"

    # 'all' 타임프레임 처리
    if timeframes and "all" in timeframes:
        timeframes = ["5m", "1h", "1d", "5d", "1mo", "3mo"]

    # 각 티커별로 백그라운드 태스크 추가
    for ticker in active_tickers:
        background_tasks.add_task(
            fill_historical_data, ticker=ticker, timeframes=timeframes, period=period
        )

    return {
        "tickers": active_tickers,
        "timeframes": timeframes,
        "period": period,
        "status": "started",
        "message": f"Data filling for {len(active_tickers)} symbols has been started in background",
    }


@app.post("/fill-data/{ticker}", response_model=schemas.DataFillResponse)
async def fill_ticker_data(
    ticker: str,
    request: schemas.DataFillRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    특정 종목의 모든 데이터 채우기 (캔들, 지표, 요약)

    Args:
        ticker: 종목 코드 (예: 005930.KS, AAPL)
        request: 요청 바디 (timeframes, period)
    """
    # 티커 검증
    symbol = await crud.get_symbol_by_ticker(db, ticker)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")

    timeframes = request.timeframes or ["5m", "1h", "1d", "5d", "1mo", "3mo"]
    period = request.period or "max"

    # 'all' 타임프레임 처리
    if timeframes and "all" in timeframes:
        timeframes = ["5m", "1h", "1d", "5d", "1mo", "3mo"]

    # 백그라운드에서 데이터 채우기 실행
    background_tasks.add_task(
        fill_historical_data, ticker=ticker, timeframes=timeframes, period=period
    )

    return {
        "ticker": ticker,
        "timeframes": timeframes,
        "period": period,
        "status": "started",
        "message": f"Data filling for {ticker} has been started in background",
    }


@app.post("/data-replenish/{ticker}", response_model=schemas.DataReplenishResponse)
async def replenish_single_ticker_data(
    ticker: str,
    timeframe: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    특정 종목의 특정 타임프레임 데이터 보충 (재실행)
    프론트엔드에서 데이터 부족 시 호출.
    """
    # 티커 검증
    symbol = await crud.get_symbol_by_ticker(db, ticker)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")

    background_tasks.add_task(fill_historical_data, ticker=ticker, timeframes=[timeframe])

    logger.info(f"Data replenishment started for {ticker}, timeframe: {timeframe}")

    return {
        "ticker": ticker,
        "timeframe": timeframe,
        "status": "replenishment_started",
        "message": f"Data replenishment for {ticker} ({timeframe}) has been started in the background.",
    }


MIN_CANDLE_COUNT_FOR_SUFFICIENCY = 200  # 기본값, 단기용
MAX_DAYS_DIFFERENCE_FOR_LATEST_CANDLE = 7  # 기본값, 단기용

# 타임프레임별 최소 필요 캔들 수 정의
TIMEFRAME_MIN_CANDLES = {
    "5m": 200,
    "1h": 200,
    "1d": 200,
    "5d": 52,  # 약 1년치 주봉
    "1mo": 24,  # 약 2년치 월봉
    "3mo": 8,  # 약 2년치 분기봉
}

# 타임프레임별 최근 데이터 최대 허용 일수 차이 정의
TIMEFRAME_MAX_DAYS_DIFFERENCE = {
    "5m": 5,  # 최근 5일 이내 (거래일 기준)
    "1h": 5,  # 최근 5일 이내
    "1d": 7,  # 최근 7일 이내
    "5d": 10,  # 최근 10일 이내 (다음 주 초)
    "1mo": 40,  # 최근 40일 이내 (다음 달 초중순)
    "3mo": 100,  # 최근 100일 이내 (다음 분기 초중순)
}


@app.get("/data-sufficiency/{ticker}", response_model=schemas.DataSufficiencyResponse)
async def get_data_sufficiency(
    ticker: str,
    timeframe: str = Query(...),  # 명시적으로 Query param으로 선언
    db: AsyncSession = Depends(get_db),
):
    symbol = await crud.get_symbol_by_ticker(db, ticker)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")

    latest_candle = await crud.get_latest_candle(db, ticker, timeframe)
    candle_count = await crud.get_candle_count(db, ticker, timeframe)

    sufficient = True
    message = f"{ticker} ({timeframe}) 데이터는 충분합니다."
    details_list = []  # 상세 메시지 리스트
    last_entry_date_val = None

    if not latest_candle:
        sufficient = False
        message = f"{ticker} ({timeframe}) 에 대한 최근 캔들 데이터가 없습니다."
        details_list.append("최근 캔들 데이터가 존재하지 않습니다.")
    else:
        last_entry_date_val = latest_candle.ts
        now_utc = datetime.now(timezone.utc)

        # timezone-aware datetime 처리 개선
        latest_candle_ts_utc = last_entry_date_val
        if latest_candle_ts_utc.tzinfo is None:
            # timezone 정보가 없으면 UTC로 가정
            latest_candle_ts_utc = latest_candle_ts_utc.replace(tzinfo=timezone.utc)
        else:
            # timezone 정보가 있으면 UTC로 변환
            latest_candle_ts_utc = latest_candle_ts_utc.astimezone(timezone.utc)

        days_diff = (now_utc.date() - latest_candle_ts_utc.date()).days

        # 타임프레임에 따른 최근 데이터 최대 허용 일수 가져오기
        max_days_allowed = TIMEFRAME_MAX_DAYS_DIFFERENCE.get(
            timeframe, MAX_DAYS_DIFFERENCE_FOR_LATEST_CANDLE
        )

        if days_diff > max_days_allowed:
            sufficient = False
            message = f"{ticker} ({timeframe}) 최근 캔들 데이터가 너무 오래되었습니다 (마지막: {latest_candle_ts_utc.strftime('%Y-%m-%d')})."
            details_list.append(
                f"데이터가 {days_diff}일 전의 것입니다 (기준: {max_days_allowed}일 이내)."
            )

    # 타임프레임에 따른 최소 필요 캔들 수 가져오기
    min_candles_needed = TIMEFRAME_MIN_CANDLES.get(timeframe, MIN_CANDLE_COUNT_FOR_SUFFICIENCY)

    if candle_count < min_candles_needed:
        sufficient = False
        current_msg_is_default = message == f"{ticker} ({timeframe}) 데이터는 충분합니다."

        insufficient_count_msg = (
            f"캔들 데이터 개수가 부족합니다 ({candle_count}개 / 필요: {min_candles_needed}개)."
        )
        details_list.append(f"캔들 개수: {candle_count} (필요: {min_candles_needed})")

        if current_msg_is_default:
            message = f"{ticker} ({timeframe}) {insufficient_count_msg}"
        else:
            message += f" 또한, {insufficient_count_msg}"

    if not sufficient and not details_list:
        details_list.append("데이터가 부족하여 일부 기능이 제한될 수 있습니다.")

    final_details_str = ", ".join(details_list) if details_list else None
    if sufficient:  # 충분할 경우 details는 null로
        final_details_str = None
        message = f"{ticker} ({timeframe}) 데이터는 충분합니다."

    return schemas.DataSufficiencyResponse(
        sufficient=sufficient,
        message=message,
        last_entry_date=last_entry_date_val,
        details=final_details_str,
        candle_count=candle_count,
    )


@app.get("/fill-data/status/{ticker}", response_model=schemas.DataStatusResponse)
async def get_data_status(ticker: str, db: AsyncSession = Depends(get_db)):
    """
    특정 종목의 데이터 상태 확인
    """
    # 티커 검증
    symbol = await crud.get_symbol_by_ticker(db, ticker)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")

    # 각 타임프레임별 최신 데이터 확인
    status = {}
    timeframes = ["5m", "1h", "1d", "5d", "1mo", "3mo"]

    for tf in timeframes:
        # 캔들 데이터
        latest_candle = await crud.get_latest_candle(db, ticker, tf)
        candle_count = await crud.get_candle_count(db, ticker, tf)

        # 지표 데이터
        latest_indicator = await crud.get_latest_indicators(db, ticker, tf)

        # 이동평균 데이터
        latest_ma = await crud.get_latest_moving_avgs(db, ticker, tf)

        # 요약 데이터
        latest_summary = await crud.get_latest_summary(db, ticker, tf)

        status[tf] = {
            "candles": {
                "count": candle_count,
                "latest": latest_candle.ts if latest_candle else None,
            },
            "indicators": {"latest": latest_indicator.ts if latest_indicator else None},
            "moving_averages": {"latest": latest_ma.ts if latest_ma else None},
            "summary": {
                "latest": latest_summary.ts if latest_summary else None,
                "level": latest_summary.level if latest_summary else None,
            },
        }

    return {"ticker": ticker, "status": status}


@app.post("/reset-data/all", response_model=schemas.DataResetResponse)
async def reset_all_active_data(
    request: schemas.DataFillRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    모든 활성 종목의 데이터를 초기화하고 다시 채우기

    1. 모든 활성 종목의 기존 데이터 삭제
    2. 새로운 데이터로 다시 채우기
    """
    # 기존 데이터 삭제
    deleted_tickers = await crud.delete_all_active_data(db)
    if not deleted_tickers:
        raise HTTPException(status_code=404, detail="No active symbols found")

    timeframes = request.timeframes or ["5m", "1h", "1d", "5d", "1mo", "3mo"]
    period = request.period or "max"

    # 'all' 타임프레임 처리
    if timeframes and "all" in timeframes:
        timeframes = ["5m", "1h", "1d", "5d", "1mo", "3mo"]

    # 각 티커별로 백그라운드 태스크에서 데이터 다시 채우기
    for ticker in deleted_tickers:
        background_tasks.add_task(
            fill_historical_data, ticker=ticker, timeframes=timeframes, period=period
        )

    return {
        "tickers": deleted_tickers,
        "deleted_count": len(deleted_tickers),
        "status": "started",
        "message": f"Reset and refill started for {len(deleted_tickers)} active symbols",
    }


@app.post("/reset-data/{ticker}", response_model=schemas.DataResetResponse)
async def reset_ticker_data(
    ticker: str,
    request: schemas.DataFillRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    특정 종목의 데이터를 초기화하고 다시 채우기

    1. 해당 종목의 기존 데이터 삭제
    2. 새로운 데이터로 다시 채우기
    """
    # 티커 검증
    symbol = await crud.get_symbol_by_ticker(db, ticker)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")

    # 기존 데이터 삭제
    deleted = await crud.delete_ticker_data(db, ticker)
    if not deleted:
        raise HTTPException(status_code=500, detail=f"Failed to delete data for {ticker}")

    timeframes = request.timeframes or ["5m", "1h", "1d", "5d", "1mo", "3mo"]
    period = request.period or "max"

    # 'all' 타임프레임 처리
    if timeframes and "all" in timeframes:
        timeframes = ["5m", "1h", "1d", "5d", "1mo", "3mo"]

    # 백그라운드에서 데이터 다시 채우기
    background_tasks.add_task(
        fill_historical_data, ticker=ticker, timeframes=timeframes, period=period
    )

    return {
        "ticker": ticker,
        "deleted_count": 1,
        "status": "started",
        "message": f"Reset and refill started for {ticker}",
    }


# 백테스트 엔드포인트
@app.post("/backtest", response_model=schemas.BacktestResponse)
async def run_backtest(
    request: schemas.BacktestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    백테스트 실행

    Args:
        request: 백테스트 요청 (ticker, timeframe, start_date, end_date, initial_capital, strategy)

    Returns:
        BacktestResponse: 백테스트 결과
    """
    # 티커 검증
    symbol = await crud.get_symbol_by_ticker(db, request.ticker)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol {request.ticker} not found")

    try:
        # 백테스트 엔진 초기화
        engine = BacktestEngine()

        # 백테스트 실행
        result = await engine.run_signal_backtest(
            ticker=request.ticker,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            strategy=request.strategy,
        )

        # Trade 객체를 dict로 변환
        trades_data = []
        for trade in result.trades:
            trades_data.append(
                schemas.TradeResult(
                    timestamp=trade.timestamp,
                    action=trade.action,
                    price=trade.price,
                    quantity=trade.quantity,
                    reason=trade.reason,
                )
            )

        return schemas.BacktestResponse(
            ticker=result.ticker,
            start_date=result.start_date,
            end_date=result.end_date,
            initial_capital=result.initial_capital,
            final_capital=result.final_capital,
            total_return_pct=result.total_return_pct,
            buy_hold_return_pct=result.buy_hold_return_pct,
            alpha=result.alpha,
            total_trades=result.total_trades,
            winning_trades=result.winning_trades,
            losing_trades=result.losing_trades,
            win_rate=result.win_rate,
            max_drawdown=result.max_drawdown,
            sharpe_ratio=result.sharpe_ratio,
            total_transaction_cost=result.total_transaction_cost,
            trades=trades_data,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Backtest error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")


@app.get("/backtest/strategies")
async def get_backtest_strategies():
    """
    사용 가능한 백테스트 전략 목록
    """
    return {
        "strategies": [
            {
                "name": "technical_summary",
                "description": "기본 기술적 요약 기반 전략 (STRONG_BUY/BUY → 매수, STRONG_SELL/SELL → 매도)",
                "risk": "높음 - 신호 빈도 과다, 후행성 강함",
            },
            {
                "name": "low_frequency",
                "description": "저빈도 트레이딩 (15일 쿨다운, 추세 전환점만 매매)",
                "risk": "낮음 - 거래 빈도 최소화",
            },
            {
                "name": "adx_filtered",
                "description": "ADX 필터링 전략 (트렌드 강도 > 25일 때만 매매)",
                "risk": "중간 - 횡보 구간 매매 금지",
            },
            {
                "name": "momentum_reversal",
                "description": "모멘텀 반전 전략 (극단적 과매수/과매도에서만 매매)",
                "risk": "중간 - 바닥/천장 잡기 시도",
            },
            {
                "name": "position_sizing",
                "description": "포지션 사이징 전략 (변동성 기반 차등 매매)",
                "risk": "중간 - 리스크 대비 포지션 조절",
            },
            {
                "name": "buy_hold_first",
                "description": "바이앤홀드 우선 전략 (첫 매수 후 장기 보유)",
                "risk": "낮음 - 최소 매매, 장기 투자",
            },
            {
                "name": "trend_filtered",
                "description": "트렌드 필터링 전략 (상승 트렌드에서 매도 금지)",
                "risk": "중간 - 추세 보호",
            },
            {
                "name": "market_adaptive",
                "description": "시장 적응형 전략 (시장 상황별 차등 적용)",
                "risk": "중간 - 시장 환경 고려",
            },
            {
                "name": "rsi",
                "description": "RSI 기반 전략 (< 30 → 매수, > 70 → 매도)",
                "risk": "중간",
            },
            {"name": "macd", "description": "MACD 기반 전략 (골든/데드 크로스)", "risk": "중간"},
        ]
    }


@app.get("/technical-signals/{ticker}", response_model=schemas.TechnicalSignalSummaryResponse)
async def get_technical_signals(
    ticker: str, timeframe: str = "5m", db: AsyncSession = Depends(get_db)
):
    """Get technical indicators with calculated signals"""
    # 티커 검증
    symbol = await crud.get_symbol_by_ticker(db, ticker)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")

    # 최신 지표 데이터 조회
    indicators = await crud.get_latest_indicators(db, ticker, timeframe)
    if not indicators:
        raise HTTPException(
            status_code=404,
            detail=f"No indicators found for {ticker} on {timeframe} timeframe",
        )

    # 최신 이동평균 데이터 조회
    moving_avgs = await crud.get_latest_moving_avgs(db, ticker, timeframe)
    if not moving_avgs:
        raise HTTPException(
            status_code=404,
            detail=f"No moving averages found for {ticker} on {timeframe} timeframe",
        )

    # 최신 캔들 데이터 조회 (종가 필요)
    candles = await crud.get_candles(db, ticker, timeframe, limit=1)
    if not candles:
        raise HTTPException(
            status_code=404,
            detail=f"No candles found for {ticker} on {timeframe} timeframe",
        )

    current_close = float(candles[0].close)

    # 시그널 계산
    oscillator_signals = {}
    ma_signals = {}

    # 오실레이터 시그널 (null 값도 NEUTRAL로 포함)
    # RSI14
    if indicators.rsi14 is not None and indicators.rsi14 > 70:
        oscillator_signals["rsi14"] = "SELL"
    elif indicators.rsi14 is not None and indicators.rsi14 < 30:
        oscillator_signals["rsi14"] = "BUY"
    else:
        oscillator_signals["rsi14"] = "NEUTRAL"

    # Stochastic %K
    if indicators.stoch_k is not None and indicators.stoch_k > 80:
        oscillator_signals["stoch_k"] = "SELL"
    elif indicators.stoch_k is not None and indicators.stoch_k < 20:
        oscillator_signals["stoch_k"] = "BUY"
    else:
        oscillator_signals["stoch_k"] = "NEUTRAL"

    # MACD
    if indicators.macd is not None and indicators.macd_signal is not None:
        if indicators.macd > indicators.macd_signal:
            oscillator_signals["macd"] = "BUY"
        elif indicators.macd < indicators.macd_signal:
            oscillator_signals["macd"] = "SELL"
        else:
            oscillator_signals["macd"] = "NEUTRAL"
    else:
        oscillator_signals["macd"] = "NEUTRAL"

    # CCI14
    if indicators.cci14 is not None and indicators.cci14 > 100:
        oscillator_signals["cci14"] = "BUY"
    elif indicators.cci14 is not None and indicators.cci14 < -100:
        oscillator_signals["cci14"] = "SELL"
    else:
        oscillator_signals["cci14"] = "NEUTRAL"

    # ROC
    if indicators.roc is not None and indicators.roc > 0:
        oscillator_signals["roc"] = "BUY"
    elif indicators.roc is not None and indicators.roc < 0:
        oscillator_signals["roc"] = "SELL"
    else:
        oscillator_signals["roc"] = "NEUTRAL"

    # Ultimate Oscillator
    if indicators.ultosc is not None and indicators.ultosc > 70:
        oscillator_signals["ultosc"] = "BUY"
    elif indicators.ultosc is not None and indicators.ultosc < 30:
        oscillator_signals["ultosc"] = "SELL"
    else:
        oscillator_signals["ultosc"] = "NEUTRAL"

    # Williams %R
    if indicators.willr14 is not None and indicators.willr14 > -20:
        oscillator_signals["willr14"] = "SELL"
    elif indicators.willr14 is not None and indicators.willr14 < -80:
        oscillator_signals["willr14"] = "BUY"
    else:
        oscillator_signals["willr14"] = "NEUTRAL"

    # Bull/Bear Power
    if indicators.bull_bear is not None and indicators.bull_bear > 0:
        oscillator_signals["bull_bear"] = "BUY"
    elif indicators.bull_bear is not None and indicators.bull_bear < 0:
        oscillator_signals["bull_bear"] = "SELL"
    else:
        oscillator_signals["bull_bear"] = "NEUTRAL"

    # 이동평균 시그널 (null 값도 NEUTRAL로 포함)
    # MA5
    if moving_avgs.ma5 is not None and current_close > moving_avgs.ma5:
        ma_signals["ma5"] = "BUY"
    elif moving_avgs.ma5 is not None and current_close < moving_avgs.ma5:
        ma_signals["ma5"] = "SELL"
    else:
        ma_signals["ma5"] = "NEUTRAL"

    # EMA5
    if moving_avgs.ema5 is not None and current_close > moving_avgs.ema5:
        ma_signals["ema5"] = "BUY"
    elif moving_avgs.ema5 is not None and current_close < moving_avgs.ema5:
        ma_signals["ema5"] = "SELL"
    else:
        ma_signals["ema5"] = "NEUTRAL"

    # MA10
    if moving_avgs.ma10 is not None and current_close > moving_avgs.ma10:
        ma_signals["ma10"] = "BUY"
    elif moving_avgs.ma10 is not None and current_close < moving_avgs.ma10:
        ma_signals["ma10"] = "SELL"
    else:
        ma_signals["ma10"] = "NEUTRAL"

    # EMA10
    if moving_avgs.ema10 is not None and current_close > moving_avgs.ema10:
        ma_signals["ema10"] = "BUY"
    elif moving_avgs.ema10 is not None and current_close < moving_avgs.ema10:
        ma_signals["ema10"] = "SELL"
    else:
        ma_signals["ema10"] = "NEUTRAL"

    # MA20
    if moving_avgs.ma20 is not None and current_close > moving_avgs.ma20:
        ma_signals["ma20"] = "BUY"
    elif moving_avgs.ma20 is not None and current_close < moving_avgs.ma20:
        ma_signals["ma20"] = "SELL"
    else:
        ma_signals["ma20"] = "NEUTRAL"

    # EMA20
    if moving_avgs.ema20 is not None and current_close > moving_avgs.ema20:
        ma_signals["ema20"] = "BUY"
    elif moving_avgs.ema20 is not None and current_close < moving_avgs.ema20:
        ma_signals["ema20"] = "SELL"
    else:
        ma_signals["ema20"] = "NEUTRAL"

    # MA50
    if moving_avgs.ma50 is not None and current_close > moving_avgs.ma50:
        ma_signals["ma50"] = "BUY"
    elif moving_avgs.ma50 is not None and current_close < moving_avgs.ma50:
        ma_signals["ma50"] = "SELL"
    else:
        ma_signals["ma50"] = "NEUTRAL"

    # MA100
    if moving_avgs.ma100 is not None and current_close > moving_avgs.ma100:
        ma_signals["ma100"] = "BUY"
    elif moving_avgs.ma100 is not None and current_close < moving_avgs.ma100:
        ma_signals["ma100"] = "SELL"
    else:
        ma_signals["ma100"] = "NEUTRAL"

    # MA200
    if moving_avgs.ma200 is not None and current_close > moving_avgs.ma200:
        ma_signals["ma200"] = "BUY"
    elif moving_avgs.ma200 is not None and current_close < moving_avgs.ma200:
        ma_signals["ma200"] = "SELL"
    else:
        ma_signals["ma200"] = "NEUTRAL"

    # 전체 시그널 카운트 (null 값은 제외하고 실제 계산 가능한 지표만)
    all_signals = []

    # 오실레이터 중 실제 값이 있는 것만 포함
    if indicators.rsi14 is not None:
        all_signals.append(oscillator_signals["rsi14"])
    if indicators.stoch_k is not None:
        all_signals.append(oscillator_signals["stoch_k"])
    if indicators.macd is not None and indicators.macd_signal is not None:
        all_signals.append(oscillator_signals["macd"])
    if indicators.cci14 is not None:
        all_signals.append(oscillator_signals["cci14"])
    if indicators.roc is not None:
        all_signals.append(oscillator_signals["roc"])
    if indicators.willr14 is not None:
        all_signals.append(oscillator_signals["willr14"])

    # 이동평균 중 실제 값이 있는 것만 포함
    if moving_avgs.ma5 is not None:
        all_signals.append(ma_signals["ma5"])
    if moving_avgs.ema5 is not None:
        all_signals.append(ma_signals["ema5"])
    if moving_avgs.ma10 is not None:
        all_signals.append(ma_signals["ma10"])
    if moving_avgs.ema10 is not None:
        all_signals.append(ma_signals["ema10"])
    if moving_avgs.ma20 is not None:
        all_signals.append(ma_signals["ma20"])
    if moving_avgs.ema20 is not None:
        all_signals.append(ma_signals["ema20"])
    if moving_avgs.ma50 is not None:
        all_signals.append(ma_signals["ma50"])
    if moving_avgs.ma100 is not None:
        all_signals.append(ma_signals["ma100"])
    if moving_avgs.ma200 is not None:
        all_signals.append(ma_signals["ma200"])

    buy_count = sum(1 for s in all_signals if s == "BUY")
    sell_count = sum(1 for s in all_signals if s == "SELL")
    neutral_count = sum(1 for s in all_signals if s == "NEUTRAL")

    # 계산 불가능한 지표 개수 계산
    total_possible_indicators = 15  # 오실레이터 6개 + 이동평균 9개 (data_filler.py와 동일)
    available_count = len(all_signals)
    unavailable_count = total_possible_indicators - available_count

    # 전체 시그널 결정 (계산 가능한 지표만으로)
    if available_count == 0:
        overall_signal = "NEUTRAL"
    elif buy_count >= (available_count * 2 // 3):
        overall_signal = "STRONG_BUY"
    elif buy_count > sell_count:
        overall_signal = "BUY"
    elif sell_count >= (available_count * 2 // 3):
        overall_signal = "STRONG_SELL"
    elif sell_count > buy_count:
        overall_signal = "SELL"
    else:
        overall_signal = "NEUTRAL"

    return {
        "ticker": ticker,
        "timeframe": timeframe,
        "ts": indicators.ts,
        "oscillator_signals": oscillator_signals,
        "ma_signals": ma_signals,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "neutral_count": neutral_count,
        "unavailable_count": unavailable_count,
        "total_indicators": total_possible_indicators,
        "overall_signal": overall_signal,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
