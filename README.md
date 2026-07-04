# OCR & VLM Synthetic Data Extraction Tools

Bộ công cụ hỗ trợ chuẩn bị dữ liệu huấn luyện OCR và Layout Analysis cho các mô hình Vision-Language Models (VLMs) từ định dạng tài liệu PDF và source HTML.

---

## 📂 Danh sách các file trong thư mục dự án (Root Files)

- **[extract_pdf_layout.py](file:///home/namdv/workspace/HTML-Reversed/extract_pdf_layout.py)**: Script Python chính sử dụng thư viện `PyMuPDF` (`fitz`) để phân tích cú pháp file PDF, render ảnh trang giấy, trích xuất tọa độ văn bản (từ, dòng, đoạn) và ảnh kèm theo.
- **[html_to_synthetic.py](file:///home/namdv/workspace/HTML-Reversed/html_to_synthetic.py)**: Script Python mẫu sử dụng `Playwright` để render code HTML, chụp màn hình và trích xuất tọa độ DOM của các phần tử chỉ định.
- **[pharmarcity.pdf](file:///home/namdv/workspace/HTML-Reversed/pharmarcity.pdf)**: File PDF tài liệu mẫu để kiểm thử công cụ trích xuất.
- **[README.md](file:///home/namdv/workspace/HTML-Reversed/README.md)**: File hướng dẫn này.
- **[.gitignore](file:///home/namdv/workspace/HTML-Reversed/.gitignore)**: Cấu hình Git để loại bỏ thư mục kết quả `output_dataset` khỏi commit nhằm tránh làm nặng repository.

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

## 📁 Cấu trúc dữ liệu đầu ra và Giải thích mục đích các file (`output_dataset`)

Thư mục kết quả đầu ra sau khi chạy lệnh trích xuất PDF có cấu trúc như sau:

```text
output_dataset/
├── page_000.png                # Ảnh gốc trang 1
├── layout_000.json             # Bounding box và text tương ứng trang 1
├── viz_page_000.png            # Ảnh xem trước trực quan hóa (khung xanh/đỏ)
├── ...
└── extracted_images/           # Thư mục chứa các ảnh được trích xuất
    ├── page_000_raw_0.png      # Byte ảnh gốc nhúng bên trong PDF
    ├── page_000_crop_0.png     # Ảnh cắt thực tế (visual crop) hiển thị trên trang
    └── ...
```

### Chi tiết mục đích của từng file:

1. **`page_XXX.png` (Ví dụ: `page_000.png`)**:
   - **Mục đích**: Là ảnh chụp nguyên bản của trang PDF thứ `XXX` ở dạng định dạng PNG chất lượng cao.
   - **Ứng dụng**: Làm **dữ liệu hình ảnh đầu vào (Input Image)** trực tiếp cho các mô hình VLM (như Donut, Kosmos, LayoutLMv3, LLaVA, v.v.) trong quá trình training.

2. **`layout_XXX.json` (Ví dụ: `layout_000.json`)**:
   - **Mục đích**: Chứa toàn bộ nhãn văn bản (ground truth text), vị trí ảnh và tọa độ bounding box tương ứng của trang giấy đó.
   - **Ứng dụng**: Cung cấp **nhãn đầu ra (Target labels/Bounding Boxes)** cho mô hình học máy. File này liên kết trực tiếp tọa độ của chữ/ảnh với tọa độ pixel trên file `page_XXX.png` (hoặc hệ tọa độ chuẩn hóa `[0, 1000]`).

3. **`viz_page_XXX.png` (Ví dụ: `viz_page_000.png`)**:
   - **Mục đích**: File ảnh xem trước (Visualization) được sinh ra để hỗ trợ việc kiểm tra thủ công hoặc debug.
   - **Cách đọc**: 
     - Khung chữ nhật **màu xanh lá** biểu thị các vùng chữ (`text`).
     - Khung chữ nhật **màu đỏ** biểu thị các vùng ảnh (`image`).
   - **Ứng dụng**: Giúp các kỹ sư dữ liệu kiểm tra nhanh xem thuật toán có nhận diện sai, lệch hoặc thiếu vùng chữ/ảnh hay không trước khi đưa tập dữ liệu vào huấn luyện.

4. **Thư mục `extracted_images/`**:
   - **`page_XXX_raw_YYY.<ext>`**: File ảnh gốc được trích xuất nguyên bản nhúng trong PDF (giữ nguyên độ phân giải và chất lượng gốc). Mục đích là để thu thập các asset ảnh sạch phục vụ cho việc sinh dữ liệu synthetic nâng cao sau này.
   - **`page_XXX_crop_YYY.png`**: File ảnh được cắt trực tiếp từ trang vẽ `page_XXX.png` dựa trên tọa độ bao. Mục đích là để lấy chính xác hình dạng ảnh hiển thị trên giao diện trang tài liệu (đã bao gồm các góc bo, tỉ lệ co giãn thực tế).

---

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