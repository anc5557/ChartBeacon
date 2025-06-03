# 시간대 처리 개선사항

## 개요
ChartBeacon 프로젝트의 시간대 처리를 일관성 있게 개선하여 다음 요구사항을 충족하도록 수정했습니다:

- **DB 저장**: 모든 시간 데이터를 UTC TIMESTAMPTZ 형식으로 저장
- **Yahoo Finance 데이터**: 거래소별 현지 시간을 UTC로 변환하여 저장
- **사용자 표시**: 한국시간(KST)으로 변환하여 표시
- **Discord 알림**: 한국시간(KST)으로 변환하여 전송

## 주요 개선사항

### 1. API 레이어 (`api/main.py`)
**Before:**
```python
datetime.utcnow()  # deprecated
```

**After:**
```python
datetime.now(timezone.utc)  # modern approach
```

### 2. 데이터 수집 (`api/data_filler.py`)

#### Yahoo Finance 시간대 처리
**Before:**
- 하드코딩된 시간대 변환
- 일관성 없는 timezone 처리

**After:**
```python
# 거래소별 적절한 시간대 처리
if ticker.endswith(".KS"):
    # 한국 주식: KST(Asia/Seoul)로 가정하고 UTC로 변환
    df.index = df.index.tz_localize("Asia/Seoul").tz_convert("UTC")
else:
    # 기타 주식: UTC로 가정 (Yahoo Finance가 적절히 제공)
    df.index = df.index.tz_localize("UTC")
```

#### 한국 주식 정규장 시간 필터링
```python
# UTC에서 KST로 변환하여 정규장 시간 필터링
if ts_series.dt.tz is not None:
    df_ts_kst = ts_series.dt.tz_convert("Asia/Seoul")
else:
    df_ts_kst = ts_series.dt.tz_localize("UTC").tz_convert("Asia/Seoul")

# 한국 정규장 시간: 09:00 ~ 15:30
regular_hours = (
    ((df["hour"] == 9) & (df["minute"] >= 0))
    | ((df["hour"] >= 10) & (df["hour"] <= 14))
    | ((df["hour"] == 15) & (df["minute"] <= 30))
)
```

### 3. 프론트엔드 (`dashboard/src/components/`)

#### 시간 표시 개선
**Before:**
```typescript
// 하드코딩된 +9시간 변환
new Date(summary.scored_at).getTime() + 9 * 60 * 60 * 1000
```

**After:**
```typescript
// Proper timezone 변환
new Date(summary.scored_at).toLocaleString("en-US", {
  timeZone: "Asia/Seoul",
})
```

### 4. Airflow DAG (`airflow/dags/smart_alerts_dag.py`)
**현재 상태:** ✅ 이미 올바르게 구현됨
```python
# Pendulum을 사용한 적절한 시간대 변환
pendulum.instance(latest_candle_ts).in_timezone("Asia/Seoul").strftime("%Y-%m-%d %H:%M:%S KST")
```

## 데이터 플로우

```
Yahoo Finance (거래소 현지시간)
           ↓
    시간대 변환 로직
           ↓
   PostgreSQL (UTC TIMESTAMPTZ)
           ↓
    API 응답 (UTC JSON)
           ↓
  Frontend/Discord (KST 표시)
```

## 시간대 변환 예시

### 한국 주식 (005930.KS)
```
Yahoo Finance: 2025-01-27 10:00:00+09:00 (KST)
         ↓
Database: 2025-01-27 01:00:00+00:00 (UTC)
         ↓
Display: 2025-01-27 10:00:00 KST
```

### 미국 주식 (AAPL)
```
Yahoo Finance: 2025-01-26 10:30:00-05:00 (EST)
         ↓
Database: 2025-01-26 15:30:00+00:00 (UTC)
         ↓
Display: 2025-01-27 00:30:00 KST
```

## 베스트 프랙티스

1. **DB 저장**: 항상 UTC TIMESTAMPTZ 사용
2. **내부 처리**: UTC로 일관되게 처리
3. **사용자 표시**: 적절한 라이브러리로 한국시간 변환
4. **로깅**: 시간대 정보 포함하여 디버깅 용이

## 검증 방법

### 1. 데이터 정합성 확인
```sql
-- DB에서 UTC 시간 확인
SELECT ticker, ts, ingested_at 
FROM candles_raw c 
JOIN symbols s ON c.symbol_id = s.id 
ORDER BY ts DESC LIMIT 5;
```

### 2. 프론트엔드 표시 확인
- 브라우저에서 한국시간으로 올바르게 표시되는지 확인
- Discord 알림에서 KST 시간이 정확한지 확인

### 3. 로그 확인
```
Processing timezone for 005930.KS - Original timezone: Asia/Seoul
Korean stock: Localizing to Asia/Seoul then converting to UTC
After timezone processing - Index timezone: UTC
```

## 주의사항

1. **하드코딩 금지**: `+9시간` 같은 하드코딩된 오프셋 사용 금지
2. **타임존 라이브러리 사용**: JavaScript `toLocaleString()`, Python `pendulum` 등 활용
3. **DB 스키마**: `TIMESTAMPTZ` 타입 사용 필수
4. **테스트**: 다양한 시간대의 데이터로 검증

## 향후 개선사항

1. **다중 시간대 지원**: 사용자별 시간대 설정 기능
2. **썸머타임 처리**: DST 변환 시점 고려
3. **시간대 검증**: 데이터 수집 시 시간대 정보 검증 강화