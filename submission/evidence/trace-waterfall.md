# Evidence — Trace Waterfall (Langfuse)

> Trace ID: `b44173150cb303648bf06956e978e69d` (incident `rag_slow` — challenge)
> Tag: `cid:req-336fca6a` · name: `run` · tổng latency: **3.682s**
> Thu thập: `GET /api/public/traces/{id}` · Trung Hiếu (Vai D)

## Waterfall (3 tầng)

```text
run (GENERATION)        |████████████████████████████████████████████░░| 3.682 s
├── retrieve (SPAN)     |████████████████████████████████████████░░░░░░| 2.506 s   ← chậm
└── generate (SPAN)     |██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░| 0.166 s
```

## Dữ liệu span thật (từ API Langfuse)

| Span | Type | Latency | % tổng | Ghi chú |
|---|---|---|---|---|
| `run` | GENERATION | 3.682 s | 100% | span cha — nhóm toàn bộ agent |
| `retrieve` | SPAN | **2.506 s** | **68%** | RAG retrieval — **span bất thường** |
| `generate` | SPAN | 0.166 s | 4.5% | LLM giả (sleep 0.15s) — bình thường |

## Đọc waterfall

- Span `retrieve` chiếm **68%** tổng latency (2.506 / 3.682) — khớp chính xác
  `time.sleep(2.5)` mà incident `rag_slow` chèn vào `retrieve()` trong
  `app/mock_rag.py`.
- Span `generate` chỉ 0.166s — LLM không phải nút thắt.
- Kết luận: **root cause nằm ở khâu RAG retrieval**, không phải LLM hay API.
  Xem chi tiết điều tra: `vai-d-challenge.md`.

## Cách kiểm tra lại

```bash
curl -u "$LANGFUSE_PUBLIC_KEY:$LANGFUSE_SECRET_KEY" \
  "https://cloud.langfuse.com/api/public/traces/b44173150cb303648bf06956e978e69d"
```