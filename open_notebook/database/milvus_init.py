from pymilvus import MilvusClient
import os
from dotenv import load_dotenv
load_dotenv()

MILVUS_ADDRESS = os.getenv("MILVUS_ADDRESS", "192.168.20.156")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
MILVUS_URL = os.getenv("MILVUS_URI", f"http://{MILVUS_ADDRESS}:{MILVUS_PORT}")

milvus_client: MilvusClient | None = None

def get_milvus_client() -> MilvusClient:
    global milvus_client
    if milvus_client is None:
        milvus_client = MilvusClient(uri=MILVUS_URL,
                                     token="root:Milvus")
    return milvus_client

def close_milvus_client():
    global milvus_client
    if milvus_client:
        milvus_client.close()
        milvus_client = None
