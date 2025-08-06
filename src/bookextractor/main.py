from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return { 
        "message": "Hello, and thank you for using my app!"
    }