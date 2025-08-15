# from sqlalchemy import create_engine
# import pandas as pd
# import os
# from dotenv import load_dotenv
# load_dotenv()

# csv_path = '/mlcv2/WorkingSpace/Personal/quannh/Project/Project/TRNS-AI/ntmkim/Work/docsqa-dev_local/sql-agent-master/data/Youtube Influencer Analysis - Updated.csv'

# df = pd.read_csv(csv_path, encoding="cp1252")
# POSTGRES_URI = 'postgresql://postgres:' + os.getenv('POSTGRES_PASSWORD') + '@' + os.getenv('POSTGRES_ADDRESS') + ':' + os.getenv('POSTGRES_PORT') + '/postgres'
# engine = create_engine(POSTGRES_URI)

# # This auto-creates the table if not exists
# df.to_sql("youtube", engine, if_exists="append", index=False, method="multi", chunksize=1000)

import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()

# Get your connection string from .env
POSTGRES_URI = 'postgresql://postgres:' + os.getenv('POSTGRES_PASSWORD') + '@' + os.getenv('POSTGRES_ADDRESS') + ':' + os.getenv('POSTGRES_PORT') + '/postgres'
engine = create_engine(POSTGRES_URI)

# Table name you want to read
table_name = "youtube"

# Read the entire table into a DataFrame
df = pd.read_sql(f"SELECT * FROM {table_name}", con=engine)

print(df.head())