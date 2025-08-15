FIFA_WC_2022_SCHEMA = """
### Bảng: fifa_wc_2022_players

**Mô tả**: Bảng chứa thông tin cầu thủ FIFA World Cup 2022, dùng để phân tích hiệu suất và so sánh giữa các quốc gia.

(Tên cột (Kiểu dữ liệu): Mô tả)

- **player_name**: *string* — Tên cầu thủ
- **nationality**: *string* — Quốc tịch của cầu thủ
- **fifa_ranking**: *integer* — Hạng của đội tuyển quốc gia trên bảng xếp hạng FIFA
- **national_team_kit_sponsor**: *string* — Nhà tài trợ áo đấu
- **position**: *string* — Vị trí của cầu thủ trên sân (GK, DF, MF, FW)
- **national_team_jersey_number**: *float* — Số áo của cầu thủ
- **player_dob**: *string* — Ngày sinh của cầu thủ
- **club**: *string* — Câu lạc bộ mà cầu thủ đang thi đấu
- **appearances**: *float* — Số lần ra sân
- **goals_scored**: *float* — Số bàn thắng
- **assists_provided**: *float* — Số kiến tạo
- **dribbles_per_90**: *float* — Số lần rê bóng trung bình mỗi 90 phút
- **interceptions_per_90**: *float* — Số lần cắt bóng trung bình mỗi 90 phút
- **tackles_per_90**: *float* — Số lần tắc bóng mỗi 90 phút
- **total_duels_won_per_90**: *float* — Số pha tranh chấp tay đôi thắng mỗi 90 phút
- **save_percentage**: *float* — Tỷ lệ cản phá thành công (chỉ áp dụng cho thủ môn)
- **clean_sheets**: *float* — Tỷ lệ giữ sạch lưới (chỉ áp dụng cho thủ môn)
- **brand_sponsor_brand_used**: *string* — Hãng quần áo tài trợ (sử dụng)
""" 