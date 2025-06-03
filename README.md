# ChartBeacon - 기술적 지표 대시보드

Investing.com 스타일의 기술적 지표 요약을 실시간으로 제공하고, Discord로 알림을 보내는 개인용 투자 도구입니다.

## 주요 기능

- 🔍 **실시간 지표 계산**: RSI, MACD, 이동평균 등 12개 이상의 기술적 지표 자동 계산 ✅
- 📊 **요약 레벨 제공**: STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL 5단계 시그널 ✅
- ⏰ **다중 타임프레임**: 5분, 1시간, 1일, 5일, 1개월, 3개월 봉 기준 분석 ✅
- 🔔 **Discord 알림**: 레벨 변경 시 실시간 알림 ✅
- 🧠 **스마트 알림**: 가격 급등락, 거래량 급증, 볼린저밴드 돌파, 지지/저항 터치 감지 ✅
- 📈 **동적 심볼 관리**: 데이터베이스에서 추적할 티커를 동적으로 관리 ✅
- 🚀 **REST API**: FastAPI 기반 고성능 API 제공 ✅
- 🌐 **웹 대시보드**: Next.js 기반 실시간 대시보드 ✅
- 📈 **수동 데이터 채우기**: 특정 종목 또는 모든 종목의 과거 데이터를 한번에 채우기 ✅
- 🎯 **백테스트 기능**: 기술적 지표 기반 전략 성과 분석 및 검증 ✅

## 시스템 구성

- **PostgreSQL 15**: 시계열 데이터 저장 ✅
- **Apache Airflow 2.9**: 스케줄링 및 워크플로 관리 ✅
- **FastAPI**: REST API 서버 ✅
- **Next.js**: 웹 대시보드 ✅
- **Docker Compose**: 원클릭 배포 ✅

## 🚀 빠른 시작 (Docker Compose)

### 1. 환경 설정

```bash
# 프로젝트 클론
git clone https://github.com/yourusername/ChartBeacon.git
cd ChartBeacon

# 환경 변수 설정
cp env.example .env
# .env 파일을 편집하여 Discord Webhook URL 설정
```

### 2. Discord Webhook 설정 (선택사항)

Discord 알림을 받으려면 `.env` 파일에서 `DISCORD_WEBHOOK_URL`을 실제 웹훅 URL로 변경하세요.

### 3. Docker Compose 실행

**PowerShell (Windows)**:
```powershell
.\start.ps1
```

**또는 직접 실행**:
```bash
docker-compose up --build -d
```

### 4. 서비스 접속

시스템이 완전히 시작되려면 약 2-3분이 걸립니다.

- **🌐 웹 대시보드**: http://localhost:3000 ✅
- **🎯 Airflow 웹 UI**: http://localhost:8080 
  - 사용자명: `airflow` / 비밀번호: `airflow`
- **🚀 API 서버**: http://localhost:8000
- **📖 API 문서**: http://localhost:8000/docs
- **🗄️ PostgreSQL**: localhost:5432
  - 데이터베이스: `chartbeacon`, `airflow`
  - 사용자명: `chartbeacon` / 비밀번호: `chartbeacon123`

### 5. 로그 확인

```bash
# 모든 서비스 로그
docker-compose logs -f

# 특정 서비스 로그
docker-compose logs -f api
docker-compose logs -f dashboard
docker-compose logs -f airflow-scheduler
docker-compose logs -f airflow-webserver
```

### 6. 시스템 중지

```bash
docker-compose down
```

**완전히 삭제 (데이터 포함)**:
```bash
docker-compose down -v
```

## 🌐 웹 대시보드

**새로 추가**: 직관적인 웹 인터페이스로 기술적 지표를 실시간 확인할 수 있습니다.

### 주요 기능
- 📈 **실시간 차트**: Recharts 기반 인터랙티브 캔들 차트
- 📊 **지표 패널**: RSI, MACD, Stochastic 등 주요 지표 표시
- 🎯 **요약 카드**: 매수/매도/중립 신호 집계 및 최종 레벨
- 🔄 **다중 타임프레임**: 5분, 1시간, 1일, 5일, 1개월, 3개월 봉 지원
- ➕ **심볼 관리**: 새 종목 추가, 활성화/비활성화 기능
- 🔧 **데이터 보충**: 부족한 데이터 자동 감지 및 보충 기능
- 📊 **백테스트**: 브라우저에서 바로 백테스트 실행

