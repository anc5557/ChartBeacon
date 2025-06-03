"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { format, formatDistanceToNow } from "date-fns";
import { ko } from "date-fns/locale";

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

interface SummaryCardProps {
  timeframe: string;
  summary?: Summary;
}

export function SummaryCard({ timeframe, summary }: SummaryCardProps) {
  if (!summary) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{timeframe} 요약</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-32 text-muted-foreground">
            데이터 없음
          </div>
        </CardContent>
      </Card>
    );
  }

  // 레벨에 따른 색상 및 아이콘
  const getLevelInfo = (level: string) => {
    switch (level) {
      case "STRONG_BUY":
        return {
          color: "bg-green-600 text-white",
          icon: <TrendingUp className="w-5 h-5" />,
          text: "적극 매수",
        };
      case "BUY":
        return {
          color: "bg-green-400 text-white",
          icon: <TrendingUp className="w-5 h-5" />,
          text: "매수",
        };
      case "NEUTRAL":
        return {
          color: "bg-gray-400 text-white",
          icon: <Minus className="w-5 h-5" />,
          text: "중립",
        };
      case "SELL":
        return {
          color: "bg-red-400 text-white",
          icon: <TrendingDown className="w-5 h-5" />,
          text: "매도",
        };
      case "STRONG_SELL":
        return {
          color: "bg-red-600 text-white",
          icon: <TrendingDown className="w-5 h-5" />,
          text: "적극 매도",
        };
      default:
        return {
          color: "bg-gray-400 text-white",
          icon: <Minus className="w-5 h-5" />,
          text: "알 수 없음",
        };
    }
  };

  const levelInfo = getLevelInfo(summary.level);
  const total = summary.buy_cnt + summary.sell_cnt + summary.neutral_cnt;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{timeframe} 요약</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 메인 레벨 */}
        <div className="text-center">
          <Badge className={`${levelInfo.color} text-lg p-3`}>
            <span className="flex items-center gap-2">
              {levelInfo.icon}
              {levelInfo.text}
            </span>
          </Badge>
        </div>

        {/* 점수 분포 */}
        <div className="space-y-3">
          <div className="text-sm font-medium">지표 분포</div>

          {/* 매수 */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-green-600">매수</span>
            <div className="flex items-center gap-2">
              <div className="w-20 h-2 bg-gray-200 rounded">
                <div
                  className="h-full bg-green-500 rounded"
                  style={{
                    width: `${
                      total > 0 ? (summary.buy_cnt / total) * 100 : 0
                    }%`,
                  }}
                />
              </div>
              <span className="text-sm font-mono w-6">{summary.buy_cnt}</span>
            </div>
          </div>

          {/* 중립 */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">중립</span>
            <div className="flex items-center gap-2">
              <div className="w-20 h-2 bg-gray-200 rounded">
                <div
                  className="h-full bg-gray-500 rounded"
                  style={{
                    width: `${
                      total > 0 ? (summary.neutral_cnt / total) * 100 : 0
                    }%`,
                  }}
                />
              </div>
              <span className="text-sm font-mono w-6">
                {summary.neutral_cnt}
              </span>
            </div>
          </div>

          {/* 매도 */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-red-600">매도</span>
            <div className="flex items-center gap-2">
              <div className="w-20 h-2 bg-gray-200 rounded">
                <div
                  className="h-full bg-red-500 rounded"
                  style={{
                    width: `${
                      total > 0 ? (summary.sell_cnt / total) * 100 : 0
                    }%`,
                  }}
                />
              </div>
              <span className="text-sm font-mono w-6">{summary.sell_cnt}</span>
            </div>
          </div>
        </div>

        {/* 업데이트 시간 */}
        <div className="text-xs text-muted-foreground mt-1">
          마지막 업데이트:{" "}
          {format(
            // UTC 시간을 한국시간으로 변환하여 표시
            new Date(
              new Date(summary.scored_at).toLocaleString("en-US", {
                timeZone: "Asia/Seoul",
              })
            ),
            "MM/dd HH:mm",
            { locale: ko }
          )}
        </div>
      </CardContent>
    </Card>
  );
}
