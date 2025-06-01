-- ChartBeacon Database Schema
-- Version: 1.1

-- Create chartbeacon database for API
CREATE DATABASE chartbeacon;

-- Connect to chartbeacon database
\c chartbeacon;

-- 1. SYMBOL MASTER
CREATE TABLE IF NOT EXISTS symbols (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. CANDLE DATA (RAW)
CREATE TABLE IF NOT EXISTS candles_raw (
    id BIGSERIAL PRIMARY KEY,
    symbol_id BIGINT NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    timeframe VARCHAR(10) NOT NULL CHECK (timeframe IN ('5m', '1h', '1d', '5d', '1mo', '3mo')),
    ts TIMESTAMPTZ NOT NULL,
    open NUMERIC(18,4) NOT NULL,
    high NUMERIC(18,4) NOT NULL,
    low NUMERIC(18,4) NOT NULL,
    close NUMERIC(18,4) NOT NULL,
    volume NUMERIC(18,0) NOT NULL,
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol_id, timeframe, ts)
);

-- 3. INDICATORS (OSCILLATORS)
CREATE TABLE IF NOT EXISTS indicators (
    id BIGSERIAL PRIMARY KEY,
    symbol_id BIGINT NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    timeframe VARCHAR(10) NOT NULL CHECK (timeframe IN ('5m', '1h', '1d', '5d', '1mo', '3mo')),
    ts TIMESTAMPTZ NOT NULL,
    rsi14 NUMERIC(10,4),
    stoch_k NUMERIC(10,4),
    stoch_d NUMERIC(10,4),
    macd NUMERIC(12,4),
    macd_signal NUMERIC(12,4),
    adx14 NUMERIC(10,4),
    cci14 NUMERIC(12,4),
    atr14 NUMERIC(14,4),
    highlow14 NUMERIC(12,4),
    ultosc NUMERIC(10,4),
    roc NUMERIC(10,4),
    bull_bear NUMERIC(14,4),
    calc_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol_id, timeframe, ts)
);

-- 4. MOVING AVERAGES
CREATE TABLE IF NOT EXISTS moving_avgs (
    id BIGSERIAL PRIMARY KEY,
    symbol_id BIGINT NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    timeframe VARCHAR(10) NOT NULL CHECK (timeframe IN ('5m', '1h', '1d', '5d', '1mo', '3mo')),
    ts TIMESTAMPTZ NOT NULL,
    ma5 NUMERIC(18,4),
    ema5 NUMERIC(18,4),
    ma10 NUMERIC(18,4),
    ema10 NUMERIC(18,4),
    ma20 NUMERIC(18,4),
    ema20 NUMERIC(18,4),
    ma50 NUMERIC(18,4),
    ma100 NUMERIC(18,4),
    ma200 NUMERIC(18,4),
    calc_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol_id, timeframe, ts)
);

-- 5. SUMMARY (BUY/SELL SCORE)
CREATE TABLE IF NOT EXISTS summary (
    id BIGSERIAL PRIMARY KEY,
    symbol_id BIGINT NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    timeframe VARCHAR(10) NOT NULL CHECK (timeframe IN ('5m', '1h', '1d', '5d', '1mo', '3mo')),
    ts TIMESTAMPTZ NOT NULL,
    buy_cnt SMALLINT NOT NULL DEFAULT 0,
    sell_cnt SMALLINT NOT NULL DEFAULT 0,
    neutral_cnt SMALLINT NOT NULL DEFAULT 0,
    level VARCHAR(20) NOT NULL CHECK (level IN ('STRONG_BUY', 'BUY', 'NEUTRAL', 'SELL', 'STRONG_SELL')),
    scored_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol_id, timeframe, ts)
);

-- Create indexes for better performance
CREATE INDEX idx_candles_raw_symbol_timeframe ON candles_raw(symbol_id, timeframe, ts DESC);
CREATE INDEX idx_indicators_symbol_timeframe ON indicators(symbol_id, timeframe, ts DESC);
CREATE INDEX idx_moving_avgs_symbol_timeframe ON moving_avgs(symbol_id, timeframe, ts DESC);
CREATE INDEX idx_summary_symbol_timeframe ON summary(symbol_id, timeframe, ts DESC);
CREATE INDEX idx_symbols_active ON symbols(active) WHERE active = TRUE;

-- Insert default symbols (initially active)
INSERT INTO symbols (ticker, name, active) VALUES 
    ('005930.KS', 'Samsung Electronics Co Ltd', TRUE),
    ('AAPL', 'Apple Inc', TRUE),
    ('TSLA', 'Tesla Inc', TRUE),
    ('SPY', 'SPDR S&P 500 ETF Trust', TRUE)
ON CONFLICT (ticker) DO UPDATE SET 
    name = EXCLUDED.name,
    active = EXCLUDED.active;

-- Airflow specific tables will be created by Airflow itself 