# app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services import registrar_entrada, registrar_saida, listar_veiculos, resetar_banco, obter_estatisticas

app = FastAPI(title="API Controle de Veículos")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite requisições de qualquer origem
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/entrada")
def entrada(placa: str, tipo: str):
    return registrar_entrada(placa, tipo)


@app.post("/saida")
def saida(placa: str):
    return registrar_saida(placa)


@app.get("/veiculos")
def veiculos():
    dados = listar_veiculos()
    return [
        {"placa": v[0], "tipo": v[1], "entrada": v[2]}
        for v in dados
    ]


@app.post("/reset")
def reset():
    return resetar_banco()


@app.get("/estatisticas")
def estatisticas():
    return obter_estatisticas()
