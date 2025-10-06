
uvicorn api.main:app --host 0.0.0.0 --port 4427 --reload \
 --reload-exclude 'utils/*'

# gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:4427 api.main:app


# langchain_milvus
# pip install "psycopg[binary]" psycopg_pool
# psycopg
# langgraph-checkpoint-postgres
# pip install gunicorn[uvicorn]
