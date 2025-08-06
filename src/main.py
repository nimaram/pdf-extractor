from fastapi import FastAPI
from api import documents


app = FastAPI()
app.include_router(documents.router)

@app.get("/")
def read_root():
    return { 
        "message": "Hello, and thank you for using my app!"
    }