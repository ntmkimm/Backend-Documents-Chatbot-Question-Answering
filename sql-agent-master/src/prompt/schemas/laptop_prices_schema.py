LAPTOP_PRICES_SCHEMA = """
### Bảng: laptop_prices

**Mô tả**: Bảng chứa thông tin về giá cả và đánh giá của các sản phẩm laptop trên Flipkart, dùng để phân tích thị trường và so sánh giá cả.

(Tên cột (Kiểu dữ liệu): Mô tả)

- **product_name**: *string* — Tên sản phẩm
- **product_id**: *string* — ID của sản phẩm
- **product_image**: *string* — Ảnh của sản phẩm
- **actual_price**: *float* — Giá thành của sản phẩm
- **discount_price**: *float* — Giá thành của sản phẩm sau khi giảm giá
- **stars**: *float* — Số sao đánh giá sản phẩm
- **rating**: *integer* — Số lượt đánh giá
- **reviews**: *integer* — Số lượt review
- **description**: *string* — Mô tả sản phẩm
- **link**: *string* — Link sản phẩm
""" 