import asyncio
from surrealdb import Surreal

async def clear_surrealdb():
    """
    Xóa hết dữ liệu trong SurrealDB namespace và database
    """
    # Thông tin kết nối
    SURREAL_ADDRESS = "127.0.0.1"
    SURREAL_PORT = 8000
    SURREAL_USER = "root"
    SURREAL_PASS = "root"
    SURREAL_NAMESPACE = "testnd"
    SURREAL_DATABASE = "testdb"
    
    # Tạo kết nối
    db = Surreal()
    
    try:
        # Kết nối tới SurrealDB
        await db.connect(f"ws://{SURREAL_ADDRESS}:{SURREAL_PORT}/rpc")
        print(f"✅ Đã kết nối tới SurrealDB tại {SURREAL_ADDRESS}:{SURREAL_PORT}")
        
        # Đăng nhập
        await db.signin({"user": SURREAL_USER, "pass": SURREAL_PASS})
        print("✅ Đăng nhập thành công")
        
        # Chọn namespace và database
        await db.use(SURREAL_NAMESPACE, SURREAL_DATABASE)
        print(f"✅ Đã chọn namespace: {SURREAL_NAMESPACE}, database: {SURREAL_DATABASE}")
        
        # Lấy danh sách tất cả các table
        result = await db.query("INFO FOR DB;")
        print("📋 Thông tin database:")
        print(result)
        
        # Xác nhận trước khi xóa
        confirm = input(f"\n⚠️  BẠN CÓ CHẮC CHẮN MUỐN XÓA HẾT DỮ LIỆU TRONG DATABASE '{SURREAL_DATABASE}' KHÔNG? (yes/no): ")
        
        if confirm.lower() != 'yes':
            print("❌ Đã hủy thao tác xóa dữ liệu")
            return
        
        # Phương pháp 1: Xóa từng table (an toàn hơn)
        print("\n🗑️  Bắt đầu xóa dữ liệu...")
        
        # Lấy danh sách các table
        tables_result = await db.query("SELECT VALUE name FROM array::distinct((SELECT VALUE meta::tb(id) FROM type::table($tb)) FOR $tb IN ['users', 'posts', 'comments', 'products', 'orders']) WHERE name != NONE;")
        
        if tables_result and len(tables_result) > 0 and tables_result[0]['result']:
            tables = tables_result[0]['result']
            print(f"📊 Tìm thấy {len(tables)} table(s): {tables}")
            
            for table in tables:
                try:
                    delete_result = await db.query(f"DELETE {table};")
                    print(f"✅ Đã xóa dữ liệu trong table: {table}")
                except Exception as e:
                    print(f"❌ Lỗi khi xóa table {table}: {e}")
        
        # Phương pháp 2: Xóa tất cả bằng cách remove database (cực kỳ nguy hiểm)
        # Uncomment dòng dưới nếu muốn xóa hoàn toàn database
        # await db.query(f"REMOVE DATABASE {SURREAL_DATABASE};")
        # print(f"💥 Đã xóa hoàn toàn database: {SURREAL_DATABASE}")
        
        # Phương pháp 3: Xóa tất cả record trong mọi table
        print("\n🧹 Thực hiện xóa toàn bộ dữ liệu...")
        await db.query("DELETE users; DELETE posts; DELETE comments; DELETE products; DELETE orders; DELETE sessions; DELETE logs;")
        
        # Kiểm tra kết quả
        check_result = await db.query("INFO FOR DB;")
        print("\n📋 Thông tin database sau khi xóa:")
        print(check_result)
        
        print("\n✅ Đã xóa hết dữ liệu thành công!")
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
    
    finally:
        # Đóng kết nối
        await db.close()
        print("🔌 Đã đóng kết nối database")

# Phiên bản đồng bộ sử dụng requests (nếu không có surrealdb async client)
def clear_surrealdb_sync():
    """
    Phiên bản đồng bộ sử dụng HTTP requests
    """
    import requests
    import json
    
    # Thông tin kết nối
    SURREAL_ADDRESS = "127.0.0.1"
    SURREAL_PORT = 8000
    SURREAL_USER = "root"
    SURREAL_PASS = "root"
    SURREAL_NAMESPACE = "testnd"
    SURREAL_DATABASE = "testdb"
    
    base_url = f"http://{SURREAL_ADDRESS}:{SURREAL_PORT}/rpc"
    
    # Headers
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        # Đăng nhập và lấy token
        signin_data = {
            "id": 1,
            "method": "signin",
            "params": [{"user": SURREAL_USER, "pass": SURREAL_PASS}]
        }
        
        response = requests.post(base_url, headers=headers, data=json.dumps(signin_data))
        print(f"✅ Kết nối thành công: {response.status_code}")
        
        # Sử dụng namespace và database
        use_data = {
            "id": 2,
            "method": "use",
            "params": [SURREAL_NAMESPACE, SURREAL_DATABASE]
        }
        
        response = requests.post(base_url, headers=headers, data=json.dumps(use_data))
        print(f"✅ Đã chọn namespace và database")
        
        # Xác nhận
        confirm = input(f"\n⚠️  BẠN CÓ CHẮC CHẮN MUỐN XÓA HẾT DỮ LIỆU KHÔNG? (yes/no): ")
        if confirm.lower() != 'yes':
            print("❌ Đã hủy thao tác")
            return
        
        # Xóa dữ liệu
        delete_queries = [
            "DELETE users;",
            "DELETE posts;", 
            "DELETE comments;",
            "DELETE products;",
            "DELETE orders;",
            "DELETE sessions;",
            "DELETE logs;"
        ]
        
        for i, query in enumerate(delete_queries):
            query_data = {
                "id": i + 3,
                "method": "query",
                "params": [query]
            }
            
            response = requests.post(base_url, headers=headers, data=json.dumps(query_data))
            print(f"✅ Đã thực hiện: {query}")
        
        print("\n✅ Đã xóa hết dữ liệu thành công!")
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")

if __name__ == "__main__":
    print("🚀 Chọn phương pháp:")
    print("1. Async (cần cài surrealdb package)")
    print("2. Sync với HTTP requests")
    
    choice = input("Nhập lựa chọn (1 hoặc 2): ")
    
    if choice == "1":
        # Chạy phiên bản async
        asyncio.run(clear_surrealdb())
    else:
        # Chạy phiên bản sync
        clear_surrealdb_sync()