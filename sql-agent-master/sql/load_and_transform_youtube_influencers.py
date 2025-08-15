import sqlite3
import pandas as pd
from pathlib import Path
import re

DATA_PATH = Path(__file__).parent.parent / 'data' / 'Youtube Influencer Analysis - Updated.csv'
DB_PATH = Path(__file__).parent.parent / 'data' / 'data.db'

def create_youtube_influencers_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS youtube_influencers (
            video_link TEXT,
            video_views INTEGER,
            video_title TEXT,
            channel_url TEXT,
            creator_name TEXT,
            creator_gender TEXT,
            total_channel_subscribers INTEGER,
            total_channel_views INTEGER,
            duration_of_video TEXT,
            duration_in_seconds REAL,
            date_of_video_upload TEXT,
            no_of_likes INTEGER,
            language_of_video TEXT,
            subtitle TEXT,
            video_description TEXT,
            hashtags INTEGER,
            no_of_comments INTEGER,
            date_of_last_comment TEXT,
            maximum_quality_of_video INTEGER,
            no_of_videos_channel INTEGER,
            no_of_playlist INTEGER,
            premiered_or_not TEXT,
            community_engagement_posts_per_week INTEGER,
            intern_who_collected_data TEXT
        )
    ''')
    conn.commit()
    conn.close()

def clean_number(x):
    """Hàm loại dấu phẩy và chuyển thành số"""
    if pd.isna(x):
        return pd.NA
    return pd.to_numeric(str(x).replace(',', '').strip(), errors='coerce')

def preprocess_youtube_influencers(df):
    """Preprocess the YouTube influencers DataFrame"""
    # Áp dụng cho DataFrame mẫu
    df['Video Views'] = df['Video Views'].apply(clean_number).astype('Int64')
    df['Total Channel Subcribers'] = df['Total Channel Subcribers'].apply(clean_number).astype('Int64')
    df['Total Chanel Views'] = df['Total Chanel Views'].apply(clean_number).astype('Int64')
    df['No of Comments'] = df['No of Comments'].apply(clean_number).astype('Int64')
    df['Duration in Seconds'] = df['Duration in Seconds'].apply(clean_number).astype('Float64')

    # Chuyển ngày
    df['Date of Video Upload'] = pd.to_datetime(df['Date of Video Upload'], errors='coerce')
    df['Date of the Last Comment'] = pd.to_datetime(df['Date of the Last Comment'], errors='coerce')
    
    return df

def insert_youtube_influencers_rows(df):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Preprocess the data
    df = preprocess_youtube_influencers(df)
    
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT INTO youtube_influencers (
                video_link, video_views, video_title, channel_url, creator_name,
                creator_gender, total_channel_subscribers, total_channel_views,
                duration_of_video, duration_in_seconds, date_of_video_upload,
                no_of_likes, language_of_video, subtitle, video_description,
                hashtags, no_of_comments, date_of_last_comment, maximum_quality_of_video,
                no_of_videos_channel, no_of_playlist, premiered_or_not,
                community_engagement_posts_per_week, intern_who_collected_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(row['Video Link']) if pd.notna(row['Video Link']) else None,
            int(row['Video Views']) if pd.notna(row['Video Views']) else 0,
            str(row['Video Title']) if pd.notna(row['Video Title']) else None,
            str(row['Channel URL']) if pd.notna(row['Channel URL']) else None,
            str(row['Creator Name']) if pd.notna(row['Creator Name']) else None,
            str(row['Creator Gender']) if pd.notna(row['Creator Gender']) else None,
            int(row['Total Channel Subcribers']) if pd.notna(row['Total Channel Subcribers']) else 0,
            int(row['Total Chanel Views']) if pd.notna(row['Total Chanel Views']) else 0,
            str(row['Duration of Video']) if pd.notna(row['Duration of Video']) else None,
            float(row['Duration in Seconds']) if pd.notna(row['Duration in Seconds']) else 0.0,
            row['Date of Video Upload'].strftime('%Y-%m-%d') if pd.notna(row['Date of Video Upload']) else None,
            int(row['No of Likes']) if pd.notna(row['No of Likes']) else 0,
            str(row['Language of the Video']) if pd.notna(row['Language of the Video']) else None,
            str(row['Subtitle']) if pd.notna(row['Subtitle']) else None,
            str(row['Video Description']) if pd.notna(row['Video Description']) else None,
            int(row['Hashtags']) if pd.notna(row['Hashtags']) else 0,
            int(row['No of Comments']) if pd.notna(row['No of Comments']) else 0,
            row['Date of the Last Comment'].strftime('%Y-%m-%d') if pd.notna(row['Date of the Last Comment']) else None,
            int(row['Maximum Quality of the Video']) if pd.notna(row['Maximum Quality of the Video']) else 0,
            int(row['No of Videos the Channel']) if pd.notna(row['No of Videos the Channel']) else 0,
            int(row['No of Playlist']) if pd.notna(row['No of Playlist']) else 0,
            str(row['Premiered or Not']) if pd.notna(row['Premiered or Not']) else None,
            int(row['Community Engagement (Posts per week)']) if pd.notna(row['Community Engagement (Posts per week)']) else 0,
            str(row['Intern Who Collected the Data']) if pd.notna(row['Intern Who Collected the Data']) else None
        ))
    
    conn.commit()
    conn.close()

def main():
    try:
        # Read the CSV file
        print("Reading YouTube influencers data...")
        df = pd.read_csv(DATA_PATH, encoding='latin')
        print(f"Loaded {len(df)} rows of data")
        
        # Display column info for debugging
        print("Column names and types:")
        print(df.dtypes)
        
        # Create the table
        print("Creating YouTube influencers table...")
        create_youtube_influencers_table()
        
        # Insert the data
        print("Inserting data into database...")
        insert_youtube_influencers_rows(df)
        
        print("Successfully loaded YouTube influencers data into database!")
        
    except Exception as e:
        print(f"Error loading YouTube influencers data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 