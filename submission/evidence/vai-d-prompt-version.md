# Evidence Vai D — Prompt Versioning (v1/v2 + label + rollback)

> Prompt name: `day13-chat` (text) trên Langfuse Cloud.
> Người tạo prompt + chạy flow: Thái Đức (Vai C) — evidence tổng hợp bởi Trung Hiếu (Vai D).

## 1. Hai phiên bản prompt

- **v1 (baseline)** — labels `baseline` + `production`:
  ```
  Feature={{feature}}
  Docs={{docs}}
  Question={{message}}
  ```
- **v2 (candidate)** — label `candidate` (thêm ràng buộc độ dài, giữ nguyên 3 biến contract):
  ```
  Feature={{feature}}
  Docs={{docs}}
  Question={{message}}
  Answer concisely under 200 words.
  ```

## 2. Hai trace chứng minh hai version/label khác nhau (cùng 1 input)

Request: `"What is your refund policy?"` (feature=qa)

| Label | Trace ID | prompt_name | prompt_label | prompt_version | prompt_source |
|---|---|---|---|---|---|
| `production` (v1) | `d0dd8d0f609767ebf898f2679f6a5bd5` | day13-chat | production | **1** | langfuse |
| `candidate` (v2) | `b782eff7771dc844c88fb2e80cc47002` | day13-chat | candidate | **2** | langfuse |

Cả hai trace đều có `prompt_source=langfuse` (không phải `local-fallback`), tức là
prompt được fetch thật từ Langfuse, không phải template local.

## 3. Đổi label + rollback

```
# Bước 1: promote production từ v1 -> v2
$ python scripts/setup_prompts.py --promote 2
Label production -> v2 (labels hiện tại: ['production', 'candidate', 'latest'])

# Bước 2: rollback production về v1
$ python scripts/setup_prompts.py --promote 1
Label production -> v1 (labels hiện tại: ['production', 'baseline'])

# Xác minh sau rollback: production trỏ về v1
Sau rollback: production hiện đang trỏ về v1
```

## 4. Cách tái hiện

```bash
python scripts/setup_prompts.py --create          # tạo v1 + v2
# chạy API với LANGFUSE_PROMPT_LABEL=production/candidate rồi gửi cùng 1 input
python scripts/setup_prompts.py --promote 2       # production -> v2
python scripts/setup_prompts.py --promote 1       # rollback production -> v1
```