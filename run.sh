
uvicorn api.main:app --host 0.0.0.0 --port 4427 --reload \
 --reload-exclude 'utils/*'