"""PS06 Banking Transaction Risk Investigation Assistant — single entry point.

Run it with:
    pip install -r requirements.txt
    python app.py

That is everything. One command starts the backend and the web UI together
on http://0.0.0.0:8000. No build steps, no extra terminals, no manual setup.
"""

import uvicorn

from core.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")