"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ChartContainer } from "@/components/chart-container";
import { IndicatorPanel } from "@/components/indicator-panel";
import { SummaryCard } from "@/components/summary-card";
import { AddSymbolDialog } from "@/components/add-symbol-dialog";
import { PromptCopyButton } from "@/components/prompt-copy-button";
import { BacktestPanel } from "@/components/backtest-panel";
import { TrendingUp, TrendingDown, Minus, Plus } from "lucide-react";

interface Symbol {
  id: number;
  ticker: string;
  name: string;
  active: boolean;
}

interface Summary {
  ticker: string;
  timeframe: string;
  ts: string;
  buy_cnt: number;
  sell_cnt: number;
  neutral_cnt: number;
  level: string;
  scored_at: string;
}

interface IndicatorData {
  indicator_type: string;
  value: string;
  signal: string;
}

const timeframes = ["5m", "1h", "1d", "5d", "1mo", "3mo"];

export default function Dashboard() {
  const [symbols, setSymbols] = useState<Symbol[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>("5m");
  const [summaries, setSummaries] = useState<Record<string, Summary>>({});
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [currentIndicators, setCurrentIndicators] = useState<IndicatorData[]>(
    []
  );

  // API Base URL
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // 심볼 목록 조회
  const fetchSymbols = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/symbols?active_only=true`);
      const data = await response.json();
      setSymbols(data);
      if (data.length > 0 && !selectedSymbol) {
        setSelectedSymbol(data[0].ticker);
      }
    } catch (error) {
      console.error("Failed to fetch symbols:", error);
    }
  }, [API_BASE, selectedSymbol]);

  // 요약 정보 조회
  const fetchSummary = useCallback(
    async (ticker: string, timeframe: string) => {
      try {
        const response = await fetch(
          `${API_BASE}/summary/${ticker}?timeframe=${timeframe}`
        );
        if (response.ok) {
          const data = await response.json();
          setSummaries((prev) => ({
            ...prev,
            [`${ticker}-${timeframe}`]: data,
          }));
        }
      } catch (error) {
        console.error(
          `Failed to fetch summary for ${ticker}-${timeframe}:`,
          error
        );
      }
    },
    [API_BASE]
  );

  // 지표 정보 조회
  const fetchIndicators = useCallback(
    async (ticker: string, timeframe: string) => {
      try {
        const response = await fetch(
          `${API_BASE}/technical-signals/${ticker}?timeframe=${timeframe}`
        );

        if (response.ok) {
          const signalsData = await response.json();
          const indicators = [];

          // 오실레이터 지표들 (백엔드에서 계산된 시그널 사용)
          if (signalsData.oscillator_signals.rsi14) {
            indicators.push({
              indicator_type: "RSI(14)",
              value: "계산됨", // 실제 값은 indicator-panel에서 표시
              signal:
                signalsData.oscillator_signals.rsi14 === "BUY"
                  ? "매수"
                  : signalsData.oscillator_signals.rsi14 === "SELL"
                  ? "매도"
                  : "중립",
            });
          }

          if (signalsData.oscillator_signals.stoch_k) {
            indicators.push({
              indicator_type: "Stochastic %K",
              value: "계산됨",
              signal:
                signalsData.oscillator_signals.stoch_k === "BUY"
                  ? "매수"
                  : signalsData.oscillator_signals.stoch_k === "SELL"
                  ? "매도"
                  : "중립",
            });
          }

          if (signalsData.oscillator_signals.macd) {
            indicators.push({
              indicator_type: "MACD",
              value: "계산됨",
              signal:
                signalsData.oscillator_signals.macd === "BUY" ? "매수" : "매도",
            });
          }

          if (signalsData.oscillator_signals.cci14) {
            indicators.push({
              indicator_type: "CCI(14)",
              value: "계산됨",
              signal:
                signalsData.oscillator_signals.cci14 === "BUY"
                  ? "매수"
                  : signalsData.oscillator_signals.cci14 === "SELL"
                  ? "매도"
                  : "중립",
            });
          }

          // 이동평균 지표들
          if (signalsData.ma_signals.ma20) {
            indicators.push({
              indicator_type: "MA(20)",
              value: "계산됨",
              signal:
                signalsData.ma_signals.ma20 === "BUY"
                  ? "매수"
                  : signalsData.ma_signals.ma20 === "SELL"
                  ? "매도"
                  : "중립",
            });
          }

          if (signalsData.ma_signals.ma50) {
            indicators.push({
              indicator_type: "MA(50)",
              value: "계산됨",
              signal:
                signalsData.ma_signals.ma50 === "BUY"
                  ? "매수"
                  : signalsData.ma_signals.ma50 === "SELL"
                  ? "매도"
                  : "중립",
            });
          }

          setCurrentIndicators(indicators);
        }
      } catch (error) {
        console.error(
          `Failed to fetch indicators for ${ticker}-${timeframe}:`,
          error
        );
      }
    },
    [API_BASE]
  );

  // 초기 데이터 로드
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await fetchSymbols();
      setLoading(false);
    };
    loadData();
  }, [fetchSymbols]);

  // 선택된 심볼의 모든 타임프레임 요약 조회
  useEffect(() => {
    if (selectedSymbol) {
      timeframes.forEach((tf) => {
        fetchSummary(selectedSymbol, tf);
      });
    }
  }, [selectedSymbol, fetchSummary]);

  // 선택된 타임프레임의 지표 조회
  useEffect(() => {
    if (selectedSymbol && selectedTimeframe) {
      fetchIndicators(selectedSymbol, selectedTimeframe);
    }
  }, [selectedSymbol, selectedTimeframe, fetchIndicators]);

  // 키보드 내비게이션 (위/아래로 종목 변경, 좌/우로 타임프레임 변경)
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // 종목 변경 (위/아래 키)
      if (
        symbols.length > 0 &&
        (event.key === "ArrowUp" || event.key === "ArrowDown")
      ) {
        const currentIndex = symbols.findIndex(
          (symbol) => symbol.ticker === selectedSymbol
        );

        if (event.key === "ArrowUp") {
          event.preventDefault();
          const prevIndex =
            currentIndex > 0 ? currentIndex - 1 : symbols.length - 1;
          setSelectedSymbol(symbols[prevIndex].ticker);
        } else if (event.key === "ArrowDown") {
          event.preventDefault();
          const nextIndex =
            currentIndex < symbols.length - 1 ? currentIndex + 1 : 0;
          setSelectedSymbol(symbols[nextIndex].ticker);
        }
      }

      // 타임프레임 변경 (좌/우 키)
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        const currentTimeframeIndex = timeframes.findIndex(
          (tf) => tf === selectedTimeframe
        );

        if (event.key === "ArrowLeft") {
          event.preventDefault();
          const prevIndex =
            currentTimeframeIndex > 0
              ? currentTimeframeIndex - 1
              : timeframes.length - 1;
          setSelectedTimeframe(timeframes[prevIndex]);
        } else if (event.key === "ArrowRight") {
          event.preventDefault();
          const nextIndex =
            currentTimeframeIndex < timeframes.length - 1
              ? currentTimeframeIndex + 1
              : 0;
          setSelectedTimeframe(timeframes[nextIndex]);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [symbols, selectedSymbol, selectedTimeframe]);

  // 요약 레벨에 따른 색상
  const getLevelColor = (level: string) => {
    switch (level) {
      case "STRONG_BUY":
        return "bg-green-600 text-white";
      case "BUY":
        return "bg-green-400 text-white";
      case "NEUTRAL":
        return "bg-gray-400 text-white";
      case "SELL":
        return "bg-red-400 text-white";
      case "STRONG_SELL":
        return "bg-red-600 text-white";
      default:
        return "bg-gray-400 text-white";
    }
  };

  // 요약 레벨에 따른 아이콘
  const getLevelIcon = (level: string) => {
    switch (level) {
      case "STRONG_BUY":
      case "BUY":
        return <TrendingUp className="w-4 h-4" />;
      case "STRONG_SELL":
      case "SELL":
        return <TrendingDown className="w-4 h-4" />;
      default:
        return <Minus className="w-4 h-4" />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">로딩 중...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        {/* 헤더 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">ChartBeacon 대시보드</h1>
            <p className="text-muted-foreground">기술적 지표 및 차트 분석</p>
          </div>
          <Button onClick={() => setIsAddDialogOpen(true)}>
            <Plus className="w-4 h-4 mr-2" />
            종목 추가
          </Button>
        </div>

        {/* 심볼 선택 */}
        <Card>
          <CardHeader>
            <CardTitle>종목 선택</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4 items-center">
              <Select value={selectedSymbol} onValueChange={setSelectedSymbol}>
                <SelectTrigger className="w-64">
                  <SelectValue placeholder="종목을 선택하세요" />
                </SelectTrigger>
                <SelectContent>
                  {symbols.map((symbol) => (
                    <SelectItem key={symbol.ticker} value={symbol.ticker}>
                      {symbol.ticker} - {symbol.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* 요약 배지들 */}
              <div className="flex gap-2">
                {timeframes.map((tf) => {
                  const summary = summaries[`${selectedSymbol}-${tf}`];
                  if (!summary) return null;

                  return (
                    <Badge key={tf} className={getLevelColor(summary.level)}>
                      <span className="flex items-center gap-1">
                        {getLevelIcon(summary.level)}
                        {tf}: {summary.level}
                      </span>
                    </Badge>
                  );
                })}
              </div>

              {/* 프롬프트 복사 버튼 */}
              {selectedSymbol && (
                <PromptCopyButton
                  ticker={selectedSymbol}
                  symbolName={
                    symbols.find((s) => s.ticker === selectedSymbol)?.name ||
                    selectedSymbol
                  }
                  indicators={currentIndicators}
                  allSummaries={summaries}
                  currentTimeframe={selectedTimeframe}
                  apiBase={API_BASE}
                />
              )}
            </div>
          </CardContent>
        </Card>

        {selectedSymbol && (
          <>
            {/* 요약 카드들 */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {timeframes.map((tf) => (
                <SummaryCard
                  key={tf}
                  timeframe={tf}
                  summary={summaries[`${selectedSymbol}-${tf}`]}
                />
              ))}
            </div>

            {/* 메인 탭 */}
            <Tabs defaultValue="analysis" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="analysis">차트 분석</TabsTrigger>
                <TabsTrigger value="backtest">백테스트</TabsTrigger>
              </TabsList>

              {/* 차트 분석 탭 */}
              <TabsContent value="analysis" className="space-y-6">
                <Tabs
                  value={selectedTimeframe}
                  onValueChange={setSelectedTimeframe}
                >
                  <TabsList>
                    {timeframes.map((tf) => (
                      <TabsTrigger key={tf} value={tf}>
                        {tf}
                      </TabsTrigger>
                    ))}
                  </TabsList>

                  {timeframes.map((tf) => (
                    <TabsContent key={tf} value={tf} className="space-y-6">
                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* 차트 영역 */}
                        <div className="lg:col-span-2">
                          <ChartContainer
                            ticker={selectedSymbol}
                            timeframe={tf}
                            apiBase={API_BASE}
                          />
                        </div>

                        {/* 지표 패널 */}
                        <div>
                          <IndicatorPanel
                            ticker={selectedSymbol}
                            timeframe={tf}
                            apiBase={API_BASE}
                          />
                        </div>
                      </div>
                    </TabsContent>
                  ))}
                </Tabs>
              </TabsContent>

              {/* 백테스트 탭 */}
              <TabsContent value="backtest" className="space-y-6">
                <BacktestPanel
                  apiBase={API_BASE}
                  selectedSymbol={selectedSymbol}
                />
              </TabsContent>
            </Tabs>
          </>
        )}

        {/* 종목 추가 다이얼로그 */}
        <AddSymbolDialog
          open={isAddDialogOpen}
          onClose={() => setIsAddDialogOpen(false)}
          onSuccess={() => {
            fetchSymbols();
            setIsAddDialogOpen(false);
          }}
          apiBase={API_BASE}
        />
      </div>
    </div>
  );
}
