"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface AddSymbolDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  apiBase: string;
}

export function AddSymbolDialog({
  open,
  onClose,
  onSuccess,
  apiBase,
}: AddSymbolDialogProps) {
  const [ticker, setTicker] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!ticker.trim() || !name.trim()) {
      setError("티커와 종목명을 모두 입력해주세요.");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setSuccess(null);

      const response = await fetch(`${apiBase}/symbols`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ticker: ticker.trim().toUpperCase(),
          name: name.trim(),
          active: true,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      // 성공 메시지 표시
      setSuccess(
        "종목이 추가되었습니다. 백그라운드에서 과거 데이터를 수집 중입니다."
      );

      // 3초 후 다이얼로그 닫기
      setTimeout(() => {
        setTicker("");
        setName("");
        setSuccess(null);
        onSuccess();
      }, 3000);
    } catch (error) {
      console.error("Failed to add symbol:", error);
      setError(
        error instanceof Error ? error.message : "종목 추가에 실패했습니다."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setTicker("");
    setName("");
    setError(null);
    setSuccess(null);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>종목 추가</DialogTitle>
          <DialogDescription>
            새로운 종목을 추가하여 기술적 분석을 시작하세요.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="ticker">티커 코드</Label>
            <Input
              id="ticker"
              placeholder="예: AAPL, 005930.KS"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="name">종목명</Label>
            <Input
              id="name"
              placeholder="예: Apple Inc., 삼성전자"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={loading}
            />
          </div>

          {error && (
            <div className="text-sm text-red-500 p-2 bg-red-50 rounded">
              {error}
            </div>
          )}

          {success && (
            <div className="text-sm text-green-600 p-2 bg-green-50 rounded">
              {success}
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={loading}
            >
              취소
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? "추가 중..." : "추가"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
