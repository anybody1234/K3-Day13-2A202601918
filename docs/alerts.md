# Alert và Runbook

Mỗi alert dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: high_latency_p95
- Severity: warning
- SLI/SLO liên quan: latency_p95_ms <= 3000ms (target 99.5%)
- Điều kiện và thời gian duy trì: P95 latency > 3000ms liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Phản hồi chậm, trải nghiệm chat bị gián đoạn, người dùng có thể timeout
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra `/metrics` endpoint xem `latency_p95` hiện tại
  2. Mở trace trên Langfuse, lọc theo latency cao, xác định span nào chậm (RAG retrieval, LLM call)
  3. Grep log với `correlation_id` của request chậm, tìm event `response_sent` có `latency_ms` cao
- Mitigation tạm thời: Tắt incident nếu đang bật (`POST /incidents/{name}/disable`), tăng timeout hoặc giảm concurrency
- Owner: on-call engineer

## Alert 2

- Tên: high_error_rate
- Severity: critical
- SLI/SLO liên quan: error_rate_pct <= 2% (target 99.0%)
- Điều kiện và thời gian duy trì: Error rate > 2% liên tục trong 3 phút
- Ảnh hưởng tới người dùng: Request thất bại, người dùng nhận HTTP 500, không thể sử dụng tính năng chat
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra `/metrics` endpoint xem `error_breakdown` để biết loại lỗi nào chiếm đa số
  2. Grep log tìm event `request_failed`, lọc theo `error_type` và `correlation_id`
  3. Mở trace trên Langfuse cho các request lỗi, xác định span nào fail (tool_call, LLM, RAG)
- Mitigation tạm thời: Tắt incident gây lỗi, restart service nếu lỗi do memory/state, fallback sang prompt local nếu Langfuse gặp sự cố
- Owner: on-call engineer

## Alert 3

- Tên: low_quality_score
- Severity: warning
- SLI/SLO liên quan: quality_score_avg >= 0.75 (target 95.0%)
- Điều kiện và thời gian duy trì: Mean quality score < 0.75 liên tục trong 10 phút
- Ảnh hưởng tới người dùng: Câu trả lời kém chất lượng, không chính xác hoặc không liên quan đến câu hỏi
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra `/metrics` endpoint xem `quality_avg` và so sánh với baseline
  2. Mở trace trên Langfuse, lọc theo `quality_score` thấp, kiểm tra prompt version đang dùng
  3. Grep log event `response_sent` có `quality_score` thấp, kiểm tra `feature` và `model` tương ứng
- Mitigation tạm thời: Rollback prompt về version/label trước đó nếu vừa thay đổi prompt, kiểm tra RAG retrieval context có đúng không
- Owner: ai-team
