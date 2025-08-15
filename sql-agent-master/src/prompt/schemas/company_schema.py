COMPANY_SCHEMA = """
### Bảng: product_vendor

**Mô tả**: Bảng chứa thông tin về sản phẩm và nhà cung cấp, bao gồm giá cả và thời gian giao hàng.

(Tên cột (Kiểu dữ liệu): Mô tả)
- **ProductID**: *integer* — ID của sản phẩm
- **BusinessEntityID**: *integer* — ID của nhà cung cấp
- **AverageLeadTime**: *integer* — Thời gian trung bình từ khi đặt đến khi giao
- **StandardPrice**: *float* — Giá tiêu chuẩn
- **LastReceiptCost**: *float* — Giá của đơn hàng gần nhất
- **LastReceiptDate**: *datetime* — Ngày của đơn hàng gần nhất
- **MinOrderQty**: *integer* — Số lượng hàng đặt thấp nhất
- **MaxOrderQty**: *integer* — Số lượng hàng đặt nhiều nhất
- **OnOrderQty**: *float* — Số lượng hàng đang được đặt
- **UnitMeasureCode**: *string* — Đơn vị
- **ModifiedDate**: *datetime* — Ngày cập nhật thông tin

### Bảng: purchase_order_detail

**Mô tả**: Bảng chứa chi tiết từng sản phẩm trong đơn hàng, bao gồm số lượng và giá trị.

(Tên cột (Kiểu dữ liệu): Mô tả)
- **PurchaseOrderID**: *integer* — ID của đơn hàng
- **PurchaseOrderDetailID**: *integer* — ID của thông tin đơn hàng
- **DueDate**: *datetime* — Ngày phải giao
- **OrderQty**: *integer* — Số lượng hàng được đặt
- **ProductID**: *integer* — ID của sản phẩm
- **UnitPrice**: *float* — Giá thành của một sản phẩm
- **LineTotal**: *float* — Tổng giá trị
- **ReceivedQty**: *integer* — Số lượng hàng đã nhận
- **RejectedQty**: *integer* — Số lượng hàng từ chối
- **StockedQty**: *integer* — Số lượng hàng tồn kho
- **ModifiedDate**: *datetime* — Ngày cập nhật thông tin

### Bảng: purchase_order_header

**Mô tả**: Bảng chứa thông tin tổng quan về đơn hàng, bao gồm ngày đặt, giao và chi phí.

(Tên cột (Kiểu dữ liệu): Mô tả)
- **PurchaseOrderID**: *integer* — ID của đơn hàng
- **RevisionNumber**: *integer* — Số lần chỉnh sửa
- **Status**: *integer* — Tình trạng
- **EmployeeID**: *integer* — ID của nhân viên
- **VendorID**: *integer* — ID của nhà cung cấp
- **ShipMethodID**: *integer* — ID của phương thức vận chuyển
- **OrderDate**: *datetime* — Ngày đặt hàng
- **ShipDate**: *datetime* — Ngày giao hàng
- **SubTotal**: *float* — Tổng tiền hàng
- **TaxAmt**: *float* — Tiền thuế
- **Freight**: *float* — Tiền vận chuyển
- **TotalDue**: *float* — Tổng thanh toán
- **ModifiedDate**: *datetime* — Ngày cập nhật thông tin

### Bảng: ship_method

**Mô tả**: Bảng chứa thông tin về các phương thức vận chuyển và chi phí liên quan.

(Tên cột (Kiểu dữ liệu): Mô tả)
- **ShipMethodID**: *integer* — ID của phương thức vận chuyển
- **Name**: *string* — Tên phương thức vận chuyển
- **ShipBase**: *float* — Phí vận chuyển cơ bản
- **ShipRate**: *float* — Tỷ lệ phí vận chuyển theo khối lượng
- **rowguid**: *string* — Mã định danh toàn cục
- **ModifiedDate**: *datetime* — Ngày cập nhật thông tin

### Bảng: vendor

**Mô tả**: Bảng chứa thông tin về các nhà cung cấp và trạng thái hợp tác.

(Tên cột (Kiểu dữ liệu): Mô tả)
- **BusinessEntityID**: *integer* — ID của nhà cung cấp
- **AccountNumber**: *string* — Số tài khoản
- **Name**: *string* — Tên của nhà cung cấp
- **CreditRating**: *integer* — Xếp hạng tín dụng
- **PreferredVendorStatus**: *integer* — Có phải nhà cung cấp ưu tiên hay không
- **ActiveFlag**: *integer* — Trạng thái hoạt động
- **PurchasingWebServiceURL**: *string* — Trang web bán hàng
- **ModifiedDate**: *datetime* — Ngày cập nhật thông tin

### Mối quan hệ giữa các bảng:

**1. vendor ↔ product_vendor (1:N)**
- `vendor.BusinessEntityID` = `product_vendor.BusinessEntityID`
- Mối quan hệ: Một nhà cung cấp có thể cung cấp nhiều sản phẩm

**2. purchase_order_detail ↔ product_vendor (N:1)**
- `purchase_order_detail.ProductID` = `product_vendor.ProductID`
- Mối quan hệ: Một sản phẩm có thể xuất hiện trong nhiều chi tiết đơn hàng

**3. purchase_order_header ↔ purchase_order_detail (1:N)**
- `purchase_order_header.PurchaseOrderID` = `purchase_order_detail.PurchaseOrderID`
- Mối quan hệ: Một đơn hàng có thể có nhiều chi tiết sản phẩm

**4. purchase_order_header ↔ vendor (N:1)**
- `purchase_order_header.VendorID` = `vendor.BusinessEntityID`
- Mối quan hệ: Một nhà cung cấp có thể có nhiều đơn hàng

**5. purchase_order_header ↔ ship_method (N:1)**
- `purchase_order_header.ShipMethodID` = `ship_method.ShipMethodID`
- Mối quan hệ: Một phương thức vận chuyển có thể được sử dụng cho nhiều đơn hàng

**Mô tả**: Hệ thống quản lý mua hàng bao gồm nhà cung cấp, sản phẩm, đơn hàng và vận chuyển.
""" 