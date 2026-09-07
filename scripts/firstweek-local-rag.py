"""Run the existing FirstWeek router locally, reading only local generated tokens."""
import json
import os
from pathlib import Path
import sys
from dotenv import dotenv_values
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
config = json.loads((root/'.firstweek/local/runtime.json').read_text())
# Load only provider credentials; unrelated legacy service settings stay out of this host.
for key, value in dotenv_values(root/'.env').items():
    if key in {'GROQ_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY', 'GLM_API_KEY', 'OPENROUTER_API_KEY'} and value:
        os.environ.setdefault(key, value)
os.environ.update(FIRSTWEEK_SERVICE_TOKEN=config['serviceToken'], FIRSTWEEK_INDEX_PATH=str(root/'.firstweek/knowledge.sqlite3'), LANGCHAIN_TRACING_V2='false')
os.environ.setdefault('FIRSTWEEK_GENERATE', 'true')
os.environ.setdefault('FIRSTWEEK_SEMANTIC', 'true')
os.environ.setdefault('FIRSTWEEK_EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
os.environ.setdefault('HF_HOME', str(root/'.firstweek/models'))
if __name__ == '__main__':
    import uvicorn
    uvicorn.run('RAG.firstweek.api:app', host='127.0.0.1', port=8003, log_level='warning')