### 접속 방법
```bash
# 웹 대시보드 접속
http://localhost:3000
```

## 🧠 스마트 알림 시스템

**새로 추가**: 단순한 레벨 변경 알림을 넘어선 지능형 알림 시스템

### 알림 유형
1. **가격 급등락 알림** (±3% 이상)
2. **거래량 급증 알림** (평균 대비 2배 이상)
3. **볼린저밴드 돌파 알림**
4. **지지/저항선 터치 알림**

### 스마트 컨텍스트 분석
- 📊 **1시간봉 추세 분석**: 5분봉 신호와 상위 시간봉 추세 비교
- 🎯 **신호 강도 분류**: STRONG, MODERATE, WEAK, INFO
- 🔄 **EMA 기반 추세 판단**: EMA20, EMA60을 활용한 추세 확인
- ⚡ **실시간 필터링**: 노이즈 신호를 줄이고 의미있는 알림만 전송

### Discord 알림 예시

```
🚨 [005930.KS] 5분봉 가격 변동: 급등
🚀 가격 급등! +3.25%

현재가: 75,500
변동률: +3.25%
기준 시간: 2025-01-15 14:35:00 UTC

📊 1H 컨텍스트: 🔥 명확한 상승 추세 (종가>EMA20>EMA60). 5분봉 매수 관련 신호와 일치!
💡 5분봉 의미: 단기적으로 매수세가 강하게 유입되었음을 의미할 수 있습니다.
🤔 대응 전략 제안: 추격 매수보다는 조정 시 매수 또는 단기 저항선 확인.
```

## 로컬 개발 환경

Docker 없이 로컬에서 개발하려면:

```bash
# uv 설치
curl -LsSf https://astral.sh/uv/install.sh | sh

# 의존성 설치
uv sync

# 환경 활성화
source .venv/bin/activate  # Linux/Mac
# 또는
.venv\Scripts\activate     # Windows

# API 서버 실행
uvicorn api.main:app --reload

# 대시보드 실행 (별도 터미널)
cd dashboard
npm install
npm run dev

# Airflow 로컬 실행 (별도 터미널)
airflow standalone
```

## 심볼 관리

### 활성 심볼 조회

```bash
curl http://localhost:8000/symbols/active
```

응답:
```json
["005930.KS", "AAPL", "TSLA", "SPY"]
```

### 새 심볼 추가

```bash
curl -X POST http://localhost:8000/symbols \
  -H "Content-Type: application/json" \
  -d '{"ticker": "QQQ", "name": "Invesco QQQ Trust", "active": true}'
```

### 심볼 비활성화 (추적 중단)

```bash
curl -X POST http://localhost:8000/symbols/TSLA/deactivate
```

### 심볼 활성화 (추적 재개)

```bash
curl -X POST http://localhost:8000/symbols/TSLA/activate
```

### 모든 심볼 조회

```bash
# 활성 심볼만
curl http://localhost:8000/symbols?active_only=true

# 모든 심볼 (비활성 포함)
curl http://localhost:8000/symbols
```

## API 사용 예시

### 최신 기술적 요약 조회

```bash
curl http://localhost:8000/summary/005930.KS?timeframe=5m
```

응답:
```json
{
  "ticker": "005930.KS",
  "timeframe": "5m",
  "ts": "2025-01-15T10:00:00",
  "buy_cnt": 9,
  "sell_cnt": 2,
  "neutral_cnt": 1,
  "level": "STRONG_BUY",
  "scored_at": "2025-01-15T10:00:15"
}
```

### OHLCV 캔들 데이터 조회

```bash
curl http://localhost:8000/candles/AAPL/1h?limit=100
```

### 기술적 신호 조회

```bash
curl http://localhost:8000/technical-signals/005930.KS?timeframe=5m
```

### 백테스트 실행

