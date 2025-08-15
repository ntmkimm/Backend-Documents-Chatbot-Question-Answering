import sqlite3
import pandas as pd
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / 'data' / 'Flipkart-Laptops.xlsx'
DB_PATH = Path(__file__).parent.parent / 'data' / 'data.db'

def create_laptop_prices_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS laptop_prices (
            product_name TEXT,
            product_id TEXT,
            product_image TEXT,
            actual_price REAL,
            discount_price REAL,
            stars REAL,
            rating INTEGER,
            reviews INTEGER,
            description TEXT,
            link TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_laptop_prices_rows(df):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    import re

    # Hàm trích số từ chuỗi dạng "1,234 Ratings" hoặc "NIL"
    def extract_number(text):
        if pd.isna(text) or str(text).strip().upper() == "NIL":
            return 0
        match = re.search(r'[\d,]+', str(text))
        if match:
            return int(match.group(0).replace(',', ''))
        return 0

    # Hàm xử lý toàn bộ DataFrame
    def preprocess_laptop_prices(df):
        # Loại bỏ khoảng trắng dư ở tên cột
        df.columns = df.columns.str.strip()

        # Chuyển các cột giá thành float (giả định đã sạch)
        df['Actual price'] = pd.to_numeric(df['Actual price'], errors='coerce').fillna(0)
        df['Discount price'] = pd.to_numeric(df['Discount price'], errors='coerce').fillna(0)

        # Chuyển đánh giá và review từ chuỗi về số
        df['Rating'] = df['Rating'].apply(extract_number)
        df['Reviews'] = df['Reviews'].apply(extract_number)

        # Chuyển đổi Stars (có thể bị "NIL" → 0)
        df['Stars'] = pd.to_numeric(df['Stars'], errors='coerce')

        # Chuẩn hóa Product image nếu đang ở float64
        if df['Product image'].dtype != 'object':
            df['Product image'] = df['Product image'].astype(str)

        return df

    # Gọi hàm xử lý
    df = preprocess_laptop_prices(df)
    
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT INTO laptop_prices (
                product_name, product_id, product_image, actual_price,
                discount_price, stars, rating, reviews, description, link
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(row['Product Name']) if pd.notna(row['Product Name']) else None,
            str(row['ProductID']) if pd.notna(row['ProductID']) else None,
            str(row['Product image']) if pd.notna(row['Product image']) else None,
            float(row['Actual price']) if pd.notna(row['Actual price']) else None,
            float(row['Discount price']) if pd.notna(row['Discount price']) else None,
            float(row['Stars']) if pd.notna(row['Stars']) else None,
            int(row['Rating']) if pd.notna(row['Rating']) else None,
            int(row['Reviews']) if pd.notna(row['Reviews']) else None,
            str(row['Description']) if pd.notna(row['Description']) else None,
            str(row['Link']) if pd.notna(row['Link']) else None
        ))
    conn.commit()
    conn.close()

def main():
    try:
        # Read the Excel file
        print("Reading laptop prices data...")
        df = pd.read_excel(DATA_PATH)
        print(f"Loaded {len(df)} rows of data")
        
        # Display column info for debugging
        print("Column names and types:")
        print(df.dtypes)
        
        # Create the table
        print("Creating laptop prices table...")
        create_laptop_prices_table()
        
        # Insert the data
        print("Inserting data into database...")
        insert_laptop_prices_rows(df)
        
        print("Successfully loaded laptop prices data into database!")
        
    except Exception as e:
        print(f"Error loading laptop prices data: {e}")

if __name__ == "__main__":
    main() 