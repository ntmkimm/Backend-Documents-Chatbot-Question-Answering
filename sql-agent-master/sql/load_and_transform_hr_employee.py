import sqlite3
import pandas as pd
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / 'data' / 'HR_Employee_Data.xlsx'
DB_PATH = Path(__file__).parent.parent / 'data' / 'data.db'

def create_employee_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employee (
            Emp_Id TEXT,
            satisfaction_level REAL,
            last_evaluation REAL,
            number_project INTEGER,
            average_montly_hours INTEGER,
            time_spend_company INTEGER,
            Work_accident INTEGER,
            left INTEGER,
            promotion_last_5years INTEGER,
            Department TEXT,
            salary TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_employee_rows(df):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT OR IGNORE INTO employee (
                Emp_Id, satisfaction_level, last_evaluation, number_project, average_montly_hours, time_spend_company, Work_accident, left, promotion_last_5years, Department, salary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(row['Emp_Id']),
            float(row['satisfaction_level']),
            float(row['last_evaluation']),
            int(row['number_project']),
            int(row['average_montly_hours']),
            int(row['time_spend_company']),
            int(row['Work_accident']),
            int(row['left']),
            int(row['promotion_last_5years']),
            str(row['Department']),
            str(row['salary'])
        ))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    df = pd.read_excel(DATA_PATH)
    create_employee_table()
    insert_employee_rows(df)