```bash
# 기술적 요약 기반 백테스트
curl -X POST http://localhost:8000/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "005930.KS",
    "timeframe": "1d",
    "start_date": "2023-01-01",
    "end_date": "2024-06-30",
    "initial_capital": 1000000,
    "strategy": "technical_summary"
  }'
```

응답:
```json
{
  "ticker": "005930.KS",
  "start_date": "2023-01-01T00:00:00",
  "end_date": "2024-06-30T00:00:00",
  "initial_capital": 1000000,
  "final_capital": 1150000,
  "total_return_pct": 15.0,
  "total_trades": 24,
  "winning_trades": 15,
  "losing_trades": 9,
  "win_rate": 62.5,
  "max_drawdown": -8.3,
  "sharpe_ratio": 1.234,
  "trades": [...]
}
```

### 사용 가능한 백테스트 전략

```bash
curl http://localhost:8000/backtest/strategies
```

응답:
```json
{
  "strategies": [
    {
      "name": "technical_summary",
      "description": "기술적 요약 기반 전략 (STRONG_BUY/BUY → 매수, STRONG_SELL/SELL → 매도)"
    },
    {
      "name": "rsi",
      "description": "RSI 기반 전략 (< 30 → 매수, > 70 → 매도)"
    },
    {
      "name": "macd",
      "description": "MACD 기반 전략 (골든/데드 크로스)"
    }
  ]
}
```

## 환경 변수 설정

`.env` 파일에서 다음 항목들을 설정하세요:

```env
# PostgreSQL 설정
POSTGRES_USER=chartbeacon
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=chartbeacon

# Discord Webhook (스마트 알림용)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN

# 추적할 티커 (fallback용 - DB가 우선)
TICKER_SYMBOLS=005930.KS,AAPL,TSLA,SPY,QQQ

# 포트 설정 (선택사항)
API_PORT=8000
DASHBOARD_PORT=3000
AIRFLOW_WEBSERVER_PORT=8080
POSTGRES_PORT=5432
```

## 동적 심볼 관리

**기존 방식** (하드코딩):
```python
TICKERS = ['005930.KS', 'AAPL', 'TSLA']  # 고정된 리스트
```

**새로운 방식** (동적):
- 데이터베이스의 `symbols` 테이블에서 `active = TRUE`인 심볼들을 자동으로 가져옴
- API를 통해 실시간으로 추적할 심볼 추가/제거 가능
- Airflow DAG가 자동으로 새로운 심볼을 인식하여 처리

### 작동 방식

1. **DAG 시작 시**: `get_active_symbols()` 함수가 DB에서 활성 심볼 조회
2. **동적 태스크 생성**: 활성 심볼 각각에 대해 fetch → calc → score → notify 태스크 생성
3. **Fallback**: DB 연결 실패 시 환경변수의 `TICKER_SYMBOLS` 사용

## 지원 지표

### 오실레이터 (11종)
- RSI (14) ✅
- Stochastic %K (9, 6) ✅
- MACD (12, 26, 9) ✅
- CCI (14) ✅
- ROC (12) ✅
- Bull/Bear Power (13) ✅
- Ultimate Oscillator ✅
- 기타

### 이동평균 (12종)
- SMA: 5, 10, 20, 50, 100, 200 ✅
- EMA: 5, 10, 20 ✅

## Discord 알림 예시

### 기존 레벨 변경 알림
```
[005930.KS] NEUTRAL → STRONG_BUY
Buy/Sell/Neutral: 9 / 2 / 1
타임프레임: 5분
시간: 2025-01-15 19:00:00 KST
```

### 스마트 알림 (새로 추가)
```
🚨 [AAPL] 5분봉 볼린저밴드 상단 돌파
📈 볼린저밴드 상단 돌파!

현재가: 225.50
상단밴드: 224.80
하단밴드: 218.20
중심선(SMA): 221.50

📊 1H 컨텍스트: 👍 단기 상승 우위 (종가>EMA20). 5분봉 매수 관련 신호와 부합.
💡 5분봉 의미: 가격이 단기적으로 과매수 구간에 진입했거나, 강한 상승 추세의 시작일 수 있습니다.
🤔 대응 전략 제안: 돌파 후 지지 확인 또는 추세 추종.
```

