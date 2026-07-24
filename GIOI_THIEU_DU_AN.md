   # ScamCheck — Kiểm tra tin nhắn có dấu hiệu lừa đảo

   ## Sản phẩm làm gì?

   ScamCheck là ứng dụng web tiếng Việt giúp kiểm tra nhanh email, SMS hoặc tin nhắn đáng ngờ trước khi người dùng bấm liên kết, cung cấp thông tin hay chuyển tiền.

   Người dùng chỉ cần dán nguyên văn tin nhắn vào ứng dụng. ScamCheck kết hợp phân tích ngữ cảnh bằng Gemini với các quy tắc kiểm tra tại chỗ để:

   - xếp loại rủi ro ở mức **thấp**, **trung bình** hoặc **cao**;
   - chỉ ra những đoạn đáng chú ý và giải thích lý do;
   - đề xuất các hành động an toàn nên thực hiện tiếp theo;
   - hướng dẫn xử lý nếu người dùng đã bấm liên kết, cung cấp thông tin hoặc chuyển tiền.

   ScamCheck là công cụ hỗ trợ nhận biết và giáo dục. Kết quả không thay thế xác minh chính thức từ ngân hàng, cơ quan chức năng hoặc đơn vị cung cấp dịch vụ.

   ## Các tính năng đã hoàn thành

   - Phân tích bằng Gemini, kết hợp quy tắc nhận biết nội dung gây áp lực, liên kết rút gọn và tên miền đáng ngờ.
   - Hiển thị mức rủi ro, lập luận, đoạn trích đáng chú ý và khuyến nghị.
   - “Cô tâm lý” giúp người dùng bình tĩnh; “Người ứng cứu” hướng dẫn các bước cần làm theo tình huống.
   - Thư viện 12 hình thức lừa đảo phổ biến, có tìm kiếm và bộ lọc.
   - Lịch sử trong phiên, hỗ trợ xem lại, kiểm tra lại và xóa kết quả.
   - Phân tích sơ bộ khi ngoại tuyến và lưu tối đa 10 kết quả trên thiết bị.
   - Bài luyện tập nhận biết lừa đảo, nhập liệu bằng giọng nói và tải kết quả thành ảnh.
   - Giao diện phù hợp máy tính và điện thoại, có chữ lớn, tương phản cao và giảm chuyển động.

   ## Cách chạy trên máy

   ### Yêu cầu

   - Python 3.14 trở lên.
   - Trình quản lý gói `uv`.
   - Khóa Gemini API để sử dụng tính năng phân tích trực tuyến.

   ### Các bước

   1. Tại thư mục dự án, cài phụ thuộc:

      ```sh
      uv sync
      ```

   2. Sao chép `.env.example` thành `.env` và điền khóa Gemini API:

      ```env
      GEMINI_API_KEY=khóa-api-của-bạn
      BASE_URL=https://generativelanguage.googleapis.com/v1beta/
      GEMINI_MODEL=gemini-3.5-flash
      AI_SESSION_CALL_LIMIT=10
      ```

   3. Khởi động ứng dụng:

      ```sh
      uv run uvicorn src.main:app --reload
      ```

   4. Mở trình duyệt tại:

      ```text
      http://127.0.0.1:8000/
      ```

   Nếu thiếu khóa API, giao diện vẫn khởi động nhưng không thể phân tích trực tuyến. Lịch sử trực tuyến và bộ đếm lượt AI sẽ đặt lại khi máy chủ khởi động lại; lịch sử ngoại tuyến nằm riêng trên trình duyệt.

   ## Công nghệ chính

   - **Backend:** Python, FastAPI, Pydantic và HTTPX.
   - **AI:** Google Gemini.
   - **Frontend:** HTML, CSS và JavaScript thuần.
   - **Lưu trữ hiện tại:** SQLite trong bộ nhớ cho lịch sử trực tuyến; `localStorage` cho lịch sử ngoại tuyến.

   ## Thông tin nhóm

   - **Tên dự án:** ScamCheck.
   - **Sự kiện:** FCTSC Hackathon 2026.
   - **Kho mã nguồn:** https://github.com/notoastedtoast/FCTSC-Hackathon-2026
   - **Các tên đóng góp được ghi nhận trong lịch sử Git:** asterized, haidangleo11, kme12345678 và Kringerlings.
