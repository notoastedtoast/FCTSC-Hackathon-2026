# ScamCheck — FCT SC Hackathon 2026

ScamCheck là ứng dụng FastAPI giúp kiểm tra email, SMS và tin nhắn đáng ngờ. Thám tử phân
tích nội dung trước; khi kết quả là **Nghi ngờ** hoặc **Nguy hiểm**, Cô tâm lý mới giải
thích ngắn gọn chiêu tác động tâm lý đang được sử dụng.

Giao diện trong `frontend/` gồm HTML, CSS, JavaScript, bộ phân tích ngoại tuyến và logo.
Thanh điều hướng trên cùng tách ba trang **Kiểm tra**, **Lịch sử** và **Luyện tập**; nút
quay lại/tiến của trình duyệt hoạt động qua các địa chỉ `#analyze`, `#history` và
`#practice`. JavaScript
gửi nội dung đến `/analyze`, rồi hiển thị kết quả từ nhà cung cấp AI trực tuyến và số lượt gọi AI đã dùng trên
trần của phiên. Mặc định mỗi phiên có tối đa 10 lượt gọi; Thám tử và Cô tâm lý mỗi người
tính một lượt. Có thể cấu hình trần bằng `AI_SESSION_CALL_LIMIT`. Mỗi lượt Thám tử có thời
gian chờ tối đa 12 giây và lượt Cô tâm lý tối đa 6 giây. Khi hết lượt, backend trả thông
báo lịch sự mà không gọi AI thêm. Khi mất mạng, một bộ quy tắc bảo thủ chạy hoàn toàn
trong trình duyệt để đưa ra đánh giá sơ bộ và không thay thế kết quả trực tuyến. Tin nhắn và
bằng chứng được hiển thị dưới dạng văn bản, không tự động mở liên kết. Bố cục tự chuyển sang
không gian làm việc hai cột trên máy tính và vẫn giữ giao diện một cột trên thiết bị di
động. Bài luyện nhận biết gồm mười câu, đáp án, lời giải thích và điểm
số đều chạy trong trình duyệt, không gọi API hay lưu vào máy chủ.

Lịch sử trình duyệt giữ tối đa mười ảnh chụp kết quả gần nhất, gồm tin nhắn, mức rủi ro,
lý do, bằng chứng, hành động đề xuất và phản hồi Cô tâm lý. Dữ liệu này chỉ phục vụ xem lại
trên thiết bị hiện tại; mục cũ tạo trước tính năng này vẫn có thể được kiểm tra lại.

Sau lần tải thành công đầu tiên, service worker lưu giao diện, CSS, JavaScript, bộ phân tích
ngoại tuyến và logo. Khi mất mạng, tin nhắn được phân tích ngay trên thiết bị, không gửi đi,
không dùng lượt AI và không ghi PostgreSQL. Kết quả luôn được ghi rõ là đánh giá sơ bộ ngoại
tuyến. Nếu kết nối bị gián đoạn trong lúc AI đang xử lý, trình duyệt giữ tin nhắn cùng
mã yêu cầu trong tab và tự lấy lại đúng kết quả khi có mạng; gửi lại cùng mã không tạo thêm
lượt AI hoặc bản ghi phân tích.

## Cấu trúc thư mục

```text
FCTSC-Hackathon-2026/
├── frontend/                  # Giao diện web và chức năng ngoại tuyến
│   ├── index.html             # Khung trang và các khu vực điều hướng
│   ├── styles.css             # Giao diện responsive
│   ├── app.js                 # Phân tích, lịch sử, thư viện và luyện tập
│   ├── offline-analyzer.js    # Đánh giá sơ bộ khi không có mạng
│   ├── service-worker.js      # Lưu bộ khung ứng dụng để chạy offline
│   └── scamcheck-logo.png
├── src/                       # Backend FastAPI
│   ├── app.py                 # Entrypoint triển khai Vercel
│   ├── main.py                # Routes, middleware và luồng xử lý API
│   ├── analyzer.py            # Chuỗi model Gemini/Groq và kiểm tra kết quả AI
│   ├── database.py            # Lưu trữ PostgreSQL/Supabase
│   ├── schemas.py             # Kiểu dữ liệu và hợp đồng API
│   ├── config.py              # Cấu hình từ biến môi trường
│   ├── catalog.py             # Truy xuất thư viện loại lừa đảo
│   ├── characters.py          # Cấu hình Cô tâm lý
│   └── data/
│       └── scam_types.json    # Dữ liệu thư viện lừa đảo
├── tests/                     # Kiểm thử API, model, database và frontend
│   └── labeled_messages.json  # Bộ 24 tin nhắn hồi quy
├── .env.example               # Mẫu biến môi trường, không chứa khóa thật
├── Makefile                   # Lệnh run và test ngắn gọn
├── pyproject.toml             # Metadata và dependencies Python
├── uv.lock                    # Phiên bản dependency đã khóa
├── pyrightconfig.json         # Cấu hình kiểm tra kiểu dữ liệu
├── AGENTS.md                  # Hợp đồng kỹ thuật và quy tắc bảo trì
└── test.py                    # Thử nghiệm mạng cũ, không thuộc bộ test chính
```

## Chạy dự án

- Đồng bộ môi trường: `uv sync`
- Sao chép `.env.example` thành `.env`, rồi đặt khóa Gemini và `DATABASE_URL`.
- Chạy API và giao diện: `make run`
- Chạy toàn bộ kiểm thử offline: `make test-offline`
- Chạy kiểm thử Gemini trực tuyến khi có thông tin xác thực: `make test-online`

Mở `http://127.0.0.1:8000/` để dùng giao diện. OpenAPI được tạo tại
`http://127.0.0.1:8000/openapi.json`.

## Supabase và Vercel

1. Tạo dự án Supabase, mở **Connect**, chọn **Transaction pooler** và sao chép chuỗi kết
   nối cổng `6543`. Chế độ này phù hợp với các hàm serverless ngắn hạn của Vercel.
2. Trong Vercel, thêm `DATABASE_URL` cho cả Production và Preview. Thay mật khẩu giữ chỗ
   bằng mật khẩu cơ sở dữ liệu và giữ `sslmode=require`.
3. Thêm `GEMINI_API_KEY`. Cấu hình trong `.env.example` dùng `gemini-3.5-flash`, sau đó
   `gemini-2.5-flash`. Có thể đổi bằng `GEMINI_MODEL` và
   `GEMINI_FALLBACK_MODEL`.
4. Để bật lớp dự phòng thứ ba, thêm `GROQ_API_KEY`; `GROQ_MODEL` mặc định là
   `openai/gpt-oss-20b`.
5. Deploy lại. `src/app.py` là entrypoint FastAPI mà Vercel tự nhận diện; ứng dụng tự tạo
   và nâng cấp ba bảng cần thiết khi khởi động.

Không đưa `DATABASE_URL` vào JavaScript hoặc biến môi trường có tiền tố công khai. Các
bảng ứng dụng bật Row Level Security và chỉ backend kết nối bằng thông tin cơ sở dữ liệu.
Dữ liệu trong `app.db` cũ không được tự động sao chép sang Supabase.

Xem [AGENTS.md](AGENTS.md) để đọc hợp đồng endpoint, quy tắc an toàn và trách nhiệm của
từng tệp.
