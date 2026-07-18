# ScamCheck — FCT SC Hackathon 2026

ScamCheck là ứng dụng FastAPI giúp kiểm tra email, SMS và tin nhắn đáng ngờ. Thám tử phân
tích nội dung trước; khi kết quả là **Nghi ngờ** hoặc **Nguy hiểm**, Cô tâm lý mới giải
thích ngắn gọn chiêu tác động tâm lý đang được sử dụng.

Giao diện trong `frontend/` gồm `index.html`, `styles.css`, `app.js` và logo. JavaScript
gửi nội dung đến `/analyze`, rồi hiển thị kết quả từ Gemini và số lượt gọi AI đã thực
hiện trong phiên. Không có giới hạn lượt gọi theo phiên, bộ phân loại từ khóa hay trình
phân tích đường dẫn cục bộ; tin nhắn và bằng chứng được hiển thị dưới dạng văn bản, không
tự động mở liên kết. Bố cục tự chuyển sang chế độ màn hình rộng trên máy tính và vẫn giữ
giao diện một cột trên thiết bị di động. Bài luyện nhận biết gồm mười câu, đáp án, lời
giải thích và điểm số đều chạy trong trình duyệt, không gọi API hay lưu vào máy chủ.

## Chạy dự án

- Đồng bộ môi trường: `uv sync`
- Chạy API và giao diện: `make run`
- Chạy toàn bộ kiểm thử offline: `make test-offline`
- Chạy kiểm thử Gemini trực tuyến khi có thông tin xác thực: `make test-online`

Mở `http://127.0.0.1:8000/` để dùng giao diện. OpenAPI được tạo tại
`http://127.0.0.1:8000/openapi.json`.

Xem [AGENTS.md](AGENTS.md) để đọc hợp đồng endpoint, quy tắc an toàn và trách nhiệm của
từng tệp.
