# Giao diện ScamCheck

Đây là giao diện HTML, CSS và JavaScript không cần thư viện ngoài, được FastAPI
phục vụ. Giao diện vẫn tách biệt với mã ứng dụng: khi xóa thư mục `frontend/`,
FastAPI sẽ tự động không gắn giao diện này.

## Chạy trên máy cục bộ

Khởi động FastAPI từ thư mục gốc của dự án:

```sh
uv run uvicorn src.main:app --reload
```

Mở <http://127.0.0.1:8000>. Giao diện và API dùng chung một origin nên không cần
cấu hình CORS hay chạy thêm máy chủ giao diện.

## Hiển thị kết quả nhiều phần

Giao diện đọc phản hồi `/analyze` mới theo các trường `detective`, `character` và
`character_notice`. Kết quả của Thám tử và từng nhân vật được hiển thị thành các phần có
tiêu đề riêng; tiêu đề và nội dung nhân vật lấy trực tiếp từ API nên có thể thêm nhân vật
mới ở backend mà không cần sửa giao diện. Phản hồi phân tích đã lưu theo định dạng cũ vẫn
được chuẩn hóa và hiển thị như trước.
