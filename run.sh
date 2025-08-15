
uvicorn api.main:app --host 0.0.0.0 --port 4427 --reload --reload-dir ./ --reload-exclude ./utils/auto_setup_step1_model.py \
 --reload-exclude ./utils/auto_setup_step3_source.py \
 --reload-exclude ./utils/auto_setup_step2_notebook.py \
 --reload-exclude ./utils/chat_session.py \
 --reload-exclude ./utils/test.py \