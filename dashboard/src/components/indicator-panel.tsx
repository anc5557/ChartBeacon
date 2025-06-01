"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

interface TechnicalSignals {
  ticker: string;
  timeframe: string;
  ts: string;
  oscillator_signals: Record<string, string>;
  ma_signals: Record<string, string>;
  buy_count: number;
  sell_count: number;
  neutral_count: number;
  unavailable_count: number;
  total_indicators: number;
  overall_signal: string;
}

interface Indicator {
  ts: string;
  rsi14: number | null;
  stoch_k: number | null;
  stoch_d: number | null;
  macd: number | null;
  macd_signal: number | null;
  adx14: number | null;
  cci14: number | null;
  atr14: number | null;
  highlow14: number | null;
  ultosc: number | null;
  roc: number | null;
  bull_bear: number | null;
}

interface MovingAvg {
  ts: string;
  ma5: number | null;
  ema5: number | null;
  ma10: number | null;
  ema10: number | null;
  ma20: number | null;
  ema20: number | null;
  ma50: number | null;
  ma100: number | null;
  ma200: number | null;
}

interface IndicatorPanelProps {
  ticker: string;
  timeframe: string;
  apiBase: string;
}

export function IndicatorPanel({
  ticker,
  timeframe,
  apiBase,
}: IndicatorPanelProps) {
  const [technicalSignals, setTechnicalSignals] =
    useState<TechnicalSignals | null>(null);
  const [indicators, setIndicators] = useState<Indicator | null>(null);
  const [movingAvgs, setMovingAvgs] = useState<MovingAvg | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 안전한 숫자 변환 및 포맷팅
  const formatNumber = (value: unknown, decimals: number = 2): string => {
    if (value === null || value === undefined || value === "") {
      return "N/A";
    }
    const num = typeof value === "string" ? parseFloat(value) : Number(value);
    if (isNaN(num)) {
      return "N/A";
    }
    return num.toFixed(decimals);
  };

  const formatCurrency = (value: unknown): string => {
    if (value === null || value === undefined || value === "") {
      return "N/A";
    }
    const num = typeof value === "string" ? parseFloat(value) : Number(value);
    if (isNaN(num)) {
      return "N/A";
    }
    return num.toLocaleString();
  };

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [technicalSignalsRes, indicatorsRes, movingAvgsRes] =
        await Promise.all([
          fetch(
            `${apiBase}/technical-signals/${ticker}?timeframe=${timeframe}`
          ),
          fetch(`${apiBase}/indicators/${ticker}/${timeframe}`),
          fetch(`${apiBase}/moving-averages/${ticker}/${timeframe}`),
        ]);

      if (technicalSignalsRes.ok) {
        const signalsData = await technicalSignalsRes.json();
        console.log("Technical signals data:", signalsData);
        setTechnicalSignals(signalsData);
      }

      if (indicatorsRes.ok) {
        const indicatorsData = await indicatorsRes.json();
        console.log("Indicators data:", indicatorsData);
        setIndicators(indicatorsData);
      }

      if (movingAvgsRes.ok) {
        const movingAvgsData = await movingAvgsRes.json();
        console.log("Moving averages data:", movingAvgsData);
        setMovingAvgs(movingAvgsData);
      }

      if (!technicalSignalsRes.ok && !indicatorsRes.ok && !movingAvgsRes.ok) {
        throw new Error("지표 데이터를 불러올 수 없습니다");
      }
    } catch (error) {
      console.error("Failed to fetch indicators:", error);
      setError(
        error instanceof Error ? error.message : "데이터를 불러올 수 없습니다"
      );
    } finally {
      setLoading(false);
    }
  }, [apiBase, ticker, timeframe]);

  useEffect(() => {
    if (ticker && timeframe) {
      fetchData();
    }
  }, [ticker, timeframe, fetchData]);

  // 신호에 따른 색상
  const getSignalColor = (signal: string) => {
    switch (signal) {
      case "BUY":
        return "bg-green-500 text-white";
      case "SELL":
        return "bg-red-500 text-white";
      default:
        return "bg-gray-500 text-white";
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>기술적 지표</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-32">
            로딩 중...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>기술적 지표</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-red-500">{error}</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>기술적 지표</CardTitle>
        {/* 시그널 요약 정보 - 백엔드에서 계산된 데이터 사용 */}
        {technicalSignals && (
          <div className="text-xs text-muted-foreground pt-1">
            종합 요약: 매수 ({technicalSignals.buy_count}) / 매도 (
            {technicalSignals.sell_count}) / 중립 (
            {technicalSignals.neutral_count}) / 계산불가 (
            {technicalSignals.unavailable_count})
            <br />
            전체 {technicalSignals.total_indicators}개 지표 중{" "}
            {technicalSignals.total_indicators -
              technicalSignals.unavailable_count}
            개 계산됨
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 오실레이터 */}
        {indicators && technicalSignals && (
          <div>
            <h3 className="text-sm font-semibold mb-3">오실레이터</h3>
            <div className="space-y-3">
              {/* RSI */}
              <div className="flex items-center justify-between">
                <span className="text-sm">RSI(14)</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono">
                    {formatNumber(indicators.rsi14)}
                  </span>
                  <Badge
                    className={getSignalColor(
                      technicalSignals.oscillator_signals.rsi14 || "NEUTRAL"
                    )}
                  >
                    {technicalSignals.oscillator_signals.rsi14 || "NEUTRAL"}
                  </Badge>
                </div>
              </div>

              {/* Stochastic */}
              <div className="flex items-center justify-between">
                <span className="text-sm">Stoch %K</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono">
                    {formatNumber(indicators.stoch_k)}
                  </span>
                  <Badge
                    className={getSignalColor(
                      technicalSignals.oscillator_signals.stoch_k || "NEUTRAL"
                    )}
                  >
                    {technicalSignals.oscillator_signals.stoch_k || "NEUTRAL"}
                  </Badge>
                </div>
              </div>

              {/* MACD */}
              <div className="flex items-center justify-between">
                <span className="text-sm">MACD</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono">
                    {formatNumber(indicators.macd, 4)}
                  </span>
                  <Badge
                    className={getSignalColor(
                      technicalSignals.oscillator_signals.macd || "NEUTRAL"
                    )}
                  >
                    {technicalSignals.oscillator_signals.macd || "NEUTRAL"}
                  </Badge>
                </div>
              </div>

              {/* CCI */}
              <div className="flex items-center justify-between">
                <span className="text-sm">CCI(14)</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono">
                    {formatNumber(indicators.cci14)}
                  </span>
                  <Badge
                    className={getSignalColor(
                      technicalSignals.oscillator_signals.cci14 || "NEUTRAL"
                    )}
                  >
                    {technicalSignals.oscillator_signals.cci14 || "NEUTRAL"}
                  </Badge>
                </div>
              </div>

              {/* ROC */}
              <div className="flex items-center justify-between">
                <span className="text-sm">ROC</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono">
                    {formatNumber(indicators.roc)}%
                  </span>
                  <Badge
                    className={getSignalColor(
                      technicalSignals.oscillator_signals.roc || "NEUTRAL"
                    )}
                  >
                    {technicalSignals.oscillator_signals.roc || "NEUTRAL"}
                  </Badge>
                </div>
              </div>

              {/* Bull/Bear Power */}
              <div className="flex items-center justify-between">
                <span className="text-sm">Bull/Bear</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono">
                    {formatNumber(indicators.bull_bear)}
                  </span>
                  <Badge
                    className={getSignalColor(
                      technicalSignals.oscillator_signals.bull_bear || "NEUTRAL"
                    )}
                  >
                    {technicalSignals.oscillator_signals.bull_bear || "NEUTRAL"}
                  </Badge>
                </div>
              </div>

              {/* Ultimate Oscillator */}
              <div className="flex items-center justify-between">
                <span className="text-sm">Ultimate Osc</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono">
                    {formatNumber(indicators.ultosc)}
                  </span>
                  <Badge
                    className={getSignalColor(
                      technicalSignals.oscillator_signals.ultosc || "NEUTRAL"
                    )}
                  >
                    {technicalSignals.oscillator_signals.ultosc || "NEUTRAL"}
                  </Badge>
                </div>
              </div>
            </div>
          </div>
        )}

        <Separator />

        {/* 이동평균 */}
        {movingAvgs && technicalSignals && (
          <div>
            <h3 className="text-sm font-semibold mb-3">이동평균</h3>
            <div className="space-y-2">
              {[
                { label: "MA5", value: movingAvgs.ma5, signalKey: "ma5" },
                { label: "EMA5", value: movingAvgs.ema5, signalKey: "ema5" },
                { label: "MA10", value: movingAvgs.ma10, signalKey: "ma10" },
                { label: "EMA10", value: movingAvgs.ema10, signalKey: "ema10" },
                { label: "MA20", value: movingAvgs.ma20, signalKey: "ma20" },
                { label: "EMA20", value: movingAvgs.ema20, signalKey: "ema20" },
                { label: "MA50", value: movingAvgs.ma50, signalKey: "ma50" },
                { label: "MA100", value: movingAvgs.ma100, signalKey: "ma100" },
                { label: "MA200", value: movingAvgs.ma200, signalKey: "ma200" },
              ].map(({ label, value, signalKey }) => {
                const signal =
                  technicalSignals.ma_signals[signalKey] || "NEUTRAL";
                return (
                  <div
                    key={label}
                    className="flex items-center justify-between"
                  >
                    <span className="text-sm">{label}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono">
                        {formatCurrency(value)}
                      </span>
                      <Badge className={getSignalColor(signal)}>{signal}</Badge>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 기타 지표 */}
        {indicators && technicalSignals && (
          <>
            <Separator />
            <div>
              <h3 className="text-sm font-semibold mb-3">기타</h3>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm">ADX(14)</span>
                  <span className="text-sm font-mono">
                    {formatNumber(indicators.adx14)}
                  </span>
                  {/* ADX는 시그널 없음 */}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">ATR(14)</span>
                  <span className="text-sm font-mono">
                    {formatNumber(indicators.atr14)}
                  </span>
                  {/* ATR은 시그널 없음 */}
                </div>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
