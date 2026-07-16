# ScamCheck — FCT SC Hackathon 2026

ScamCheck kiểm tra nội dung đáng ngờ theo hai bước tuần tự. Thám tử phân tích trước; chỉ
khi kết quả là **Nghi ngờ** hoặc **Nguy hiểm**, Cô tâm lý mới giải thích chiêu tác động
tâm lý trong 2–3 câu. Nếu bước Cô tâm lý gặp lỗi, kết quả Thám tử vẫn được trả về đầy đủ.

Trang web cũng có thư viện 12 kiểu lừa đảo phổ biến, bộ lọc theo nhóm và phần chi tiết cho
từng kiểu. Không có chức năng trò chuyện với nhân vật.

## Chạy dự án

- Chạy ứng dụng: `make run`
- Chạy kiểm thử offline và bảng hồi quy 24 tin: `make test-offline`
- Chạy kiểm thử Gemini có dùng thông tin xác thực: `make test-online`

OpenAPI được tạo tại `/openapi.json`. Xem [AGENTS.md](AGENTS.md) để đọc hợp đồng endpoint,
luồng triển khai, quy tắc an toàn và trách nhiệm từng tệp.
