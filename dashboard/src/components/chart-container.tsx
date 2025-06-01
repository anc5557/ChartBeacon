"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { format } from "date-fns";

interface Candle {
  id: number;
  symbol_id: number;
  timeframe: string;
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ingested_at: string;
}

interface SummaryPoint {
  ticker: string;
  timeframe: string;
  ts: string;
  buy_cnt: number;
  sell_cnt: number;
  neutral_cnt: number;
  level: string;
  scored_at: string;
}

interface ChartContainerProps {
  ticker: string;
  timeframe: string;
  apiBase: string;
}

interface TooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: {
      name: string;
      close: number;
      high: number;
      low: number;
      open: number;
      volume: number;
      timestamp: string;
      level?: string | null;
    };
  }>;
  label?: string;
}

interface DotProps {
  cx?: number;
  cy?: number;
  payload?: {
    name: string;
    close: number;
    high: number;
    low: number;
    open: number;
    volume: number;
    timestamp: string;
    level?: string | null;
  };
}

export function ChartContainer({
  ticker,
  timeframe,
  apiBase,
}: ChartContainerProps) {
  const [candles, setCandles] = useState<Candle[]>([]);
  const [summaryPoints, setSummaryPoints] = useState<SummaryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCandles = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(
        `${apiBase}/candles/${ticker}/${timeframe}?limit=100`
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      // 시간순으로 정렬 (오래된 것부터)
      const sortedData = data.reverse();
      setCandles(sortedData);
    } catch (error) {
      console.error("Failed to fetch candles:", error);
      setError(
        error instanceof Error ? error.message : "데이터를 불러올 수 없습니다"
      );
    } finally {
      setLoading(false);
    }
  }, [apiBase, ticker, timeframe]);

  const fetchSummaryHistory = useCallback(async () => {
    try {
      const response = await fetch(
        `${apiBase}/summary/history/${ticker}?timeframe=${timeframe}&limit=100`
      );

      if (response.ok) {
        const data = await response.json();
        console.log("Summary history data:", data);
        // 시간순으로 정렬 (오래된 것부터)
        const sortedData = data.reverse();
        setSummaryPoints(sortedData);
        console.log("Set summary points:", sortedData);
      } else {
        console.log("Summary history response not ok:", response.status);
      }
    } catch (error) {
      console.error("Failed to fetch summary history:", error);
    }
  }, [apiBase, ticker, timeframe]);

  useEffect(() => {
    if (ticker && timeframe) {
      fetchCandles();
      fetchSummaryHistory();
    }
  }, [ticker, timeframe, fetchCandles, fetchSummaryHistory]);

  // timeframe에 따른 시간 포맷 결정
  const getTimeFormat = (timeframe: string) => {
    switch (timeframe) {
      case "5m":
      case "1h":
        return "MM/dd HH:mm";
      case "1d":
      case "5d":
        return "yy/MM/dd";
      case "1mo":
      case "3mo":
        return "yy/MM";
      default:
        return "MM/dd HH:mm";
    }
  };

  // timeframe에 따른 매칭 허용 시간 결정 (밀리초)
  const getMatchingWindow = (timeframe: string) => {
    switch (timeframe) {
      case "5m":
        return 300000; // 5분
      case "1h":
        return 3600000; // 1시간
      case "1d":
        return 86400000; // 1일
      case "5d":
        return 86400000 * 2; // 2일 (5일 캔들은 매일 데이터가 있으므로)
      case "1mo":
        return 86400000 * 7; // 7일 (월별 캔들은 주간 단위로 매칭)
      case "3mo":
        return 86400000 * 14; // 14일 (3개월 캔들은 더 넓은 범위로 매칭)
      default:
        return 300000; // 기본 5분
    }
  };

  // 차트 데이터 변환 (UTC → KST)
  const chartData = candles.map((candle) => {
    const utcDate = new Date(candle.ts);
    // UTC → KST (+9시간)
    const kstDate = new Date(utcDate.getTime() + 9 * 60 * 60 * 1000);
    const formattedTime = format(kstDate, getTimeFormat(timeframe));

    // 해당 시점의 summary 찾기
    const matchingSummary = summaryPoints.find((summary) => {
      const timeDiff = Math.abs(
        new Date(candle.ts).getTime() - new Date(summary.ts).getTime()
      );
      return timeDiff < getMatchingWindow(timeframe);
    });

    return {
      name: formattedTime,
      close: Number(candle.close),
      high: Number(candle.high),
      low: Number(candle.low),
      open: Number(candle.open),
      volume: Number(candle.volume),
      timestamp: candle.ts,
      level: matchingSummary?.level || null,
    };
  });

  // 레벨이 있는 데이터 포인트 개수 계산
  const levelDataPoints = chartData.filter((d) => d.level).length;
  console.log("Summary points count:", summaryPoints.length);
  console.log("Candles count:", candles.length);
  console.log("Level data points:", levelDataPoints);

  // 레벨별 색상
  const getLevelColor = (level: string) => {
    switch (level) {
      case "STRONG_BUY":
        return "#16a34a"; // green-600
      case "BUY":
        return "#4ade80"; // green-400
      case "NEUTRAL":
        return "#9ca3af"; // gray-400
      case "SELL":
        return "#f87171"; // red-400
      case "STRONG_SELL":
        return "#dc2626"; // red-600
      default:
        return "#9ca3af";
    }
  };

  // 커스텀 툴팁
  const CustomTooltip = ({ active, payload, label }: TooltipProps) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;

      return (
        <div className="bg-background border rounded p-3 shadow-lg">
          <p className="font-medium">{label}</p>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="text-green-600">
              시가: {data.open.toLocaleString()}
            </div>
            <div className="text-blue-600">
              고가: {data.high.toLocaleString()}
            </div>
            <div className="text-red-600">
              저가: {data.low.toLocaleString()}
            </div>
            <div className="text-purple-600">
              종가: {data.close.toLocaleString()}
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            거래량: {data.volume.toLocaleString()}
          </p>
          {data.level && (
            <div className="mt-2 pt-2 border-t">
              <div
                className="inline-flex items-center px-2 py-1 rounded text-xs font-medium text-white"
                style={{
                  backgroundColor: getLevelColor(data.level),
                }}
              >
                추천: {data.level}
              </div>
            </div>
          )}
        </div>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>
            {ticker} - {timeframe} 차트
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-96">
            <div>로딩 중...</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>
            {ticker} - {timeframe} 차트
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-96">
            <div className="text-red-500">오류: {error}</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {ticker} - {timeframe} 차트
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-96">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 12 }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 12 }}
                domain={["dataMin - 1", "dataMax + 1"]}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="close"
                stroke="#2563eb"
                strokeWidth={2}
                dot={(props) => {
                  const { cx, cy, payload } = props as DotProps;
                  if (payload?.level) {
                    return (
                      <circle
                        key={`dot-${payload.timestamp}-${payload.level}`}
                        cx={cx}
                        cy={cy}
                        r={6}
                        fill={getLevelColor(payload.level)}
                        stroke="#fff"
                        strokeWidth={2}
                      />
                    );
                  }
                  return <g key={`empty-${cx}-${cy}`} />; // 빈 그룹 요소 반환
                }}
                activeDot={{ r: 4, fill: "#2563eb" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 space-y-2">
          <div className="text-sm text-muted-foreground">
            최근 {chartData.length}개 데이터 포인트 표시
            {levelDataPoints > 0 && (
              <span> • {levelDataPoints}개 포지션 추천</span>
            )}
          </div>

          {/* 레벨 범례 */}
          {levelDataPoints > 0 && (
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="text-muted-foreground">포지션 추천:</span>
              {[
                { level: "STRONG_BUY", label: "강력매수" },
                { level: "BUY", label: "매수" },
                { level: "NEUTRAL", label: "중립" },
                { level: "SELL", label: "매도" },
                { level: "STRONG_SELL", label: "강력매도" },
              ].map(({ level, label }) => (
                <div key={level} className="flex items-center gap-1">
                  <div
                    className="w-3 h-3 rounded-full border border-white"
                    style={{ backgroundColor: getLevelColor(level) }}
                  />
                  <span>{label}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
