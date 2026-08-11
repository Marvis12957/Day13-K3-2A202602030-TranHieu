# Evidence Vai C — Thái Đức (2A202601581)

Branch: `2A202601581-ThaiDuc` · Tickets C1, C2, C4, C5 (C3 xem mục cuối)

Toàn bộ output dưới đây chạy trên máy local, API ở port 8010 (port 8000 đang bị
process khác chiếm), fake LLM, chưa có key Langfuse.

---

## C1 — `error_rate_pct` trong `/metrics`

Guard chia 0 khi chưa có traffic:

```text
$ curl -s http://127.0.0.1:8010/metrics | python -m json.tool
    "traffic": 0,
    "error_breakdown": {},
    "error_rate_pct": 0.0,
```

Sau 10 request thành công (`load_test.py --concurrency 5`):

```text
{
    "traffic": 10,
    "latency_p50": 152.0,
    "latency_p95": 160.0,
    "latency_p99": 160.0,
    "avg_cost_usd": 0.0021,
    "total_cost_usd": 0.0206,
    "tokens_in_total": 330,
    "tokens_out_total": 1308,
    "error_breakdown": {},
    "error_rate_pct": 0.0,
    "quality_avg": 0.88
}
```

Với lỗi thật — bật incident `tool_fail` rồi gửi 2 request:

```text
$ curl -X POST http://127.0.0.1:8010/incidents/tool_fail/enable
$ # 2 request -> HTTP 500 500
traffic 10 | error_breakdown {'RuntimeError': 2} | error_rate_pct 16.67
```

`16.67 = 2 / (10 + 2) * 100` — đúng công thức tính trên **tổng request đã nhận**,
không phải chỉ trên request thành công. Đã tắt `tool_fail` sau khi đo.

---

## C2 — Correlation ID trong trace

`app/agent.py` lấy `correlation_id` từ `structlog.contextvars.get_contextvars()`
(do middleware của Vai A bind) và đưa vào:

- **tag của trace**: `cid:req-xxxxxxxx` → lọc được trực tiếp trên Langfuse UI
- **metadata của generation**: `correlation_id`

Kiểm chứng bằng recording client (thay `get_langfuse_client`):

```text
trace tags = ['lab', 'qa', 'claude-sonnet-4-5', 'cid:req-deadbeef']
trace meta = {'prompt_name': 'day13-chat', 'prompt_label': 'production',
              'prompt_version': 'local-v1', 'prompt_source': 'local'}

OK  tags có cid:req-deadbeef
OK  generation metadata có correlation_id
OK  trace metadata giữ đúng 4 key prompt_*
OK  user_id đã hash (không phải u01)
OK  session_id giữ nguyên
OK  không có context -> fallback 'MISSING' (không crash)
```

**Lý do không đặt vào trace metadata:** public test
`tests/test_agent_prompt_trace.py:52` assert trace metadata **bằng đúng** 4 key
`prompt_name/prompt_label/prompt_version/prompt_source`. Thêm key thứ 5 làm
pytest fail:

```text
E  AssertionError: assert {'correlation...angfuse', ...} == {'prompt_labe...version': '3'}
E    Left contains 1 more item:
E    {'correlation_id': 'MISSING'}
```

Cách hiện tại giữ pytest pass mà vẫn nối được trace ↔ log.

---

## C5 — Sub-component span

`@observe(as_type="span")` áp lên `mock_rag.retrieve` và `FakeLLM.generate`:

```text
OK  mock_rag.retrieve được @observe bọc (__wrapped__=True)
OK  FakeLLM.generate được @observe bọc (__wrapped__=True)
```

Khi có key Langfuse, waterfall sẽ có 3 tầng: `run` (generation) → `retrieve`
(span) + `generate` (span). Đây là thứ giúp CP3 phân biệt được incident nằm ở
bước RAG hay bước LLM.

---

## C4 — SLO, alert rules, runbook

```text
$ python scripts/validate_dashboard.py
HỢP LỆ: 6/6 panel có trong dashboard contract.

$ grep -rn "TODO" config/ docs/alerts.md
(không còn TODO)
```

3 alert trong `config/alert_rules.yaml`, tất cả symptom-based và đều có ngưỡng
thời gian duy trì:

| Alert | Severity | Condition | Owner |
|---|---|---|---|
| `high_latency_p95` | warning | `latency_p95 > 3000ms for 5 minutes` | on-call-engineer |
| `elevated_error_rate` | critical | `error_rate_pct > 5 for 3 minutes` | on-call-engineer |
| `cost_budget_exceeded` | warning | `daily_cost_usd > 2.5 for 15 minutes` | team-lead |

Runbook đầy đủ 3 alert trong `docs/alerts.md`, mỗi alert có 3 bước kiểm tra đầu
tiên theo đúng luồng **Metrics → Traces → Logs**.

---

## Trạng thái test và log trên branch này

```text
$ python -m pytest -q
22 passed, 2 warnings, 2 subtests passed

$ python scripts/validate_logs.py
Total log records analyzed: 21
Unique correlation IDs found: 10
Potential PII leaks detected: 0
Estimated Score: 100/100
```

Ghi chú: `langfuse==3.2.1` có trong `requirements.txt` nhưng nếu chưa cài thì
`tests/test_tracing_adapter.py` và `tests/test_agent_prompt_trace.py` sẽ fail
(2 test cần SDK thật). Chạy `pip install -r requirements.txt` trước khi chấm.

---

## C3 — Prompt versioning (CHƯA hoàn thành)

`scripts/setup_prompts.py` đã viết sẵn (tạo v1 `baseline`+`production`, v2
`candidate`, promote/rollback label `production`) nhưng **chưa chạy được** vì
máy chưa có `.env` với key Langfuse. Phần còn thiếu để lấy trọn điểm:

- [ ] `python scripts/setup_prompts.py --create`
- [ ] Chạy cùng 1 input với `LANGFUSE_PROMPT_LABEL=baseline` và `=candidate`, ghi 2 trace ID
- [ ] Ảnh danh sách 2 prompt version
- [ ] `--promote 2` → chạy 1 request → `--promote 1` (rollback), chụp ảnh trước/sau
- [ ] Ảnh ≥10 traces và 1 ảnh waterfall có span `retrieve`/`generate`
