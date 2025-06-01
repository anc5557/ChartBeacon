"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Copy, Check } from "lucide-react";

interface IndicatorData {
  indicator_type: string;
  value: string;
  signal: string;
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

interface PriceData {
  current_price: number;
  change: number;
  change_percent: number;
  volume: number;
  high_24h?: number;
  low_24h?: number;
}

interface PromptCopyButtonProps {
  ticker: string;
  symbolName: string;
  indicators: IndicatorData[];
  allSummaries: Record<string, Summary>;
  currentTimeframe: string;
  apiBase: string;
}

export function PromptCopyButton({
  ticker,
  symbolName,
  indicators,
  allSummaries,
  currentTimeframe,
  apiBase,
}: PromptCopyButtonProps) {
  const [copied, setCopied] = useState(false);
  const [priceData, setPriceData] = useState<PriceData | null>(null);

  const safeFixed = (value: unknown, decimals: number = 2): string => {
    const num = Number(value);
    if (isNaN(num)) return "0.00";
    return num.toFixed(decimals);
  };

  // 컴포넌트 마운트 시 가격 데이터 가져오기
  useEffect(() => {
    const fetchPriceData = async () => {
      try {
        const response = await fetch(`${apiBase}/candles/${ticker}/1d?limit=2`);
        if (response.ok) {
          const candles = await response.json();
          if (candles.length >= 2) {
            const latest = candles[0];
            const previous = candles[1];
            const currentPrice = Number(latest.close);
            const previousPrice = Number(previous.close);
            const change = currentPrice - previousPrice;
            const changePercent = (change / previousPrice) * 100;

            setPriceData({
              current_price: currentPrice,
              change: change,
              change_percent: changePercent,
              volume: Number(latest.volume),
              high_24h: Number(latest.high),
              low_24h: Number(latest.low),
            });
          }
        }
      } catch (error) {
        console.error("Failed to fetch price data:", error);
      }
    };

    fetchPriceData();
  }, [ticker, apiBase]);

  const generatePrompt = () => {
    const indicatorText = indicators
      .map((indicator) => {
        if (!indicator || !indicator.indicator_type) return "";

        const type = indicator.indicator_type;
        const value = indicator.value;
        const signal = indicator.signal;

        return `- ${type}: ${value} (${signal})`;
      })
      .filter(Boolean)
      .join("\n");

    const timeframes = ["5m", "1h", "1d", "5d", "1mo", "3mo"];
    const allSummaryText = timeframes
      .map((tf) => {
        const summary = allSummaries[`${ticker}-${tf}`];
        if (!summary) return `${tf}: 데이터 없음`;
        return `${tf}: ${summary.level} (매수: ${summary.buy_cnt}, 중립: ${summary.neutral_cnt}, 매도: ${summary.sell_cnt})`;
      })
      .join("\n");

    const priceText = priceData
      ? `현재가: $${safeFixed(priceData.current_price)}
전일 대비: ${priceData.change >= 0 ? "+" : ""}${safeFixed(priceData.change)} (${
          priceData.change_percent >= 0 ? "+" : ""
        }${safeFixed(priceData.change_percent)}%)
거래량: ${priceData.volume.toLocaleString()}
일중 고가: $${safeFixed(priceData.high_24h || 0)}
일중 저가: $${safeFixed(priceData.low_24h || 0)}`
      : "현재가: 데이터 로딩 중\n전일 대비: -\n거래량: -\n일중 고가: -\n일중 저가: -";

    return `
    당신은 금융 전문가입니다. 다음 종목에 대해 지표 추이 및 가격 정보 그리고 해당 종목에 대한 검색을 통해 단 중 장기적으로 해당 종목의 전망을 보고서 형태로 작성해주세요

${ticker} - ${symbolName} 종목 분석 요청

📊 현재 가격 정보
${priceText}

📈 타임프레임별 기술적 분석 신호
${allSummaryText}

🔍 ${currentTimeframe} 타임프레임 세부 지표
${indicatorText || "지표 정보 없음"}

이 종목에 대해 다음을 포함한 투자 분석 보고서를 작성해 주세요:

1. 현재 기술적 지표 종합 해석 및 매매 신호 분석
2. 최신 뉴스, 실적, 재무상태 분석  
3. 업계 동향 및 경쟁 포지션
4. 단중장기 투자 전망 및 목표가
5. 주요 위험 요인 및 투자 전략

바로 분석을 시작해 주세요. 주저하지말고 최선을 다해 분석해주세요.

`;
  };

  const handleCopy = async () => {
    try {
      const prompt = generatePrompt();
      await navigator.clipboard.writeText(prompt);
      setCopied(true);

      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error("복사 실패:", error);
      alert("복사에 실패했습니다.");
    }
  };

  return (
    <Button
      onClick={handleCopy}
      variant="outline"
      size="sm"
      className="flex items-center gap-2"
    >
      {copied ? (
        <>
          <Check className="w-4 h-4" />
          복사완료
        </>
      ) : (
        <>
          <Copy className="w-4 h-4" />
          AI 분석 프롬프트 복사
        </>
      )}
    </Button>
  );
}
