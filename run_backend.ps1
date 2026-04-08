$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m uvicorn api.app:app --reload --app-dir src
