# ScamCheck - FCT SC Hackathon 2026
Hello moi nguoi, truoc khi push code vao branch "main" thi minh tao 1 brach moi cua minh nhes:D

Một cái nữa là nếu muốn push code lên main brach thì bàn bạc với nhau phiên bản cuối nhé vì branch này sẽ là branch chứa source code
của phiên bản stable nhất nhé.
Chúc mọi người "vibe" code vui vẻ🫠

## API storage

Successful `POST /analyze` requests are stored in `app.db` in the current directory.
Set `DATABASE_PATH` only if you need to override that location. The API response includes the generated
database ID alongside the analysis:

```json
{
  "confidence": 0.91,
  "reasoning": "The message creates urgency and requests credentials.",
  "indicators": ["Urgency", "Credential request"],
  "scenarios": [
    {"scenario": "malicious_fake_links", "detected": true, "confidence": 0.94, "evidence": "Liên kết dùng tên miền giả mạo."},
    {"scenario": "close_contact_impersonation_conflict", "detected": false, "confidence": 0.03, "evidence": "Không có bằng chứng."},
    {"scenario": "authority_or_business_impersonation", "detected": false, "confidence": 0.08, "evidence": "Không có bằng chứng."},
    {"scenario": "credential_or_otp_theft", "detected": true, "confidence": 0.88, "evidence": "Tin nhắn yêu cầu thông tin đăng nhập."},
    {"scenario": "payment_or_invoice_fraud", "detected": false, "confidence": 0.04, "evidence": "Không có bằng chứng."},
    {"scenario": "investment_or_crypto_fraud", "detected": false, "confidence": 0.01, "evidence": "Không có bằng chứng."},
    {"scenario": "romance_or_relationship_fraud", "detected": false, "confidence": 0.01, "evidence": "Không có bằng chứng."},
    {"scenario": "prize_refund_or_advance_fee", "detected": false, "confidence": 0.02, "evidence": "Không có bằng chứng."},
    {"scenario": "job_or_task_fraud", "detected": false, "confidence": 0.01, "evidence": "Không có bằng chứng."},
    {"scenario": "tech_support_or_remote_access", "detected": false, "confidence": 0.03, "evidence": "Không có bằng chứng."},
    {"scenario": "extortion_or_threats", "detected": true, "confidence": 0.79, "evidence": "Tin nhắn đe dọa khóa tài khoản."},
    {"scenario": "marketplace_or_delivery_fraud", "detected": false, "confidence": 0.02, "evidence": "Không có bằng chứng."}
  ],
  "id": "a1b2c3d4e5f60718293a4b5c6d7e8f90"
}
```

Gemini must return every scenario above in that order. `indicators` can still report scam
signals that do not fit one of the fixed scenarios.

The frontend can retrieve the complete stored record using `GET /analyses/{id}`:

The response contains the same `scenarios` array; it is omitted below only for brevity.

```json
{
  "confidence": 0.91,
  "reasoning": "The message creates urgency and requests credentials.",
  "indicators": ["Urgency", "Credential request"],
  "id": "a1b2c3d4e5f60718293a4b5c6d7e8f90",
  "text": "Act now and send your password",
  "source": "sms",
  "created_at": "2026-07-14T12:00:00"
}
```
