import sqlite3
import re
import csv
import os
from datetime import datetime

# Conexao com o banco de dados
conn = sqlite3.connect("estacionamento.db")
cursor = conn.cursor()

# criar tabela (colunas adicionais para responsável e CPF podem ser adicionadas depois)
cursor.execute("""CREATE TABLE IF NOT EXISTS movimentacoes ( id INTEGER PRIMARY KEY AUTOINCREMENT,
               placa TEXT NOT NULL, tipo TEXT NOT NULL, entrada TEXT NOT NULL, saida TEXT)""")
conn.commit()


def registrar_responsavel():
    placa = normalizar_placa(input("Placa do veículo: "))

    if not placa_valida(placa):
        print("Placa inválida!")
        return

    cursor.execute("""
        SELECT 1 FROM movimentacoes
        WHERE placa = ? AND saida IS NULL
    """, (placa,))
    if not cursor.fetchone():
        print("Veículo não encontrado ou já saiu.")
        return

    responsavel = input("Nome do responsável: ").strip()
    if not responsavel:
        print("Nome do responsável é obrigatório.")
        return

    cursor.execute("""
        UPDATE movimentacoes
        SET responsavel = ?
        WHERE placa = ? AND saida IS NULL
    """, (responsavel, placa))
    conn.commit()
    print("Responsável registrado com sucesso!")


def registrar_cpf():
    placa = normalizar_placa(input("Placa do veículo: "))

    if not placa_valida(placa):
        print("Placa inválida!")
        return

    cursor.execute("""
        SELECT 1 FROM movimentacoes
        WHERE placa = ? AND saida IS NULL
    """, (placa,))
    if not cursor.fetchone():
        print("Veículo não encontrado ou já saiu.")
        return

    cpf = input("CPF do responsável: ").strip()
    if not cpf:
        print("CPF do responsável é obrigatório.")
        return

    cursor.execute("""
        UPDATE movimentacoes
        SET cpf_responsavel = ?
        WHERE placa = ? AND saida IS NULL
    """, (cpf, placa))
    conn.commit()
    print("CPF registrado com sucesso!")


def ensure_columns():
    # Garante que as colunas responsavel e cpf_responsavel existam
    cursor.execute("PRAGMA table_info(movimentacoes)")
    cols = [r[1] for r in cursor.fetchall()]
    if 'responsavel' not in cols:
        cursor.execute("ALTER TABLE movimentacoes ADD COLUMN responsavel TEXT")
    if 'cpf_responsavel' not in cols:
        cursor.execute(
            "ALTER TABLE movimentacoes ADD COLUMN cpf_responsavel TEXT")
    conn.commit()


