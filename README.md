# OCR & VLM Synthetic Data Extraction Tools

Bộ công cụ hỗ trợ chuẩn bị dữ liệu huấn luyện OCR và Layout Analysis cho các mô hình Vision-Language Models (VLMs) từ định dạng tài liệu PDF và source HTML.

---

## 🚀 Tính năng nổi bật

1. **Trích xuất dữ liệu từ PDF (`extract_pdf_layout.py`)**:
   - Tự động chuyển đổi các trang PDF thành file ảnh chất lượng cao (tự chọn DPI).
   - Trích xuất tọa độ Bounding Box của chữ ở các cấp độ: từ đơn (`word`), dòng (`line`) hoặc khối văn bản (`block`).
   - Tự động phát hiện vị trí ảnh/logo, trích xuất cả file ảnh nhúng gốc (`raw`) lẫn ảnh cắt thực tế (`crop`).
   - Hỗ trợ xuất tọa độ dưới dạng pixel thực tế hoặc chuẩn hóa về dải `[0, 1000]` (phù hợp với các mô hình LayoutLM, Donut, Kosmos-2.5, v.v.).
   - Vẽ khung trực quan hóa (khung xanh cho chữ, khung đỏ cho ảnh) giúp kiểm tra trực quan chất lượng nhãn (QA).

2. **Sinh dữ liệu trực tiếp từ HTML (`html_to_synthetic.py`)**:
   - Render mã nguồn HTML trên trình duyệt không đầu (Headless Browser) qua thư viện Playwright.
   - Chụp toàn bộ trang web (Full Page Screenshot) và thu thập tọa độ chuẩn xác của các thẻ DOM chỉ định (`p`, `img`, `h1`, `button`, v.v.).
   - Tránh hiện tượng sai lệch thứ tự đọc (reading order) thường thấy trên PDF.

---

## 🛠️ Hướng dẫn cài đặt (Setup)

### Yêu cầu hệ thống
- Python 3.10 trở lên.

### Cài đặt thư viện

Bạn nên cài đặt các thư viện cần thiết bằng pip:

```bash
# Cài đặt thư viện cho công cụ PDF (đã có sẵn trong môi trường mặc định)
pip install pymupdf pillow

# Cài đặt thư viện cho công cụ HTML (Playwright)
pip install playwright
playwright install chromium
```

---

## 💻 Hướng dẫn sử dụng

### 1. Trích xuất dữ liệu từ PDF (`extract_pdf_layout.py`)

Công cụ này xử lý các file PDF (được lưu trực tiếp từ web hoặc file gốc) để sinh ra dataset.

**Cú pháp cơ bản:**
```bash
python3 extract_pdf_layout.py --pdf <duong_dan_file_pdf> --output <thu_muc_output> [options]
```

**Các tham số tùy chọn (Options):**
- `--granularity`: Cấp độ trích xuất chữ (`word` - mặc định, `line`, `block`).
- `--dpi`: Độ phân giải ảnh đầu ra khi render PDF (mặc định: `150`).
- `--normalize`: Chuẩn hóa tọa độ bounding box về dải `[0, 1000]`.
- `--extract-images`: Trích xuất cả các file ảnh/logo bên trong PDF ra thư mục riêng và lưu đường dẫn vào JSON.

**Ví dụ chạy thực tế:**
```bash
# Trích xuất chi tiết cấp từ và xuất cả các ảnh có trong file
python3 extract_pdf_layout.py --pdf pharmarcity.pdf --output output_dataset --extract-images

# Trích xuất cấp độ block văn bản và chuẩn hóa tọa độ bounding box về dạng [0, 1000]
python3 extract_pdf_layout.py --pdf pharmarcity.pdf --output output_dataset_normalized --normalize --granularity block
```

---

### 2. Sinh dữ liệu từ mã nguồn HTML (`html_to_synthetic.py`)

Công cụ này render trực tiếp code HTML để xuất ra ảnh screenshot và nhãn tọa độ DOM.

**Cú pháp cơ bản:**
```bash
python3 html_to_synthetic.py --html <duong_dan_file_html_hoac_url> --output <thu_muc_output> [options]
```

**Các tham số tùy chọn (Options):**
- `--selectors`: Danh sách các tag/class CSS cần trích xuất bounding box (mặc định: `p, h1, h2, h3, h4, h5, h6, img, button, a, span`).
- `--width` / `--height`: Kích thước khung nhìn trình duyệt ban đầu (mặc định: `1280x800`).
- `--normalize`: Chuẩn hóa tọa độ về dải `[0, 1000]`.

**Ví dụ chạy thực tế:**
```bash
python3 html_to_synthetic.py --html index.html --output html_dataset --normalize
```

---

## 📁 Cấu trúc dữ liệu đầu ra (Output Directory Structure)

Sau khi chạy thành công công cụ PDF, thư mục đầu ra sẽ có cấu trúc như sau:

```text
output_dataset/
├── page_000.png                # Ảnh gốc trang 1 dùng làm Input cho VLM
├── layout_000.json             # Bounding box và text tương ứng trang 1
├── viz_page_000.png            # Ảnh xem trước (xanh lá = text, đỏ = image)
├── ...
└── extracted_images/           # Thư mục chứa các ảnh được trích xuất
    ├── page_000_raw_0.png      # Byte ảnh gốc nhúng bên trong PDF
    ├── page_000_crop_0.png     # Ảnh cắt thực tế (visual crop) hiển thị trên trang
    └── ...
```

### Chi tiết định dạng nhãn JSON (`layout_000.json`):
```json
{
  "page_index": 0,
  "page_dimensions": {
    "points": [594.96, 841.92],
    "pixels": [1240, 1754]
  },
  "coordinate_system": "pixel_coordinates",
  "annotations": [
    {
      "type": "text",
      "bbox": [165.62, 76.9, 235.41, 105.4],
      "text": "Chuỗi",
      "metadata": {
        "block_no": 0,
        "line_no": 0,
        "word_no": 0
      }
    },
    {
      "type": "image",
      "bbox": [1067.72, 1447.4, 1157.28, 1536.97],
      "metadata": {
        "block_no": 7,
        "width": 270,
        "height": 258,
        "ext": "jpeg",
        "image_path_raw": "extracted_images/page_000_raw_7.jpeg",
        "image_path_crop": "extracted_images/page_000_crop_7.png"
      }
    }
  ]
}
```