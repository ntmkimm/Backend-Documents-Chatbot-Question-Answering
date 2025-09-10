## 🚀 Quick Start

Ready to try Open Notebook? Choose your preferred method:

### ⚡ Instant Setup

```bash
docker network create --driver bridge my_network 
docker-compose up -d # adjust when surrealdb when ur not root user (do not mount rocksdb), also consider port of postgres and surrealdb of your docker-compose
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

DEFAULT_CHAT_MODEL=Qwen/Qwen2.5-32B-Instruct
DEFAULT_TRANSFORMATION_MODEL=Qwen/Qwen2.5-32B-Instruct
DEFAULT_LARGE_CONTEXT_MODEL=Qwen/Qwen2.5-32B-Instruct
DEFAULT_TEXT_TO_SPEECH_MODEL=
DEFAULT_SPEECH_TO_TEXT_MODEL=
DEFAULT_EMBEDDING_MODEL=text-embedding-3-small
DEFAULT_TOOLS_MODEL=Qwen/Qwen2.5-32B-Instruct
```

```bash
python migrate.py # IMPORTANT: migrate function for query database in surrealdb
bash run.sh
```

**What gets created:**
```
open-notebook/
├── notebook_data/     # Your notebooks and research content
└── surreal_data/      # Database files
```

**Simple run:**
```bash
python utils/auto_***
```

> **⚠️ Important**: 
> 1. **Run from a dedicated folder**: Create and run this from inside a new `open-notebook` folder so your data volumes are properly organized
> 2. **Volume persistence**: The volumes (`-v ./notebook_data:/app/data` and `-v ./surreal_data:/mydata`) are essential to persist your data between container restarts. Without them, you'll lose all your notebooks and research when the container stops. -->
