import sqlite3
import re
import csv
import os
from datetime import datetime

# Conexao com o banco de dados
conn = sqlite3.connect("estacionamento.db")
cursor = conn.cursor()

# criar tabela
cursor.execute("""CREATE TABLE IF NOT EXISTS movimentacoes ( id INTEGER PRIMARY KEY AUTOINCREMENT,
               placa TEXT NOT NULL, tipo TEXT NOT NULL, entrada TEXT NOT NULL, saida TEXT)""")
conn.commit()

# normalizacao da placa


def normalizar_placa(placa):
    return placa.upper().replace("-", "").replace(" ", "")

# validacao da placa


def placa_valida(placa):
    placa = normalizar_placa(placa)

    padrao_antigo = r'^[A-Z]{3}[0-9]{4}$'
    padrao_mercosul = r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$'

    return (
        re.match(padrao_antigo, placa) is not None or
        re.match(padrao_mercosul, placa) is not None
    )

# registro de entrada


def registrar_entrada():
    placa = normalizar_placa(input("Placa do  veiculo: "))

    if not placa_valida(placa):
        print("Placa invalida! Ex: ABC1234 OU ABC1D23")
        return

    # verificacao se o carro está no pátio
    cursor.execute("""
                   SELECT 1 FROM movimentacoes WHERE placa = ?
                   AND saida IS NULL""", (placa,))

    if cursor.fetchone():
        print("Veiculo já está no estacionamento!")
        return

    tipo = input("Tipo do veiculo: ")
    entrada = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    cursor.execute("""
                   INSERT INTO movimentacoes (placa, tipo, entrada)
                   VALUES (?, ?, ?)
                   """, (placa, tipo, entrada))

    conn.commit()
    print("Entrada do veículo registrada com sucesso!")

# registro de saida


def registrar_saida():
    placa = normalizar_placa(input("Placa do veículo: "))

    if not placa_valida(placa):
        print("Placa Inválida!")
        return

    saida = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    cursor.execute("""UPDATE movimentacoes
                   SET saida = ?
                   WHERE placa = ? AND saida IS NULL""",
                   (saida, placa))

    if cursor.rowcount == 0:
        print("Veiculo não encontrado ou já saiu.")
    else:
        conn.commit()
        print("Saída de veículo, registrada com sucesso!")


def listar_veiculos_dentro():
    cursor.execute("""SELECT placa, tipo, entrada FROM movimentacoes
                   WHERE saida IS NULL""")
    veiculos = cursor.fetchall()

    if not veiculos:
        print("Nenhum veiculo no estacionamento.")
    else:
        for v in veiculos:
            print(f"Placa: {v[0]} | Tipo: {v[1]} | Entrada: {v[2]}")

# Criar relatorios


def relatório(tipo):
    if tipo == "diario":
        filtro = datetime.now().strftime("%d-%m-%Y")
        titulo = f"RELATÓRIO DO DIA {filtro}"
        like = f"{filtro}%"

    elif tipo == "mensal":
        filtro = datetime.now().strftime("%m-%Y")
        titulo = f"%-{filtro}%"
        like = f"{filtro}%"

    else:
        print("Tipo de relatório inválido")
        return

    cursor.execute("""
        SELECT placa, tipo, entrada, saida
        FROM movimentacoes
        WHERE entrada LIKE ?
        """, (like,))

    registros = cursor.fetchall()

    print(f"\n{titulo}")

    if not registros:
        print("Nenhuma movimentacao encontrada.")
    else:
        for r in registros:
            print(
                f"Placa: {r[0]} | Tipo: {r[1]} | Entrada: {r[2]} | Saida: {r[3]}")

# importar relatorios


def exportar_relatório(tipo):
    pasta_projeto = os.path.dirname(os.path.abspath(__file__))
    if tipo == "diario":
        filtro = datetime.now().strftime("%d-%m-%Y")
        nome_arquivo = f"relatorio_diario_{filtro}.csv"
        like = f"{filtro}%"

    elif tipo == "mensal":
        filtro = datetime.now().strftime("%m-%Y")
        nome_arquivo = f"relatorio_mensal_{filtro}.csv"
        like = f"%-{filtro}%"

    else:
        print("Tipo inválido")
        return

    caminho = os.path.join(pasta_projeto, nome_arquivo)

    cursor.execute("""
        SELECT placa, tipo, entrada, saida
        FROM movimentacoes
        WHERE entrada LIKE ?
    """, (like,))

    registros = cursor.fetchall()

    if not registros:
        print("Nenhum dado para exportar.")
        return

    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        writer = csv.writer(arquivo, delimiter=";")
        writer.writerow(["Placa", "Tipo", "Entrada", "Saída"])
        writer.writerows(registros)

    print(f"Relatório exportado com sucesso em:\n{caminho}")


def menu():
    while True:
        print("""
            ====== CONTROLE DE VEICULOS ======
                    1 - Registrar entrada 
                    2 - Registrar saida 
                    3 - Listar veiculos no pátio 
                    4 - Relatório Mensal
                    5 - Relatório Diario
                    6 - Exportar Relatório Diario
                    7 - Exportar Relatório Mensal
                    0 - Sair
                    =================================
                    """)

        opcao = input("Escolha uma opcão: ")

        if opcao == "1":
            registrar_entrada()
        elif opcao == "2":
            registrar_saida()
        elif opcao == "3":
            listar_veiculos_dentro()
        elif opcao == "4":
            relatório("mensal")
        elif opcao == "5":
            relatório("diario")
        elif opcao == "6":
            exportar_relatório("diario")
        elif opcao == "7":
            exportar_relatório("mensal")
        elif opcao == "0":
            print("Encerrando o sistema, bye...")
            break
        else:
            print("Opcão inválida!")


menu()
conn.close()
