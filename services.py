# services.py
import sqlite3
from datetime import datetime

conn = sqlite3.connect("estacionamento.db", check_same_thread=False)
cursor = conn.cursor()


def registrar_entrada(placa, tipo):
    entrada = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    cursor.execute("""
        SELECT 1 FROM movimentacoes 
        WHERE placa = ? AND saida IS NULL
    """, (placa,))
    if cursor.fetchone():
        return {"erro": "Veículo já está no estacionamento"}

    cursor.execute("""
        INSERT INTO movimentacoes (placa, tipo, entrada)
        VALUES (?, ?, ?)
    """, (placa, tipo, entrada))
    conn.commit()

    return {"status": "entrada registrada", "placa": placa}


def registrar_saida(placa):
    saida = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    cursor.execute("""
        UPDATE movimentacoes
        SET saida = ?
        WHERE placa = ? AND saida IS NULL
    """, (saida, placa))
    conn.commit()

    if cursor.rowcount == 0:
        return {"erro": "Veículo não encontrado"}

    return {"status": "saida registrada", "placa": placa}


def listar_veiculos():
    cursor.execute("""
        SELECT placa, tipo, entrada
        FROM movimentacoes
        WHERE saida IS NULL
    """)
    return cursor.fetchall()

def resetar_banco():
    cursor.execute("DELETE FROM movimentacoes")
    conn.commit()
    return {"status": "banco de dados resetado com sucesso"}