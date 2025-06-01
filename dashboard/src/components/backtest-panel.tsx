"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface BacktestPanelProps {
  apiBase: string;
  selectedSymbol: string;
}

interface BacktestResult {
  ticker: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_capital: number;
  total_return_pct: number;
  buy_hold_return_pct: number; // 단순 보유 수익률
  alpha: number; // 초과 수익률
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  max_drawdown: number;
  sharpe_ratio: number;
  total_transaction_cost: number; // 총 거래 비용
  trades: Array<{
    timestamp: string;
    action: string;
    price: number;
    quantity: number;
    reason: string;
  }>;
}

export function BacktestPanel({ apiBase, selectedSymbol }: BacktestPanelProps) {
  // 기본 날짜 설정: 오늘부터 1년 전까지
  const getDefaultDates = () => {
    const today = new Date();
    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(today.getFullYear() - 1);

    return {
      start: oneYearAgo.toISOString().split("T")[0],
      end: today.toISOString().split("T")[0],
    };
  };

  const defaultDates = getDefaultDates();

  const [ticker, setTicker] = useState(selectedSymbol);
  const [timeframe, setTimeframe] = useState("1d");
  const [startDate, setStartDate] = useState(defaultDates.start);
  const [endDate, setEndDate] = useState(defaultDates.end);
  const [initialCapital, setInitialCapital] = useState(1000000);
  const [strategy, setStrategy] = useState("low_frequency"); // 개선된 기본 전략
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 전략별 설명
  const strategyDescriptions = {
    technical_summary: {
      description: "기본 기술적 요약 전략 - 모든 신호에 즉시 반응",
      pros: ["빠른 반응", "단순한 로직"],
      cons: ["신호 빈도 과다", "수수료 부담", "후행성 강함", "횡보 구간 손실"],
      risk: "높음",
      color: "text-red-600",
    },
    low_frequency: {
      description: "저빈도 트레이딩 - 15일 쿨다운, 추세 전환점만 매매",
      pros: ["수수료 절약", "노이즈 제거", "추세 전환 포착"],
      cons: ["기회 놓칠 수 있음", "진입 시점 제한"],
      risk: "낮음",
      color: "text-green-600",
    },
    adx_filtered: {
      description: "ADX 필터링 - 트렌드 강도 확인 후 매매",
      pros: ["횡보 구간 매매 금지", "트렌드 확인", "신뢰도 높음"],
      cons: ["초기 트렌드 놓칠 수 있음"],
      risk: "중간",
      color: "text-yellow-600",
    },
    momentum_reversal: {
      description: "모멘텀 반전 - 극단적 과매수/과매도에서만 매매",
      pros: ["바닥/천장 근처 진입", "역추세 포착"],
      cons: ["타이밍 어려움", "추세 지속 시 손실"],
      risk: "중간",
      color: "text-yellow-600",
    },
    position_sizing: {
      description: "포지션 사이징 - 변동성 기반 차등 매매",
      pros: ["리스크 조절", "신호 강도 반영", "자금 관리"],
      cons: ["복잡한 로직", "기회비용"],
      risk: "중간",
      color: "text-yellow-600",
    },
    buy_hold_first: {
      description: "바이앤홀드 우선 - 첫 매수 후 장기 보유",
      pros: ["수수료 최소화", "장기 수익", "스트레스 적음"],
      cons: ["단기 변동성 노출", "기회비용"],
      risk: "낮음",
      color: "text-green-600",
    },
    trend_filtered: {
      description: "트렌드 필터링 - 상승 트렌드에서 매도 금지",
      pros: ["추세 보호", "상승장 활용"],
      cons: ["하락 전환 늦음"],
      risk: "중간",
      color: "text-yellow-600",
    },
    market_adaptive: {
      description: "시장 적응형 - 시장 상황별 차등 적용",
      pros: ["시장 환경 고려", "유연한 대응"],
      cons: ["복잡한 판단", "오판 위험"],
      risk: "중간",
      color: "text-yellow-600",
    },
    rsi: {
      description: "RSI 전략 - 과매수/과매도 기반",
      pros: ["명확한 기준", "역추세 포착"],
      cons: ["추세장에서 약함", "신호 지연"],
      risk: "중간",
      color: "text-yellow-600",
    },
    macd: {
      description: "MACD 전략 - 골든/데드 크로스",
      pros: ["추세 추종", "명확한 신호"],
      cons: ["후행성", "횡보에서 약함"],
      risk: "중간",
      color: "text-yellow-600",
    },
  };

  // 선택된 종목이 변경되면 ticker 업데이트
  useEffect(() => {
    setTicker(selectedSymbol);
  }, [selectedSymbol]);

  // 빠른 기간 선택
  const setQuickPeriod = (months: number) => {
    const today = new Date();
    const startDate = new Date();
    startDate.setMonth(today.getMonth() - months);

    setStartDate(startDate.toISOString().split("T")[0]);
    setEndDate(today.toISOString().split("T")[0]);
  };

  const runBacktest = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${apiBase}/backtest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ticker,
          timeframe,
          start_date: startDate,
          end_date: endDate,
          initial_capital: initialCapital,
          strategy,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "백테스트 실행 실패");
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류");
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("ko-KR", {
      style: "currency",
      currency: "KRW",
    }).format(amount);
  };

  const getReturnColor = (returnPct: number) => {
    if (returnPct > 0) return "text-green-600";
    if (returnPct < 0) return "text-red-600";
    return "text-gray-600";
  };

  const safeFixed = (value: unknown, decimals: number = 2): string => {
    const num = Number(value);
    if (isNaN(num)) return "0.00";
    return num.toFixed(decimals);
  };

  return (
    <div className="space-y-4">
      {/* 설정 패널 */}
      <Card>
        <CardHeader>
          <CardTitle>백테스트 설정</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="ticker">종목 코드 (현재 선택된 종목)</Label>
              <Input
                id="ticker"
                value={ticker}
                readOnly
                className="bg-gray-50 cursor-not-allowed"
                placeholder="005930.KS"
              />
            </div>
            <div>
              <Label htmlFor="timeframe">시간프레임</Label>
              <Select value={timeframe} onValueChange={setTimeframe}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="5m">5분</SelectItem>
                  <SelectItem value="1h">1시간</SelectItem>
                  <SelectItem value="1d">1일</SelectItem>
                  <SelectItem value="5d">5일</SelectItem>
                  <SelectItem value="1mo">1개월</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="startDate">시작일</Label>
                <Input
                  id="startDate"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="endDate">종료일</Label>
                <Input
                  id="endDate"
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </div>
            </div>

            {/* 빠른 기간 선택 */}
            <div>
              <Label className="text-sm">빠른 기간 선택</Label>
              <div className="flex gap-2 mt-1">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setQuickPeriod(3)}
                >
                  3개월
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setQuickPeriod(6)}
                >
                  6개월
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setQuickPeriod(12)}
                >
                  1년
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setQuickPeriod(24)}
                >
                  2년
                </Button>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="capital">초기 자본</Label>
              <Input
                id="capital"
                type="number"
                value={initialCapital}
                onChange={(e) => setInitialCapital(Number(e.target.value))}
              />
            </div>
            <div>
              <Label htmlFor="strategy">전략</Label>
              <Select value={strategy} onValueChange={setStrategy}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="technical_summary">
                    🔴 기본 기술적 요약 (높은 리스크)
                  </SelectItem>
                  <SelectItem value="low_frequency">
                    🟢 저빈도 트레이딩 (낮은 리스크)
                  </SelectItem>
                  <SelectItem value="adx_filtered">
                    🟡 ADX 필터링 (중간 리스크)
                  </SelectItem>
                  <SelectItem value="momentum_reversal">
                    🟡 모멘텀 반전 (중간 리스크)
                  </SelectItem>
                  <SelectItem value="position_sizing">
                    🟡 포지션 사이징 (중간 리스크)
                  </SelectItem>
                  <SelectItem value="buy_hold_first">
                    🟢 바이앤홀드 우선 (낮은 리스크)
                  </SelectItem>
                  <SelectItem value="trend_filtered">
                    🟡 트렌드 필터링 (중간 리스크)
                  </SelectItem>
                  <SelectItem value="market_adaptive">
                    🟡 시장 적응형 (중간 리스크)
                  </SelectItem>
                  <SelectItem value="rsi">🟡 RSI (중간 리스크)</SelectItem>
                  <SelectItem value="macd">🟡 MACD (중간 리스크)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* 선택된 전략 정보 */}
          {strategyDescriptions[
            strategy as keyof typeof strategyDescriptions
          ] && (
            <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <h4 className="font-semibold text-blue-900 mb-2">
                선택된 전략:{" "}
                {
                  strategyDescriptions[
                    strategy as keyof typeof strategyDescriptions
                  ].description
                }
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="font-medium text-green-800 mb-1">✅ 장점:</p>
                  <ul className="text-green-700 space-y-1">
                    {strategyDescriptions[
                      strategy as keyof typeof strategyDescriptions
                    ].pros.map((pro, index) => (
                      <li key={index} className="flex items-center gap-1">
                        <span className="w-1 h-1 bg-green-600 rounded-full"></span>
                        {pro}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="font-medium text-red-800 mb-1">⚠️ 단점:</p>
                  <ul className="text-red-700 space-y-1">
                    {strategyDescriptions[
                      strategy as keyof typeof strategyDescriptions
                    ].cons.map((con, index) => (
                      <li key={index} className="flex items-center gap-1">
                        <span className="w-1 h-1 bg-red-600 rounded-full"></span>
                        {con}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-blue-200">
                <span className="text-sm font-medium">리스크 레벨: </span>
                <span
                  className={`font-bold ${
                    strategyDescriptions[
                      strategy as keyof typeof strategyDescriptions
                    ].color
                  }`}
                >
                  {
                    strategyDescriptions[
                      strategy as keyof typeof strategyDescriptions
                    ].risk
                  }
                </span>
              </div>
            </div>
          )}

          <Button onClick={runBacktest} disabled={loading} className="w-full">
            {loading ? "백테스트 실행 중..." : "백테스트 실행"}
          </Button>
        </CardContent>
      </Card>

      {/* 에러 메시지 */}
      {error && (
        <Card className="border-red-500">
          <CardContent className="pt-6">
            <p className="text-red-600">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* 결과 패널 */}
      {result && (
        <div className="space-y-4">
          {/* 성과 요약 */}
          <Card>
            <CardHeader>
              <CardTitle>백테스트 결과 - {result.ticker}</CardTitle>
              <div className="text-sm text-gray-600">
                전략:{" "}
                {
                  strategyDescriptions[
                    strategy as keyof typeof strategyDescriptions
                  ]?.description
                }
                <span
                  className={`ml-2 font-medium ${
                    strategyDescriptions[
                      strategy as keyof typeof strategyDescriptions
                    ]?.color
                  }`}
                >
                  (리스크:{" "}
                  {
                    strategyDescriptions[
                      strategy as keyof typeof strategyDescriptions
                    ]?.risk
                  }
                  )
                </span>
              </div>
            </CardHeader>
            <CardContent>
              {/* 전략 vs Buy & Hold 비교 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6 p-4 bg-gray-50 rounded-lg">
                <div className="text-center">
                  <p className="text-sm text-gray-500 mb-2">전략 수익률</p>
                  <p
                    className={`text-3xl font-bold ${getReturnColor(
                      result.total_return_pct
                    )}`}
                  >
                    {safeFixed(result.total_return_pct)}%
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-sm text-gray-500 mb-2">단순 보유 수익률</p>
                  <p
                    className={`text-3xl font-bold ${getReturnColor(
                      result.buy_hold_return_pct
                    )}`}
                  >
                    {safeFixed(result.buy_hold_return_pct)}%
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-sm text-gray-500 mb-2">
                    알파 (초과수익)
                    {result.alpha > 0
                      ? " 🎯"
                      : result.alpha < 0
                      ? " ⚠️"
                      : " ➖"}
                  </p>
                  <p
                    className={`text-3xl font-bold ${getReturnColor(
                      result.alpha
                    )}`}
                  >
                    {result.alpha > 0 ? "+" : ""}
                    {safeFixed(result.alpha)}%
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <p className="text-sm text-gray-500">최종 자본</p>
                  <p className="text-2xl font-bold">
                    {formatCurrency(result.final_capital)}
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-sm text-gray-500">승률</p>
                  <p className="text-2xl font-bold">
                    {safeFixed(result.win_rate, 1)}%
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-sm text-gray-500">총 거래</p>
                  <p className="text-2xl font-bold">{result.total_trades}</p>
                </div>
                <div className="text-center">
                  <p className="text-sm text-gray-500">샤프 비율</p>
                  <p className="text-2xl font-bold">
                    {safeFixed(result.sharpe_ratio, 3)}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-6">
                <div>
                  <p className="text-sm text-gray-500">초기 자본</p>
                  <p className="font-bold">
                    {formatCurrency(result.initial_capital)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">수익 거래</p>
                  <p className="font-bold text-green-600">
                    {result.winning_trades}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">손실 거래</p>
                  <p className="font-bold text-red-600">
                    {result.losing_trades}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">최대 낙폭</p>
                  <p className="font-bold text-red-600">
                    {safeFixed(result.max_drawdown)}%
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">거래 비용</p>
                  <p className="font-bold text-red-600">
                    {formatCurrency(result.total_transaction_cost || 0)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">테스트 기간</p>
                  <p className="font-bold text-sm">
                    {new Date(result.start_date).toLocaleDateString()} ~<br />
                    {new Date(result.end_date).toLocaleDateString()}
                  </p>
                </div>
              </div>

              {/* 전략 평가 */}
              <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                <h4 className="font-semibold mb-2">전략 평가</h4>
                <div className="text-sm space-y-2">
                  {result.alpha > 5 ? (
                    <p className="text-green-600 font-medium">
                      ✅ 우수: 시장 대비 {safeFixed(result.alpha)}% 초과수익
                      달성
                    </p>
                  ) : result.alpha > 0 ? (
                    <p className="text-blue-600 font-medium">
                      👍 양호: 시장 대비 {safeFixed(result.alpha)}% 초과수익
                    </p>
                  ) : (
                    <p className="text-red-600 font-medium">
                      ⚠️ 아쉬움: 시장 대비 {safeFixed(result.alpha)}% 저조
                    </p>
                  )}

                  {result.total_trades > 50 && (
                    <p className="text-orange-600">
                      📊 거래 빈도 높음 ({result.total_trades}회) - 수수료 부담
                      검토 필요
                    </p>
                  )}

                  {result.total_trades < 5 && (
                    <p className="text-blue-600">
                      🎯 거래 빈도 적절 ({result.total_trades}회) - 수수료
                      효율적
                    </p>
                  )}

                  {result.win_rate > 60 ? (
                    <p className="text-green-600">
                      🎯 높은 승률 ({safeFixed(result.win_rate, 1)}%)
                    </p>
                  ) : result.win_rate < 40 ? (
                    <p className="text-red-600">
                      📉 낮은 승률 ({safeFixed(result.win_rate, 1)}%) - 전략
                      개선 필요
                    </p>
                  ) : (
                    <p className="text-gray-600">
                      ⚖️ 보통 승률 ({safeFixed(result.win_rate, 1)}%)
                    </p>
                  )}

                  {result.max_drawdown > 20 && (
                    <p className="text-red-600">
                      ⚠️ 높은 최대 낙폭 ({safeFixed(result.max_drawdown)}%) -
                      리스크 관리 강화 필요
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 거래 내역 */}
          <Card>
            <CardHeader>
              <CardTitle>거래 내역 (최근 10개)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {result.trades
                  .slice(-10)
                  .reverse()
                  .map((trade, index) => (
                    <div
                      key={index}
                      className="flex justify-between items-center p-2 bg-gray-50 rounded"
                    >
                      <div className="flex items-center space-x-2">
                        <span
                          className={`px-2 py-1 rounded text-xs font-bold ${
                            trade.action === "BUY"
                              ? "bg-blue-100 text-blue-800"
                              : "bg-red-100 text-red-800"
                          }`}
                        >
                          {trade.action}
                        </span>
                        <span className="text-sm">
                          {trade.quantity}주 @ {safeFixed(trade.price)}
                        </span>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium">
                          {new Date(trade.timestamp).toLocaleDateString()}
                        </p>
                        <p className="text-xs text-gray-500">{trade.reason}</p>
                      </div>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
