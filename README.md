## 🚀 Quick Start

Ready to try Open Notebook? Choose your preferred method:

### ⚡ Instant Setup

Setup in .env
```bash
OPENAI_API_KEY=
EMBEDDING_BASE_URL= (set up if you need to use a local model instead of ChatGPT)
OPENROUTER_BASE_URL=
OPENROUTER_API_KEY=
SURREAL_ADDRESS=
SURREAL_PORT= 
SURREAL_USER=
SURREAL_PASS=
SURREAL_NAMESPACE=
SURREAL_DATABASE=
```

```bash
docker run -d \
  --name surrealdb \
  -p 8000:8000 \
  -v "$(pwd)/surreal_data:/mydata" \
  -e SURREAL_EXPERIMENTAL_GRAPHQL=true \
  --restart always \
  surrealdb/surrealdb:v2 \
  start --log info --user root --pass root rocksdb:/mydata/mydatabase.db
```

```bash
bash run.sh
```

**What gets created:**
```
open-notebook/
├── notebook_data/     # Your notebooks and research content
└── surreal_data/      # Database files
```

**Access your installation:**
- **🖥️ Main Interface**: http://localhost:8502 (Streamlit UI)
- **🔧 API Access**: http://localhost:5055 (REST API)
- **📚 API Documentation**: http://localhost:5055/docs (Interactive Swagger UI)

**Simple run:**
```bash
python utils/auto_***
```

> **⚠️ Important**: 
> 1. **Run from a dedicated folder**: Create and run this from inside a new `open-notebook` folder so your data volumes are properly organized
> 2. **Volume persistence**: The volumes (`-v ./notebook_data:/app/data` and `-v ./surreal_data:/mydata`) are essential to persist your data between container restarts. Without them, you'll lose all your notebooks and research when the container stops. -->



