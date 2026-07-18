# ScamCheck — FCT SC Hackathon 2026

ScamCheck là ứng dụng FastAPI giúp kiểm tra email, SMS và tin nhắn đáng ngờ. Thám tử phân
tích nội dung trước; khi kết quả là **Nghi ngờ** hoặc **Nguy hiểm**, Cô tâm lý mới giải
thích ngắn gọn chiêu tác động tâm lý đang được sử dụng.

Giao diện trong `frontend/` gồm HTML, CSS, JavaScript, bộ phân tích ngoại tuyến và logo.
Thanh điều hướng trên cùng tách ba trang **Kiểm tra**, **Lịch sử** và **Luyện tập**; nút
quay lại/tiến của trình duyệt hoạt động qua các địa chỉ `#analyze`, `#history` và
`#practice`. JavaScript
gửi nội dung đến `/analyze`, rồi hiển thị kết quả từ Gemini và số lượt gọi AI đã dùng trên
trần của phiên. Mặc định mỗi phiên có tối đa 10 lượt gọi; Thám tử và Cô tâm lý mỗi người
tính một lượt. Có thể cấu hình trần bằng `AI_SESSION_CALL_LIMIT`. Mỗi lượt Thám tử có thời
gian chờ tối đa 12 giây và lượt Cô tâm lý tối đa 6 giây. Khi hết lượt, backend trả thông
báo lịch sự mà không gọi Gemini thêm. Khi mất mạng, một bộ quy tắc bảo thủ chạy hoàn toàn
trong trình duyệt để đưa ra đánh giá sơ bộ và không thay thế kết quả Gemini. Tin nhắn và
bằng chứng được hiển thị dưới dạng văn bản, không tự động mở liên kết. Bố cục tự chuyển sang
không gian làm việc hai cột trên máy tính và vẫn giữ giao diện một cột trên thiết bị di
động. Bài luyện nhận biết gồm mười câu, đáp án, lời giải thích và điểm
số đều chạy trong trình duyệt, không gọi API hay lưu vào máy chủ.

Lịch sử trình duyệt giữ tối đa mười ảnh chụp kết quả gần nhất, gồm tin nhắn, mức rủi ro,
lý do, bằng chứng, hành động đề xuất và phản hồi Cô tâm lý. Nút **Xem kết quả** mở lại màn
hình kết quả đầy đủ mà không gọi AI lần nữa. Dữ liệu này chỉ phục vụ xem lại trên thiết bị
hiện tại; mục cũ tạo trước tính năng này không có kết quả để khôi phục nhưng vẫn có thể
được kiểm tra lại.

Sau lần tải thành công đầu tiên, service worker lưu giao diện, CSS, JavaScript, bộ phân tích
ngoại tuyến và logo. Khi mất mạng, tin nhắn được phân tích ngay trên thiết bị, không gửi đi,
không dùng lượt AI và không ghi SQLite. Kết quả luôn được ghi rõ là đánh giá sơ bộ ngoại
tuyến; khi có mạng, luồng kiểm tra tiếp tục dùng Gemini như bình thường.

## Chạy dự án

- Đồng bộ môi trường: `uv sync`
- Chạy API và giao diện: `make run`
- Chạy toàn bộ kiểm thử offline: `make test-offline`
- Chạy kiểm thử Gemini trực tuyến khi có thông tin xác thực: `make test-online`

Mở `http://127.0.0.1:8000/` để dùng giao diện. OpenAPI được tạo tại
`http://127.0.0.1:8000/openapi.json`.

Xem [AGENTS.md](AGENTS.md) để đọc hợp đồng endpoint, quy tắc an toàn và trách nhiệm của
từng tệp.
