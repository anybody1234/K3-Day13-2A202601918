# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: K3-Observability
- Repository URL: https://github.com/anybody1234/Day13-K3-Observability
- Commit SHA cuối: (sẽ cập nhật sau commit cuối)
- Thành viên và vai trò:

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100**
  - PASSED: Basic JSON schema
  - PASSED: Correlation ID propagation (21+ unique IDs)
  - PASSED: Log enrichment (user_id_hash, session_id, feature, model)
  - PASSED: PII scrubbing (không có PII leak)
  - Tổng log records: 41+ bản ghi JSON hợp lệ
- Tổng số traces: 20+ traces trên Langfuse (tracing_enabled: true)
- Số PII leak còn lại: 0
- Link/đường dẫn dashboard: `streamlit run dashboard_app.py`
- `python -m pytest -q`: passed
- `python scripts/validate_dashboard.py`: HỢP LỆ 6/6 panel

## 3. Logging và tracing

- Evidence correlation ID: Mỗi request có unique correlation ID dạng `req-XXXXXXXX` (ví dụ: `req-81929f37`, `req-c300daeb`). Correlation ID được tạo tại middleware, bind vào structlog context, và trả về trong response header `x-request-id`.
- Evidence PII redaction: Email, SĐT VN, CCCD, credit card và VN address đều được scrub bởi `pii.py` trước khi log ghi xuống file. Validator xác nhận 0 PII leak.
- Evidence trace waterfall: Xem Langfuse dashboard tại `https://jp.cloud.langfuse.com`
- Giải thích span đáng chú ý: Span `LabAgent.run` (generation) chứa toàn bộ pipeline: RAG retrieval → prompt resolve → LLM generate. Khi `rag_slow` bật, span này tăng từ ~550ms lên ~3050ms do RAG retrieval thêm 2.5s delay.

## 4. Prompt versioning

- Prompt name: `day13-chat`
- Version/label baseline: Version 1, label `baseline` và `production`
- Version/label candidate: Version 2, label `candidate`
- Trace ID của mỗi version: Xem traces trên Langfuse có metadata `prompt_name`, `prompt_label`, `prompt_version`
- Bằng chứng đổi label hoặc rollback: Thao tác trên Langfuse UI

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: **HỢP LỆ: 6/6 panel**
- Evidence dashboard: Streamlit dashboard (`dashboard_app.py`) với 6 panel:
  1. **Latency Percentiles** — P50, P95, P99 (ms), SLO: P95 ≤ 3000ms
  2. **Request Traffic** — count, rate/min, threshold: rate ≥ 1 req/min
  3. **Error Rate & Breakdown** — error_rate_pct, count by error_type, SLO: ≤ 2%
  4. **Cost Over Time** — sum/min, total (USD), SLO: total ≤ $2.50
  5. **Input & Output Tokens** — sum per field, threshold: ≤ 50,000
  6. **Quality Proxy** — mean quality_score (0–1), SLO: mean ≥ 0.75
- SLO đã chọn và lý do:
  - `latency_p95_ms ≤ 3000ms` (target 99.5%): Đảm bảo trải nghiệm chat responsive
  - `error_rate_pct ≤ 2%` (target 99.0%): Giữ độ tin cậy cao
  - `daily_cost_usd ≤ $2.50` (target 100%): Kiểm soát chi phí
  - `quality_score_avg ≥ 0.75` (target 95%): Đảm bảo chất lượng câu trả lời
- Alert rules và runbook: Xem `config/alert_rules.yaml` và `docs/alerts.md`
  - `high_latency_p95` (warning): P95 > 3000ms trong 5 phút
  - `high_error_rate` (critical): error rate > 2% trong 3 phút
  - `low_quality_score` (warning): quality < 0.75 trong 10 phút

## 6. Điều tra challenge

- Challenge ID: `day13-k3-observability-v1`
- Cohort: K3
- Incident: `rag_slow`
- Affected feature: `refund`
- Latency threshold: 2000ms

### Triệu chứng từ metrics

| Metric | Baseline (trước incident) | Sau incident | Thay đổi |
|---|---|---|---|
| P95 latency | 598 ms | 3073 ms | +414% ⚠️ |
| Error rate | 0% | 0% | Không đổi |
| Quality avg | 0.88 | 0.87 | Giảm nhẹ |
| Total cost | $0.0223 | $0.0324 | Tăng nhẹ |

**Triệu chứng chính**: P95 latency tăng vọt từ 598ms → 3073ms, vượt SLO 3000ms.

### Trace ID và log evidence

Các request bị ảnh hưởng (feature=refund, latency > 2000ms):

| Correlation ID | Feature | Latency (ms) | Timestamp |
|---|---|---|---|
| `req-c300daeb` | refund | 3055 | 2026-08-11T04:54:13Z |
| `req-a0042e1f` | refund | 3058 | 2026-08-11T04:54:16Z |
| `req-8545cdca` | refund | 3046 | 2026-08-11T04:54:19Z |
| `req-92156e84` | refund | 3073 | 2026-08-11T04:54:23Z |
| `req-264c4b75` | refund | 3054 | 2026-08-11T04:54:26Z |

Incident event trong log: `incident_enabled` tại `2026-08-11T04:54:04Z` với `payload: {name: rag_slow}`

### Root cause

**Luồng điều tra: Metrics → Traces → Logs**

1. **Metrics**: P95 latency tăng từ 598ms lên 3073ms sau khi incident được bật.
2. **Traces**: Span `LabAgent.run` (generation) cho feature `refund` có duration ~3050ms, so với baseline ~550ms. Span duy nhất chậm là phần RAG retrieval.
3. **Logs**: Log event `incident_enabled` xác nhận `rag_slow` được bật lúc `04:54:04Z`. Tất cả request sau đó với feature `refund` (match keyword trong RAG corpus) có latency >3000ms.

**Root cause**: Incident `rag_slow` inject `time.sleep(2.5)` vào hàm `retrieve()` trong `app/mock_rag.py` (line 17-18). Khi `STATE["rag_slow"]` là `True`, mỗi RAG retrieval call thêm 2.5 giây delay. Feature `refund` bị ảnh hưởng vì keyword "refund" match trong `CORPUS` dictionary, khiến hàm `retrieve()` phải đi qua đường sleep trước khi trả kết quả.

### Fix action

1. **Immediate**: Disable incident bằng `POST /incidents/rag_slow/disable` hoặc `python scripts/inject_incident.py --disable`
2. **Code fix**: Trong production, cần thêm timeout cho RAG retrieval call và circuit breaker để fallback khi retrieval chậm hơn SLO

### Preventive measure

1. **Monitoring**: Alert `high_latency_p95` sẽ fire khi P95 > 3000ms trong 5 phút, theo runbook `docs/alerts.md#alert-1`
2. **Timeout**: Thêm timeout cho RAG retrieval (ví dụ 1000ms) để không để một service chậm kéo toàn bộ pipeline
3. **Circuit breaker**: Khi RAG liên tục chậm, tự động chuyển sang fallback answer thay vì chờ
4. **Trace alerting**: Set up alert trên Langfuse khi span duration vượt threshold

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| | CP1: Logging, PII, Correlation ID | `7d193d7`, `6eca361`, `4c0bd64` | Structlog processors, PII regex patterns |
| | CP2: Dashboard, SLO, Alert rules | `d242383` | Streamlit dashboard, dashboard contract validation |
| | CP3: Challenge investigation | (commit này) | Metrics→Traces→Logs investigation flow |
