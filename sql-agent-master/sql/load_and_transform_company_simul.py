import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'data' / 'data.db'
DATA_DIR = Path(__file__).parent.parent / 'data'

def create_product_vendor_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_vendor (
            ProductID INTEGER,
            BusinessEntityID INTEGER,
            AverageLeadTime INTEGER,
            StandardPrice REAL, 
            LastReceiptCost REAL,
            LastReceiptDate TEXT,
            MinOrderQty INTEGER,
            MaxOrderQty INTEGER,
            OnOrderQty REAL,
            UnitMeasureCode TEXT,
            ModifiedDate TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_product_vendor_rows(df):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT OR IGNORE INTO product_vendor (
                ProductID, BusinessEntityID, AverageLeadTime, StandardPrice, LastReceiptCost, LastReceiptDate, MinOrderQty, MaxOrderQty, OnOrderQty, UnitMeasureCode, ModifiedDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            int(row['ProductID']),
            int(row['BusinessEntityID']),
            int(row['AverageLeadTime']),
            float(row['StandardPrice']),
            float(row['LastReceiptCost']),
            str(row['LastReceiptDate']),
            int(row['MinOrderQty']),
            int(row['MaxOrderQty']),
            float(row['OnOrderQty']) if not pd.isna(row['OnOrderQty']) else None,
            str(row['UnitMeasureCode']),
            str(row['ModifiedDate'])
        ))
    conn.commit()
    conn.close()

def create_purchase_order_detail_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_order_detail (
            PurchaseOrderID INTEGER,
            PurchaseOrderDetailID INTEGER,
            DueDate TEXT,
            OrderQty INTEGER,
            ProductID INTEGER,
            UnitPrice REAL,
            LineTotal REAL,
            ReceivedQty INTEGER,
            RejectedQty INTEGER,
            StockedQty INTEGER,
            ModifiedDate TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_purchase_order_detail_rows(df):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT OR IGNORE INTO purchase_order_detail (
                PurchaseOrderID, PurchaseOrderDetailID, DueDate, OrderQty, ProductID, UnitPrice, LineTotal, ReceivedQty, RejectedQty, StockedQty, ModifiedDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            int(row['PurchaseOrderID']),
            int(row['PurchaseOrderDetailID']),
            str(row['DueDate']),
            int(row['OrderQty']),
            int(row['ProductID']),
            float(row['UnitPrice']),
            float(row['LineTotal']),
            int(row['ReceivedQty']),
            int(row['RejectedQty']),
            int(row['StockedQty']),
            str(row['ModifiedDate'])
        ))
    conn.commit()
    conn.close()

def create_purchase_order_header_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_order_header (
            PurchaseOrderID INTEGER,
            RevisionNumber INTEGER,
            Status INTEGER,
            EmployeeID INTEGER,
            VendorID INTEGER,
            ShipMethodID INTEGER,
            OrderDate TEXT,
            ShipDate TEXT,
            SubTotal REAL,
            TaxAmt REAL,
            Freight REAL,
            TotalDue REAL,
            ModifiedDate TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_purchase_order_header_rows(df):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT OR IGNORE INTO purchase_order_header (
                PurchaseOrderID, RevisionNumber, Status, EmployeeID, VendorID, ShipMethodID, OrderDate, ShipDate, SubTotal, TaxAmt, Freight, TotalDue, ModifiedDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            int(row['PurchaseOrderID']),
            int(row['RevisionNumber']),
            int(row['Status']),
            int(row['EmployeeID']),
            int(row['VendorID']),
            int(row['ShipMethodID']),
            str(row['OrderDate']),
            str(row['ShipDate']),
            float(row['SubTotal']),
            float(row['TaxAmt']),
            float(row['Freight']),
            float(row['TotalDue']),
            str(row['ModifiedDate'])
        ))
    conn.commit()
    conn.close()

def create_ship_method_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ship_method (
            ShipMethodID INTEGER,
            Name TEXT,
            ShipBase REAL,
            ShipRate REAL,
            rowguid TEXT,
            ModifiedDate TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_ship_method_rows(df):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT OR IGNORE INTO ship_method (
                ShipMethodID, Name, ShipBase, ShipRate, rowguid, ModifiedDate
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            int(row['ShipMethodID']),
            str(row['Name']),
            float(row['ShipBase']),
            float(row['ShipRate']),
            str(row['rowguid']),
            str(row['ModifiedDate'])
        ))
    conn.commit()
    conn.close()

def create_vendor_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendor (
            BusinessEntityID INTEGER,
            AccountNumber TEXT,
            Name TEXT,
            CreditRating INTEGER,
            PreferredVendorStatus INTEGER,
            ActiveFlag INTEGER,
            PurchasingWebServiceURL TEXT,
            ModifiedDate TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_vendor_rows(df):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT OR IGNORE INTO vendor (
                BusinessEntityID, AccountNumber, Name, CreditRating, PreferredVendorStatus, ActiveFlag, PurchasingWebServiceURL, ModifiedDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            int(row['BusinessEntityID']),
            str(row['AccountNumber']),
            str(row['Name']),
            int(row['CreditRating']),
            int(row['PreferredVendorStatus']),
            int(row['ActiveFlag']),
            str(row['PurchasingWebServiceURL']),
            str(row['ModifiedDate'])
        ))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    # ProductVendor
    df_product_vendor = pd.read_excel(DATA_DIR / 'Purchasing.ProductVendor.xlsx')
    create_product_vendor_table()
    insert_product_vendor_rows(df_product_vendor)

    # PurchaseOrderDetail
    df_purchase_order_detail = pd.read_excel(DATA_DIR / 'Purchasing.PurchaseOrderDetail.xlsx')
    create_purchase_order_detail_table()
    insert_purchase_order_detail_rows(df_purchase_order_detail)

    # PurchaseOrderHeader
    df_purchase_order_header = pd.read_excel(DATA_DIR / 'Purchasing.PurchaseOrderHeader.xlsx')
    create_purchase_order_header_table()
    insert_purchase_order_header_rows(df_purchase_order_header)

    # ShipMethod
    df_ship_method = pd.read_excel(DATA_DIR / 'Purchasing.ShipMethod.xlsx')
    create_ship_method_table()
    insert_ship_method_rows(df_ship_method)

    # Vendor
    df_vendor = pd.read_excel(DATA_DIR / 'Purchasing.Vendor.xlsx')
    create_vendor_table()
    insert_vendor_rows(df_vendor)