## 데이터베이스 스키마

- `symbols`: 티커 심볼 마스터 (active 컬럼으로 관리) ✅
- `candles_raw`: OHLCV 원시 데이터 ✅
- `indicators`: 계산된 오실레이터 지표 ✅
- `moving_avgs`: 이동평균 데이터 ✅
- `summary`: 최종 요약 및 레벨 ✅

## 자주 사용하는 명령어

### 심볼 관리
```bash
# 현재 추적 중인 심볼 확인
curl http://localhost:8000/symbols/active

# 새 심볼 추가
curl -X POST http://localhost:8000/symbols \
  -H "Content-Type: application/json" \
  -d '{"ticker": "NVDA", "name": "NVIDIA Corporation"}'

# 심볼 추적 중단
curl -X POST http://localhost:8000/symbols/NVDA/deactivate
```

### 서비스 관리
```bash
# 서비스 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f airflow

# 데이터베이스 접속
docker exec -it chartbeacon-db psql -U chartbeacon
```

### 대시보드 접속
```bash
# 웹 대시보드
http://localhost:3000

# API 문서
http://localhost:8000/docs

# Airflow Web UI
http://localhost:8080
```

### Airflow 관리
```bash
# DAG 수동 실행
curl -X POST http://localhost:8080/api/v1/dags/indicators_5m/dagRuns \
  -u airflow:airflow \
  -H "Content-Type: application/json" \
  -d '{"dag_run_id": "manual_' $(date +%Y%m%d_%H%M%S) '"}'
```

## 문제 해결

### 서비스 상태 확인
```bash
docker-compose ps
docker-compose logs -f [service_name]
```

### 데이터베이스 접속
```bash
docker exec -it chartbeacon-db psql -U chartbeacon
```

### 대시보드 접속 불가
```bash
# 대시보드 로그 확인
docker-compose logs -f dashboard

# API 서버 상태 확인
curl http://localhost:8000/
```

