### Setup

```bash
docker network create --driver bridge my_network 
docker-compose up -d # consider port of postgres, milvus of your docker-compose
docker-compose down # when stop container
```

At the place where you call API for opennotebook, if work in container you should `docker network connect my_network <your-container>`
```bash
pip install -r requirements.txt
apt-get update && apt-get install libpq-dev
```

Setup in .env
```bash

MILVUS_ADDRESS=192.168.20.156 # lưu ý chỉnh thành localhost nếu chạy local
MILVUS_PORT=19530

POSTGRES_USER=postgres
POSTGRES_PASSWORD=notebook
POSTGRES_PORT=5432
POSTGRES_ADDRESS=db # lưu ý, chỉnh thành localhost nếu chạy local, nếu tạo network connect đến container chứa service db thì để nguyên
POSTGRES_DB=postgres

API_BASE_URL=
SURREAL_ADDRESS=surrealdb # lưu ý, chỉnh thành localhost nếu chạy local, nếu tạo network connect đến container suurealdb thì để nguyên
SURREAL_PORT=8000
SURREAL_USER=root
SURREAL_PASSWORD=root
SURREAL_NAMESPACE=open_notebook
SURREAL_DATABASE=production

OPENAI_API_KEY=
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://api.studio.nebius.ai/v1

DEFAULT_CHAT_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
DEFAULT_TRANSFORMATION_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
DEFAULT_LARGE_CONTEXT_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
DEFAULT_TEXT_TO_SPEECH_MODEL=
DEFAULT_SPEECH_TO_TEXT_MODEL=
DEFAULT_TOOLS_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
DEFAULT_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536

# LANGUAGE_MODEL_PROVIDER=openai 
LANGUAGE_MODEL_PROVIDER=openrouter
```

```bash
bash run.sh
```

**What gets created:**
```
data/
├── uploads/     # Your notebooks and research content
```

**Simple run:**
```bash
python utils/auto_setup_step2_notebooks.py
python utils/auto_setup_step3_source/py
python utils/ask_chat_session.py
```



