# Evidence — Danh sách Traces (≥10) trên Langfuse

> Nguồn: `GET /api/public/traces` project Langfuse Cloud (host `cloud.langfuse.com`).
> Thu thập: Trung Hiếu (Vai D) · Ngày: 2026-08-11.
> 15 trace liệt kê dưới đây (yêu cầu tối thiểu 10) — lấy từ các lần chạy
> `load_test.py`, challenge `rag_slow` và kiểm tra prompt version.

| # | Trace ID | name | latency (s) | prompt_version | tag `cid:` |
|---|---|---|---|---|---|
| 1 | `b782eff7771dc844c88fb2e80cc47002` | run | 1.254 | **2** (candidate) | `req-d71edb24` |
| 2 | `d0dd8d0f609767ebf898f2679f6a5bd5` | run | 1.256 | **1** (production) | `req-f11fa800` |
| 3 | `67ba3de6110ece0c9aca09250f36f74c` | run | 3.841 | local-v1 | `req-16782bca` |
| 4 | `f14168752104459f4a0af0f7ecfd2246` | run | 3.663 | local-v1 | `req-2d4a3370` |
| 5 | `b44173150cb303648bf06956e978e69d` | run | 3.682 | local-v1 | `req-336fca6a` |
| 6 | `4f744bf987a3a0e10945c5318ed2fe21` | run | 3.643 | local-v1 | `req-b2c33b4a` |
| 7 | `9cf244ac60fcab6b71316a8960959d1c` | run | 3.790 | local-v1 | `req-1d72f2b8` |
| 8 | `9e2921af6dc8c87c046c5bb5177686d1` | run | 1.157 | local-v1 | `req-7dd4f156` |
| 9 | `fa8a621ac8b8e36d3f1c71632cb9beba` | run | 1.179 | local-v1 | `req-8671a301` |
| 10 | `554222a736bce2ccd17af4c8247813c2` | run | 1.244 | local-v1 | `req-34ad9b10` |
| 11 | `032fcf79869182ee73035b5127e36446` | run | 1.162 | local-v1 | `req-b2b3e66d` |
| 12 | `b614bb36f8c6afe347a629702491795a` | run | 1.175 | local-v1 | `req-2dc5b94d` |
| 13 | `1bf7ab35edb82edd62ddd9b11b22b27d` | run | 1.159 | local-v1 | `req-208269d3` |
| 14 | `bf40bef808e0dc5e653da449ebd733ab` | run | 1.302 | local-v1 | `req-a7b479d9` |
| 15 | `3ed0d7cf14a613b70c406b0e591308f1` | run | 2.731 | local-v1 | `req-d01fe24f` |

## Ghi chú

- **Trace #1–#2** (`prompt_version=2` candidate, `prompt_version=1` production) là
  bằng chứng prompt versioning — xem `vai-d-prompt-version.md`.
- **Trace #3–#7** (latency ~3.6–3.8s) là 5 trace của incident `rag_slow` trong
  challenge — xem `vai-d-challenge.md` và `trace-waterfall.md`.
- Mỗi trace có tag `cid:req-<8hex>` để nối được với log trong `data/logs.jsonl`
  (luồng Metrics → Traces → Logs).

## Cách kiểm tra lại

```bash
# Dùng API public của Langfuse (Basic auth bằng public/secret key)
curl -u "$LANGFUSE_PUBLIC_KEY:$LANGFUSE_SECRET_KEY" \
  "https://cloud.langfuse.com/api/public/traces?limit=15"
```