HR_EMPLOYEE_SCHEMA = """
### Bảng: employee

**Mô tả**: Bảng chứa thông tin nhân viên và hiệu suất làm việc, dùng để phân tích xu hướng nghỉ việc và mức độ hài lòng.

(Tên cột (Kiểu dữ liệu): Mô tả)

- **Emp_Id**: *string* — Mã định danh duy nhất của nhân viên  
- **satisfaction_level**: *float* — Mức độ hài lòng trong công việc (từ 0 đến 1)  
- **last_evaluation**: *float* — Điểm đánh giá hiệu suất gần nhất (từ 0 đến 1)  
- **number_project**: *integer* — Số lượng dự án nhân viên đã tham gia  
- **average_montly_hours**: *integer* — Số giờ làm việc trung bình mỗi tháng  
- **time_spend_company**: *integer* — Số năm nhân viên đã làm việc tại công ty  
- **Work_accident**: *boolean* — Nhân viên có gặp tai nạn lao động không (1 là Có, 0 là Không)  
- **left**: *boolean* — Nhân viên đã nghỉ việc chưa (1 là Đã nghỉ, 0 là Chưa nghỉ)  
- **promotion_last_5years**: *boolean* — Nhân viên có được thăng chức trong 5 năm qua không (1 là Có, 0 là Không)  
- **Department**: *string* — Phòng ban nơi nhân viên làm việc  
- **salary**: *string* — Mức lương của nhân viên (thấp, trung bình, cao)  
""" 