ensure_columns()

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
    # tornar nome do responsável obrigatório e validar formato (apenas letras/espacos)

    def validar_nome(nome):
        nome = nome.strip()
        if len(nome) < 2:
            return False
        for ch in nome:
            if not (ch.isalpha() or ch.isspace()):
                return False
        return True

    while True:
        responsavel = input("Nome do responsável: ").strip()
        if not responsavel:
            print("Nome do responsável é obrigatório. Tente novamente.")
            continue
        if not validar_nome(responsavel):
            print("Nome inválido. Use apenas letras e espaços. Tente novamente.")
            continue
        break

    # Remover sufixos/prefixos comuns (Sr., Sra., Dr., Dra., Srta., Senhor(a), Dona)
    honorifics = {
        'sr', 'sra', 'sr.', 'sra.', 'dr', 'dra', 'dr.', 'dra.', 'srta', 'srta.',
        'senhor', 'senhora', 'dona', 'don', 'mr', 'mrs', 'sra(a)'
    }
    parts = [p.strip('.,') for p in responsavel.split() if p.strip()]
    filtered = [p for p in parts if p.lower().replace(
        '.', '').replace('(', '').replace(')', '') not in honorifics]
    # Normalizar nome: salvar em Title Case (cada palavra com inicial maiúscula)
    responsavel = ' '.join(w.capitalize() for w in filtered)

    # CPF obrigatório com validação básica
    def validar_cpf(cpf):
        cpf = re.sub(r'\D', '', cpf)
        if len(cpf) != 11:
            return False
        if cpf == cpf[0] * 11:
            return False

        def calc(digs):
            s = 0
            peso = len(digs) + 1
            for d in digs:
                s += int(d) * peso
                peso -= 1
            r = s % 11
            return '0' if r < 2 else str(11 - r)

        d1 = calc(cpf[:9])
        d2 = calc(cpf[:10])
        return cpf[9] == d1 and cpf[10] == d2

    while True:
        cpf_responsavel = input(
            "CPF do responsável (apenas números): ").strip()
        if not cpf_responsavel:
            print("CPF é obrigatório. Tente novamente.")
            continue
        cpf_digits = re.sub(r'\D', '', cpf_responsavel)
        if not validar_cpf(cpf_digits):
            print("CPF inválido. Digite um CPF válido com 11 dígitos.")
            continue
        cpf_responsavel = cpf_digits
        break
    entrada = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    cursor.execute("""
                   INSERT INTO movimentacoes (placa, tipo, entrada, responsavel, cpf_responsavel)
                   VALUES (?, ?, ?, ?, ?)
                   """, (placa, tipo, entrada, responsavel or None, cpf_responsavel or None))

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
    cursor.execute("""SELECT placa, tipo, entrada, responsavel, cpf_responsavel FROM movimentacoes
                   WHERE saida IS NULL""")
    veiculos = cursor.fetchall()

    if not veiculos:
        print("Nenhum veiculo no estacionamento.")
    else:
        for v in veiculos:
            placa, tipo, entrada, responsavel, cpf = v
            resp = responsavel if responsavel else '-'
            cpf_display = cpf if cpf else '-'
            print(
                f"Placa: {placa} | Tipo: {tipo} | Entrada: {entrada} | Responsável: {resp} | CPF: {cpf_display}")

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
        SELECT placa, tipo, entrada, saida, responsavel, cpf_responsavel
        FROM movimentacoes
        WHERE entrada LIKE ?
        """, (like,))

    registros = cursor.fetchall()

    print(f"\n{titulo}")

    if not registros:
        print("Nenhuma movimentacao encontrada.")
    else:
        for r in registros:
            placa, tipo, entrada, saida, responsavel, cpf = r
            resp = responsavel if responsavel else '-'
            cpf_display = cpf if cpf else '-'
            print(
                f"Placa: {placa} | Tipo: {tipo} | Entrada: {entrada} | Saida: {saida} | Responsável: {resp} | CPF: {cpf_display}")

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
        SELECT placa, tipo, entrada, saida, responsavel, cpf_responsavel
        FROM movimentacoes
        WHERE entrada LIKE ?
    """, (like,))

    registros = cursor.fetchall()

    if not registros:
        print("Nenhum dado para exportar.")
        return

    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        writer = csv.writer(arquivo, delimiter=";")
        writer.writerow(["Placa", "Tipo", "Entrada",
                        "Saída", "Responsável", "CPF"])
        writer.writerows(registros)

    print(f"Relatório exportado com sucesso em:\n{caminho}")


def menu():
    while True:
        print("""
            ====== CONTROLE DE VEICULOS ======
                    1 - Registrar entrada
                    2 - Registrar responsavel
                    3 - registrar cpf
                    4 - Registrar saida 
                    5 - Listar veiculos no pátio 
                    6 - Relatório Mensal
                    7 - Relatório Diario
                    8 - Exportar Relatório Diario
                    9 - Exportar Relatório Mensal
                    0 - Sair
                    =================================
                    """)

        opcao = input("Escolha uma opcão: ")

        if opcao == "1":
            registrar_entrada()
        elif opcao == "2":
            registrar_responsavel()
        elif opcao == "3":
            registrar_cpf()
        elif opcao == "4":
            registrar_saida()
        elif opcao == "5":
            listar_veiculos_dentro()
        elif opcao == "6":
            relatório("mensal")
        elif opcao == "7":
            relatório("diario")
        elif opcao == "8":
            exportar_relatório("diario")
        elif opcao == "9":
            exportar_relatório("mensal")
        elif opcao == "0":
            print("Encerrando o sistema, bye...")
            break
        else:
            print("Opcão inválida!")


menu()
conn.close()
