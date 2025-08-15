# SQL Agent

## Lưu ý quan trọng

**Tập dữ liệu ABBREV.xlsx (nutrients) chưa được xử lý:**
- Chưa có file schema tương ứng
- Chưa có script insert dữ liệu
- Cần tạo schema dựa trên mô tả trong file `data/XLSX Dataset.xlsx`
- Cần xem các cột của tập dữ liệu để sinh ra file schema và script insert

## Khởi động nhanh

### 1. Tạo môi trường ảo
```bash
uv venv
```

### 2. Cài đặt các gói phụ thuộc
```bash
uv sync
```

### 3. Thiết lập biến môi trường
Tạo file `.env`:
```env
NEBIUS_API_KEY=your_nebius_api_key_here
```

### 4. Chèn dữ liệu
Chạy các script chuyển đổi dữ liệu:
```bash
python sql/load_and_transform_company_simul.py
python sql/load_and_transform_hr_employee.py
python sql/load_and_transform_laptop_prices.py
python sql/load_and_transform_wc_2022.py
python sql/load_and_transform_youtube_influencers.py
```

### 5. Chạy ứng dụng
```bash
python -m src.main
```

## Cấu trúc thư mục

```
sql-agent/
├── data/                          # File dữ liệu (XLSX/CSV)
│   ├── ABBREV.xlsx               # ⚠️ Chưa có schema và script insert
│   ├── FIFA WC 2022 Players Stats .xlsx
│   ├── Flipkart-Laptops.xlsx
│   ├── HR_Employee_Data.xlsx
│   ├── Purchasing.*.xlsx
│   └── Youtube Influencer Analysis - Updated.csv
├── src/
│   ├── prompt/
│   │   └── schemas/              # Định nghĩa schema cơ sở dữ liệu
│   │       ├── company_schema.py
│   │       ├── fifa_wc_2022_schema.py
│   │       ├── hr_employee_schema.py
│   │       ├── laptop_prices_schema.py
│   │       └── youtube_influencers_schema.py
│   ├── graph/
│   │   └── sql_graph.py          # Triển khai graph chính
│   ├── tool/
│   │   └── query_tool.py         # Công cụ thực thi SQL
│   └── main.py                   # Ứng dụng chính với các câu hỏi
├── sql/                          # Script chuyển đổi dữ liệu
│   ├── load_and_transform_company_simul.py
│   ├── load_and_transform_hr_employee.py
│   ├── load_and_transform_laptop_prices.py
│   ├── load_and_transform_wc_2022.py
│   └── load_and_transform_youtube_influencers.py
├── pyproject.toml               # Cấu hình dự án
└── uv.lock                      # File lock cho các gói phụ thuộc
```

## Vị trí quan trọng

- **Schemas**: `src/prompt/schemas/` - Định nghĩa schema cơ sở dữ liệu
- **Questions**: `data/XLSX Dataset.xlsx` - Câu hỏi định nghĩa sẵn bằng tiếng Việt
- **Datasets**: `data/` - File XLSX và CSV
- **Data Processing**: `sql/` - Script để tải và chuyển đổi dữ liệu

## Cách sử dụng

Chỉnh sửa câu hỏi trong `src/main.py` với các câu hỏi trong `data/XLSX Dataset.xlsx`:
```python
company_questions = [
    "Số lượng đơn hàng nhiều nhất mà một nhà cung cấp từng có là bao nhiêu?",
    "Phương thức vận chuyển nào được sử dụng nhiều nhất?"
]
```

Import schemas:
```python
from src.prompt.schemas import (
    COMPANY_SCHEMA,
    HR_EMPLOYEE_SCHEMA,
    FIFA_WC_2022_SCHEMA,
    LAPTOP_PRICES_SCHEMA,
    YOUTUBE_INFLUENCERS_SCHEMA
)
```
