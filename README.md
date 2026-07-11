# OCR & VLM Synthetic Data Extraction Tools

Bộ công cụ hỗ trợ chuẩn bị dữ liệu huấn luyện OCR và Layout Analysis cho các mô hình Vision-Language Models (VLMs) từ tài liệu PDF và từ internet (tập dữ liệu FineWeb-2).

---

## 📂 Danh sách các file trong thư mục dự án (Root Files)

- **[extract_pdf_layout.py](extract_pdf_layout.py)**: Script Python chính sử dụng thư viện `PyMuPDF` (`fitz`) để phân tích cú pháp file PDF, render ảnh trang giấy, trích xuất tọa độ văn bản (từ, dòng, đoạn) và ảnh kèm theo.
- **[scrape_fineweb_pdf.py](scrape_fineweb_pdf.py)**: Script thu thập dữ liệu web từ tập dữ liệu `HuggingFaceFW/fineweb-2` (subset tiếng Việt `vie_Latn`), lọc theo năm (2021 -> 2026), tự động cuộn trang để kích hoạt lazy loading và in trang web thành PDF bằng trình duyệt Playwright ngầm trước khi chuyển sang pipeline trích xuất.
- **[requirements.txt](requirements.txt)**: Khai báo tất cả các thư viện Python cần thiết cho dự án.
- **[pharmarcity.pdf](pharmarcity.pdf)**: File PDF tài liệu mẫu để kiểm thử công cụ trích xuất.
- **[README.md](README.md)**: File hướng dẫn sử dụng và giải thích kỹ thuật này.
- **[.gitignore](.gitignore)**: Cấu hình Git để loại bỏ thư mục kết quả `output_dataset` và môi trường ảo `.venv` khỏi commit.

---

## 🛠️ Hướng dẫn cài đặt (Setup)

Khuyến khích sử dụng môi trường ảo độc lập qua công cụ `uv` để cài đặt nhanh chóng và tránh xung đột thư viện hệ thống:

1. **Khởi tạo môi trường ảo**:
   ```bash
   uv venv .venv
   ```

2. **Kích hoạt môi trường ảo**:
   - Trên Linux/macOS:
     ```bash
     source .venv/bin/activate
     ```
   - Trên Windows (Command Prompt):
     ```cmd
     .venv\Scripts\activate.bat
     ```

3. **Cài đặt thư viện từ `requirements.txt`**:
   ```bash
   uv pip install -r requirements.txt
   ```

4. **Cài đặt driver cho Playwright**:
   ```bash
   .venv/bin/playwright install chromium
   ```

---

## 💻 Hướng dẫn sử dụng

### 1. Thu thập dữ liệu web từ FineWeb-2 (`scrape_fineweb_pdf.py`)

Công cụ này stream trực tiếp tập dữ liệu `HuggingFaceFW/fineweb-2` subset tiếng Việt, lọc các bài viết từ năm 2021 đến 2026, tải trang web dưới dạng PDF và trích xuất layout tự động.

**Cú pháp cơ bản:**
```bash
.venv/bin/python scrape_fineweb_pdf.py --num-samples <so_luong_mau> --output <thu_muc_dau_ra> [options]
```

**Các tham số tùy chọn (Options):**
- `--num-samples`: Số lượng trang web cần tải và trích xuất thành công (mặc định: `20`).
- `--output`: Thư mục lưu trữ kết quả (mặc định: `output_dataset/fineweb_samples`).
- `--start-year` / `--end-year`: Khoảng năm bài viết được crawl để lọc dữ liệu (mặc định: `2021` đến `2026`).
- `--granularity`: Cấp độ trích xuất chữ (`word` - mặc định, `line`, `block`).
- `--dpi`: Độ phân giải ảnh đầu ra khi render PDF (mặc định: `150`).
- `--normalize`: Chuẩn hóa tọa độ bounding box về dải `[0, 1000]`.
- `--extract-images`: Trích xuất cả các file ảnh/logo có trong trang web ra thư mục riêng và lưu đường dẫn vào JSON.

**Ví dụ chạy thực tế:**
```bash
# Tải 20 trang web tiếng Việt (2021-2026), in PDF và trích xuất layout block, tọa độ chuẩn hóa, cắt ảnh
.venv/bin/python scrape_fineweb_pdf.py --num-samples 20 --granularity block --normalize --extract-images
```

### 2. Trích xuất dữ liệu trực tiếp từ file PDF có sẵn (`extract_pdf_layout.py`)

Công cụ này xử lý trực tiếp các file PDF có sẵn của bạn để sinh ra dataset.

**Cú pháp cơ bản:**
```bash
.venv/bin/python extract_pdf_layout.py --pdf <duong_dan_file_pdf> --output <thu_muc_output> [options]
```

**Ví dụ chạy thực tế:**
```bash
.venv/bin/python extract_pdf_layout.py --pdf pharmarcity.pdf --output output_dataset/pharmarcity_layout --extract-images
```

---

## 📁 Cấu trúc dữ liệu đầu ra (`output_dataset`)

Thư mục kết quả sau khi chạy lệnh trích xuất được phân chia rõ ràng theo từng tài liệu để tránh ghi đè dữ liệu:

```text
output_dataset/fineweb_samples/
├── doc_000/
│   ├── document.pdf              # File PDF gốc tải về từ trang web
│   ├── url.txt                   # Đường dẫn link trang web nguồn của tài liệu này
│   ├── page_000.png              # Ảnh render trang 1
│   ├── layout_000.json           # Nhãn layout và OCR trang 1
│   ├── viz_page_000.png          # Ảnh xem trước trực quan (khung xanh cho text, đỏ cho ảnh)
│   └── extracted_images/         # Thư mục chứa các ảnh con được trích xuất trên trang
│       ├── page_000_raw_0.png    # Ảnh gốc nhúng bên trong PDF
│       ├── page_000_crop_0.png   # Ảnh cắt thực tế từ giao diện hiển thị
│       └── ...
└── doc_001/
    ├── ...
```

---

## 💡 Lưu ý kỹ thuật (Troubleshooting & Tips)

### Giải quyết vấn đề trang trắng/thiếu nội dung (Lazy Loading & Print CSS)

Khi tải các trang web hiện đại về làm PDF ngầm, chúng ta thường gặp phải 2 vấn đề lớn:
1. **Lazy Loading**: Các trang web chỉ tải ảnh hoặc nội dung khi người dùng cuộn chuột tới vị trí đó. Nếu in PDF trực tiếp ngay sau khi mở trang, các phần ở giữa và dưới trang sẽ bị trống hoàn toàn.
2. **Print Stylesheet (@media print)**: Nhiều trang web áp dụng các luật CSS ẩn đi các thành phần lớn như menu, banner, sidebar, thậm chí cả nội dung chính khi in để tiết kiệm giấy in.

**Cách giải quyết đã được tích hợp trong `scrape_fineweb_pdf.py`**:
*   **Tự động cuộn trang (Scroll-to-bottom)**: Trước khi in PDF, Playwright sẽ chạy một hàm Javascript cuộn chuột tự động từ đầu trang xuống cuối trang để ép trình duyệt kích hoạt và tải toàn bộ ảnh/nội dung lười, sau đó cuộn ngược lại lên đầu để chuẩn bị in.
*   **Giả lập giao diện màn hình (Emulate Screen)**: Gọi hàm `page.emulate_media(media="screen")` để bắt buộc trình duyệt sử dụng giao diện hiển thị trên màn hình máy tính để in PDF thay vì bộ CSS rút gọn dành cho máy in giấy. Cách này giúp giữ nguyên đầy đủ layout, banner và các khối bài viết.