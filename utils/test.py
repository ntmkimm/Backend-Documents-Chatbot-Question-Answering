# import requests
# from dotenv import load_dotenv
# load_dotenv()
# import os

# API_KEY = os.getenv("OPENAI_API_KEY")
# BASE_URL = "https://api.openai.com/tokenize"
# # BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1") + "/chat/completions"

# text = "Artificial intelligence is transforming healthcare by improving diagnostics and patient care."

# payload = {
#     "model": "gpt-4o",  
#     "messages": [
#         {"role": "user", "content": text}
#     ],
#     # "max_tokens": 1
# }

# headers = {
#     "Authorization": f"Bearer {API_KEY}",
#     "Content-Type": "application/json"
# }

# resp = requests.post(BASE_URL, headers=headers, json=payload)
# print(resp)
# print(resp.json())
# print("number of tokens: ", resp.json()["usage"].get("total_tokens"))


# # import os
# # import requests
# # from dotenv import load_dotenv

# # load_dotenv()

# # API_KEY = os.getenv("OPENROUTER_API_KEY")  # or your Nebius key
# # BASE_URL = os.getenv("API_BASE_URL", "https://api.studio.nebius.ai")  # provider base URL

# # text = "Artificial intelligence is transforming healthcare by improving diagnostics and patient care."

# # payload = {
# #     "model": "Qwen/Qwen3-30B-A3B-Instruct-2507",  # pick any supported model
# #     "input": text
# # }

# # headers = {
# #     "Authorization": f"Bearer {API_KEY}",
# #     "Content-Type": "application/json"
# # }
# # BASE_URL = "https://api.studio.nebius.ai"
# # resp = requests.post(f"{BASE_URL}/tokenize", headers=headers, json=payload)
# # print(resp)
# # resp.raise_for_status()
# # data = resp.json()

# # print("Token IDs:", data.get("tokens"))
# # print("Number of tokens:", len(data.get("tokens", [])))

from pymilvus import connections, utility

# Kết nối tới Milvus server
connections.connect("default", host="192.168.20.156", port="19530")

# Tên collection muốn drop
collection_name = "agent_memory1"

# Kiểm tra tồn tại
if utility.has_collection(collection_name):
    utility.drop_collection(collection_name)
    print(f"Collection {collection_name} dropped successfully")
else:
    print(f"Collection {collection_name} not found")
