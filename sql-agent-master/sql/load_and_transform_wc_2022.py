import sqlite3
import pandas as pd
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / 'data' / 'FIFA WC 2022 Players Stats .xlsx'
DB_PATH = Path(__file__).parent.parent / 'data' / 'data.db'

def create_fifa_wc_2022_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fifa_wc_2022_players (
            player_name TEXT,
            nationality TEXT,
            fifa_ranking INTEGER,
            national_team_kit_sponsor TEXT,
            position TEXT,
            national_team_jersey_number REAL,
            player_dob DATE,
            club TEXT,
            appearances REAL,
            goals_scored REAL,
            assists_provided REAL,
            dribbles_per_90 REAL,
            interceptions_per_90 REAL,
            tackles_per_90 REAL,
            total_duels_won_per_90 REAL,
            save_percentage REAL,
            clean_sheets REAL,
            brand_sponsor_brand_used TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_fifa_wc_2022_rows(df):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Các cột cần chuyển về kiểu float hoặc int
    numeric_cols = [
        ' Appearances', 'Goals Scored ', 'Assists Provided ', 'Dribbles per 90',
        'Interceptions per 90', 'Tackles per 90', 'Total Duels Won per 90',
        'Save Percentage', 'Clean Sheets', 'National Team Jersey Number'
    ]

    # Convert string to numeric (ignore errors)
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Convert ngày sinh
    df['Player DOB'] = pd.to_datetime(df['Player DOB'], errors='coerce')
    
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT INTO fifa_wc_2022_players (
                player_name, nationality, fifa_ranking, national_team_kit_sponsor,
                position, national_team_jersey_number, player_dob, club,
                appearances, goals_scored, assists_provided, dribbles_per_90,
                interceptions_per_90, tackles_per_90, total_duels_won_per_90,
                save_percentage, clean_sheets, brand_sponsor_brand_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(row['Player Name ']) if pd.notna(row['Player Name ']) else None,
            str(row['Nationality ']) if pd.notna(row['Nationality ']) else None,
            int(row['FIFA Ranking ']) if pd.notna(row['FIFA Ranking ']) else None,
            str(row['National Team Kit Sponsor']) if pd.notna(row['National Team Kit Sponsor']) else None,
            str(row['Position']) if pd.notna(row['Position']) else None,
            float(row['National Team Jersey Number']) if pd.notna(row['National Team Jersey Number']) else None,
            str(row['Player DOB']) if pd.notna(row['Player DOB']) else None,
            str(row['Club ']) if pd.notna(row['Club ']) else None,
            float(row[' Appearances']) if pd.notna(row[' Appearances']) else None,
            float(row['Goals Scored ']) if pd.notna(row['Goals Scored ']) else None,
            float(row['Assists Provided ']) if pd.notna(row['Assists Provided ']) else None,
            float(row['Dribbles per 90']) if pd.notna(row['Dribbles per 90']) else None,
            float(row['Interceptions per 90']) if pd.notna(row['Interceptions per 90']) else None,
            float(row['Tackles per 90']) if pd.notna(row['Tackles per 90']) else None,
            float(row['Total Duels Won per 90']) if pd.notna(row['Total Duels Won per 90']) else None,
            float(row['Save Percentage']) if pd.notna(row['Save Percentage']) else None,
            float(row['Clean Sheets']) if pd.notna(row['Clean Sheets']) else None,
            str(row['Brand Sponsor/Brand Used']) if pd.notna(row['Brand Sponsor/Brand Used']) else None
        ))
    conn.commit()
    conn.close()

def main():
    try:
        # Read the Excel file
        print("Reading FIFA WC 2022 data...")
        df = pd.read_excel(DATA_PATH)
        print(f"Loaded {len(df)} rows of data")
        
        # Create the table
        print("Creating FIFA WC 2022 players table...")
        create_fifa_wc_2022_table()
        
        # Insert the data
        print("Inserting data into database...")
        insert_fifa_wc_2022_rows(df)
        
        print("Successfully loaded FIFA WC 2022 data into database!")
        
    except Exception as e:
        print(f"Error loading FIFA WC 2022 data: {e}")

if __name__ == "__main__":
    main()
