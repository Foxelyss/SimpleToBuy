from fastapi import FastAPI
import uvicorn
import __init__
from main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
