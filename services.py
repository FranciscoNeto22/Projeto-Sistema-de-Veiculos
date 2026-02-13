# services.py
import sqlite3
from datetime import datetime


def get_db_connection():
    return sqlite3.connect("estacionamento.db", check_same_thread=False)


def registrar_entrada(placa, tipo, responsavel=None, cpf_responsavel=None):
    entrada = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM movimentacoes 
            WHERE placa = ? AND saida IS NULL
        """, (placa,))
        if cursor.fetchone():
            return {"erro": "Veículo já está no estacionamento"}

        # garantir colunas (em caso de uso direto do services)
        try:
            cursor.execute("PRAGMA table_info(movimentacoes)")
            cols = [r[1] for r in cursor.fetchall()]
            if 'responsavel' in cols and 'cpf_responsavel' in cols:
                cursor.execute("""
                    INSERT INTO movimentacoes (placa, tipo, entrada, responsavel, cpf_responsavel)
                    VALUES (?, ?, ?, ?, ?)
                """, (placa, tipo, entrada, responsavel, cpf_responsavel))
            else:
                cursor.execute("""
                    INSERT INTO movimentacoes (placa, tipo, entrada)
                    VALUES (?, ?, ?)
                """, (placa, tipo, entrada))
        except Exception:
            cursor.execute("""
                INSERT INTO movimentacoes (placa, tipo, entrada)
                VALUES (?, ?, ?)
            """, (placa, tipo, entrada))

        conn.commit()

    return {"status": "entrada registrada", "placa": placa}


def registrar_saida(placa):
    saida = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    with get_db_connection() as conn:
        cursor = conn.cursor()
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
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT placa, tipo, entrada, responsavel, cpf_responsavel
            FROM movimentacoes
            WHERE saida IS NULL
        """)
        return cursor.fetchall()


def resetar_banco():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movimentacoes")
        conn.commit()
    return {"status": "banco de dados resetado com sucesso"}


def obter_estatisticas():
    """Retorna um resumo com os contadores usados na interface:
    - no_patio: veículos com saida IS NULL
    - sairam_hoje: veículos que tiveram saida na data de hoje
    - visitantes: veículos no pátio com tipo indicando visitante
    - pendentes: veículos no pátio com entrada há mais de 24 horas (considerado pendente)
    """
    from datetime import datetime, timedelta

    # No pátio
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT placa, tipo, entrada, saida FROM movimentacoes")
        rows = cursor.fetchall()

        now = datetime.now()
        no_patio = 0
        visitantes = 0
        pendentes = 0
        sairam_hoje = 0

        for placa, tipo, entrada_str, saida_str in rows:
            # contar no pátio
            if saida_str is None:
                no_patio += 1

                # visitantes: considerar apenas quando tipo == 'visitante' (case-insensitive)
                if tipo and isinstance(tipo, str) and tipo.strip().lower() == 'visitante':
                    visitantes += 1

                # pendentes: entrada > 24 horas
                try:
                    entrada_dt = datetime.strptime(
                        entrada_str, "%d-%m-%Y %H:%M:%S")
                    if now - entrada_dt > timedelta(hours=24):
                        pendentes += 1
                except Exception:
                    # se não for possível parsear, não conta como pendente
                    pass
            else:
                # checar se saiu hoje
                try:
                    saida_dt = datetime.strptime(
                        saida_str, "%d-%m-%Y %H:%M:%S")
                    if (saida_dt.date() == now.date()):
                        sairam_hoje += 1
                except Exception:
                    pass

    return {
        "no_patio": no_patio,
        "sairam_hoje": sairam_hoje,
        "visitantes": visitantes,
        "pendentes": pendentes,
    }
