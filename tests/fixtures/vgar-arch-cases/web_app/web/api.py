import os

from core.logic import run


@app.get("/items")
def _items():
    return run(os.environ.get("API_KEY"))
