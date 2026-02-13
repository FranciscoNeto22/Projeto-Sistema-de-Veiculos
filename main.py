from fastapi import FastAPI

app = FastAPI(title="API Estacionamento")


@app.get("/")
def home():
    return {"status": "API do estacionamento rodando"}