### Airflow DAG 수동 실행
1. Airflow Web UI 접속 (http://localhost:8080)
2. DAGs 탭에서 원하는 DAG 선택
3. "Trigger DAG" 버튼 클릭

## 개발 환경 설정

로컬 개발을 위한 Python 환경:

```bash
# uv 설치 (Linux/macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 프로젝트 초기화 및 의존성 설치
cd ChartBeacon
uv sync

# 개발 모드로 API 실행
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 대시보드 개발 모드 실행
cd dashboard
npm install
npm run dev

# 테스트 실행
uv run pytest

# 코드 포맷팅
uv run black .
uv run isort .

# 타입 체크
uv run mypy .
```

## 아키텍처 다이어그램

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Dashboard │    │    API Server   │    │   PostgreSQL    │
│   (Next.js)     │◄───┤   (FastAPI)     │◄───┤   Database      │
│   Port: 3000    │    │   Port: 8000    │    │   Port: 5432    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        ▲
                                │                        │
                                ▼                        │
┌─────────────────┐    ┌─────────────────┐               │
│  Discord Alerts │◄───┤  Apache Airflow │───────────────┘
│   (Webhook)     │    │  (Scheduler)    │
│                 │    │  Port: 8080     │
└─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────┐
│                  Data Processing Flow                   │
│                                                         │
│  Active Symbols → Data Fetch → Indicators → Summary    │
│       ↓              ↓           ↓          ↓         │
│  Smart Alerts ← Price/Volume ← Technical ← Level      │
│  (5min cycle)    Analysis       Signals    Detection   │
└─────────────────────────────────────────────────────────┘
``` 

## 📊 수동 데이터 채우기

### 특정 종목 데이터 채우기

MA200을 계산하기 위해 충분한 기간(약 300일)의 데이터를 한번에 가져와서 캔들, 지표, 요약 데이터를 모두 계산합니다.

```bash
# 삼성전자 모든 타임프레임 데이터 채우기
curl -X POST http://localhost:8000/fill-data/005930.KS

# 특정 타임프레임만 지정
curl -X POST "http://localhost:8000/fill-data/AAPL?timeframes=1d&timeframes=1h"

# 기간 지정 (일봉의 경우)
curl -X POST "http://localhost:8000/fill-data/TSLA?period=500d"
```

응답:
```json
{
  "ticker": "005930.KS",
  "timeframes": ["5m", "1h", "1d", "5d", "1mo", "3mo"],
  "period": "300d",
  "status": "started",
  "message": "Data filling for 005930.KS has been started in background"
}
```

### 모든 활성 종목 데이터 채우기

```bash
# 모든 활성 종목 데이터 채우기
curl -X POST http://localhost:8000/fill-data/all

# 특정 타임프레임만
curl -X POST "http://localhost:8000/fill-data/all?timeframes=1d"
```

응답:
```json
{
  "tickers": ["005930.KS", "AAPL", "TSLA", "SPY"],
  "timeframes": ["5m", "1h", "1d", "5d", "1mo", "3mo"],
  "period": "300d",
  "status": "started",
  "message": "Data filling for 4 symbols has been started in background"
}
```

### 데이터 상태 확인

```bash
curl http://localhost:8000/fill-data/status/005930.KS
```

응답:
```json
{
  "ticker": "005930.KS",
  "status": {
    "5m": {
      "candles": {
        "count": 4800,
        "latest": "2025-01-15T15:25:00Z"
      },
      "indicators": {
        "latest": "2025-01-15T15:25:00Z"
      },
      "moving_averages": {
        "latest": "2025-01-15T15:25:00Z"
      },
      "summary": {
        "latest": "2025-01-15T15:25:00Z",
        "level": "STRONG_BUY"
      }
    },
    "1h": {
      // ... 1시간 데이터 상태
    },
    "1d": {
      // ... 일봉 데이터 상태
    }
  }
}
```

### 사용 시나리오

1. **초기 설정**: 새로운 종목 추가 후 과거 데이터 채우기
   ```bash
   # 종목 추가
   curl -X POST http://localhost:8000/symbols \
     -H "Content-Type: application/json" \
     -d '{"ticker": "NVDA", "name": "NVIDIA Corporation"}'
   
   # 데이터 채우기
   curl -X POST http://localhost:8000/fill-data/NVDA
   ```

2. **일괄 데이터 업데이트**: 시스템 재시작 후 모든 데이터 보충
   ```bash
   curl -X POST http://localhost:8000/fill-data/all
   ```

3. **데이터 검증**: 특정 종목의 데이터 완성도 확인
   ```bash
   curl http://localhost:8000/fill-data/status/AAPL
   ```

4. **웹 대시보드에서 데이터 보충**: 브라우저에서 버튼 클릭으로 간편하게 데이터 보충 가능 ✅

## 📋 데이터 처리 순서

각 데이터 채우기 요청은 다음 순서로 처리됩니다:

1. **캔들 데이터 수집**: Yahoo Finance에서 OHLCV 데이터 가져오기 ✅
2. **기술적 지표 계산**: RSI, MACD, Stochastic 등 11개 지표 ✅
3. **이동평균 계산**: MA5, EMA5, MA10, EMA10, MA20, EMA20, MA50, MA100, MA200 ✅
4. **요약 생성**: 매수/매도/중립 신호 집계 및 최종 레벨 결정 ✅

### 타임프레임별 데이터 제한

- **5분봉**: 최대 60일 (Yahoo Finance API 제한)
- **1시간봉**: 최대 730일
- **일봉**: 제한 없음 (period 파라미터로 조정 가능)
- **5일봉, 1개월봉, 3개월봉**: 지원 ✅

### MA200 데이터 요구사항

MA200을 정확히 계산하려면 최소 200개의 데이터 포인트가 필요합니다:
- **5분봉**: 200 × 5분 = 약 16.7시간 (실제로는 거래시간 고려하여 약 3-4일)
- **1시간봉**: 200시간 = 약 30-40거래일
- **일봉**: 200일 = 약 10개월

기본 `period=300d` 설정으로 모든 타임프레임에서 MA200을 안정적으로 계산할 수 있습니다.

---

## 라이선스

개인 프로젝트용으로 제작되었습니다.

## 기여

버그 리포트와 개선 제안은 Issues를 통해 남겨주세요.

---

Made with ❤️ for personal trading analysis 