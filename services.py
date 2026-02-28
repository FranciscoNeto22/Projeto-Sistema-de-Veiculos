# services.py
import csv
import os
import sqlite3
from datetime import datetime
import zipfile
from typing import Optional
import bcrypt
import json
import pytz
try:
    import psutil
except ImportError:
    psutil = None

def get_db_connection():
    return sqlite3.connect("estacionamento.db", timeout=10, check_same_thread=False)


def registrar_entrada(placa, tipo, empresa_id, responsavel=None, cpf_responsavel=None):
    entrada = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM movimentacoes 
            WHERE placa = ? AND saida IS NULL AND empresa_id = ?
        """, (placa, empresa_id))
        if cursor.fetchone():
            return {"erro": "Veículo já está no estacionamento"}

        # garantir colunas (em caso de uso direto do services)
        try:
            cursor.execute("PRAGMA table_info(movimentacoes)")
            cols = [r[1] for r in cursor.fetchall()]
            if 'responsavel' in cols and 'cpf_responsavel' in cols:
                cursor.execute("""
                    INSERT INTO movimentacoes (placa, tipo, entrada, responsavel, cpf_responsavel, empresa_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (placa, tipo, entrada, responsavel, cpf_responsavel, empresa_id))
            else:
                cursor.execute("""
                    INSERT INTO movimentacoes (placa, tipo, entrada, empresa_id)
                    VALUES (?, ?, ?, ?)
                """, (placa, tipo, entrada, empresa_id))
        except Exception:
            cursor.execute("""
                INSERT INTO movimentacoes (placa, tipo, entrada, empresa_id)
                VALUES (?, ?, ?, ?)
            """, (placa, tipo, entrada, empresa_id))

    return {"status": "entrada registrada", "placa": placa}


def registrar_saida(placa, empresa_id):
    saida = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE movimentacoes
            SET saida = ?
            WHERE placa = ? AND saida IS NULL AND empresa_id = ?
        """, (saida, placa, empresa_id))

        if cursor.rowcount == 0:
            return {"erro": "Veículo não encontrado"}

    return {"status": "saida registrada", "placa": placa}


def listar_veiculos(empresa_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT placa, tipo, entrada, responsavel, cpf_responsavel
            FROM movimentacoes
            WHERE saida IS NULL AND empresa_id = ?
        """, (empresa_id,))
        return cursor.fetchall()


def listar_saidas(empresa_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT placa, tipo, entrada, saida, responsavel, cpf_responsavel
            FROM movimentacoes
            WHERE saida IS NOT NULL AND empresa_id = ?
            ORDER BY id DESC
        """, (empresa_id,))
        return cursor.fetchall()


def resetar_banco(empresa_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movimentacoes WHERE empresa_id = ?", (empresa_id,))
    return {"status": "Veículos da sua empresa foram resetados com sucesso"}


def registrar_cadastro(dados, empresa_id):
    # Garantir que a tabela existe
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cadastros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT,
                data_nascimento TEXT,
                telefone TEXT,
                cep TEXT,
                endereco TEXT,
                numero TEXT,
                cargo TEXT,
                email TEXT,
                cpf TEXT,
                empresa TEXT,
                placa TEXT,
                tipo_veiculo TEXT,
                empresa_id INTEGER NOT NULL
            )
        """)

        # Correção: Verificar se a coluna 'numero' existe e adicionar se faltar (Migração Automática)
        cursor.execute("PRAGMA table_info(cadastros)")
        colunas_existentes = [col[1] for col in cursor.fetchall()]
        if 'numero' not in colunas_existentes:
            cursor.execute("ALTER TABLE cadastros ADD COLUMN numero TEXT")
        if 'tipo_veiculo' not in colunas_existentes:
            cursor.execute(
                "ALTER TABLE cadastros ADD COLUMN tipo_veiculo TEXT")

        cursor.execute("""
            INSERT INTO cadastros (nome, data_nascimento, telefone, cep, endereco, numero, cargo, email, cpf, empresa, placa, tipo_veiculo, empresa_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (dados.get('nome'), dados.get('data_nascimento'), dados.get('telefone'),
              dados.get('cep'), dados.get('endereco'), dados.get('numero'),
              dados.get('cargo'), dados.get('email'), dados.get('cpf'),
              dados.get('empresa'), dados.get('placa'), dados.get('tipo_veiculo'), empresa_id))

    # Registrar entrada automaticamente se houver placa informada
    if dados.get('placa'):
        tipo = dados.get('tipo_veiculo') if dados.get(
            'tipo_veiculo') else "Carro"
        registrar_entrada(dados.get('placa'), tipo, empresa_id,
                          dados.get('nome'), dados.get('cpf'))

    return {"status": "Cadastro realizado com sucesso!"}


def listar_cadastros(empresa_id, busca: Optional[str] = None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Garante que a tabela exista antes de consultar
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cadastros (
                id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, data_nascimento TEXT, telefone TEXT, cep TEXT,
                endereco TEXT, numero TEXT, cargo TEXT, email TEXT, cpf TEXT,
                empresa TEXT, placa TEXT, tipo_veiculo TEXT, empresa_id INTEGER
            )
        """)

        if busca:
            query = """
                SELECT id, nome, cpf, telefone, email, cargo, empresa, placa
                FROM cadastros
                WHERE empresa_id = ? AND (nome LIKE ? OR placa LIKE ?)
                ORDER BY nome
            """
            params = (empresa_id, f"%{busca}%", f"%{busca}%")
            cursor.execute(query, params)
        else:
            query = """
                SELECT id, nome, cpf, telefone, email, cargo, empresa, placa
                FROM cadastros
                WHERE empresa_id = ?
                ORDER BY nome
            """
            cursor.execute(query, (empresa_id,))

        return cursor.fetchall()


def excluir_cadastro(cadastro_id: int, empresa_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cadastros WHERE id = ? AND empresa_id = ?", (cadastro_id, empresa_id))
        if cursor.rowcount == 0:
            return {"erro": "Cadastro não encontrado."}
    return {"status": "Cadastro excluído com sucesso!"}


def get_cadastro_por_id(cadastro_id: int, empresa_id: int):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cadastros WHERE id = ? AND empresa_id = ?", (cadastro_id, empresa_id))
        cadastro = cursor.fetchone()
        return cadastro


def atualizar_cadastro(cadastro_id: int, dados, empresa_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE cadastros SET
                nome = ?, data_nascimento = ?, telefone = ?, cep = ?, endereco = ?,
                numero = ?, cargo = ?, email = ?, cpf = ?, empresa = ?, placa = ?, tipo_veiculo = ?
            WHERE id = ? AND empresa_id = ?
        """, (
            dados.get('nome'), dados.get(
                'data_nascimento'), dados.get('telefone'),
            dados.get('cep'), dados.get('endereco'), dados.get('numero'),
            dados.get('cargo'), dados.get('email'), dados.get('cpf'),
            dados.get('empresa'), dados.get(
                'placa'), dados.get('tipo_veiculo'),
            cadastro_id, empresa_id
        ))
        if cursor.rowcount == 0:
            return {"erro": "Cadastro não encontrado para atualizar."}
    return {"status": "Cadastro atualizado com sucesso!"}


def setup_usuarios():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'operador',
                empresa_id INTEGER NOT NULL,
                FOREIGN KEY (empresa_id) REFERENCES empresas (id)
            )
        """)
        
        # --- NOVA TABELA DE EMPRESAS ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS empresas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_empresa TEXT NOT NULL,
                cnpj TEXT UNIQUE NOT NULL
            )
        """)

        # --- MIGRAÇÃO AUTOMÁTICA DE COLUNAS ---
        cursor.execute("PRAGMA table_info(usuarios)")
        cols = [r[1] for r in cursor.fetchall()]
        if 'role' not in cols:
            cursor.execute(
                "ALTER TABLE usuarios ADD COLUMN role TEXT DEFAULT 'operador'")
            # Atualiza o admin para ter permissão total
            cursor.execute(
                "UPDATE usuarios SET role = 'admin' WHERE username = 'admin'")
        
        if 'empresa_id' not in cols:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN empresa_id INTEGER NOT NULL DEFAULT 1")

        # Garante que a empresa padrão (ID 1) exista
        cursor.execute("SELECT id FROM empresas WHERE id = 1")
        if not cursor.fetchone():
            cursor.execute("INSERT OR IGNORE INTO empresas (id, nome_empresa, cnpj) VALUES (1, 'Empresa Padrão', '00000000000000')")

        # Criar tabela de configurações (para o layout dinâmico)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracoes (
                chave TEXT PRIMARY KEY,
                valor TEXT
            )
        """)

        # --- CHAT TABLES ---
        # Tabela de Protocolos/Conversas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_protocolos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_cliente TEXT NOT NULL,
                assunto TEXT,
                data_inicio TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'aberto', -- aberto, fechado
                empresa_id INTEGER NOT NULL
            )
        """)

        # Migração: Verificar se a tabela chat_mensagens antiga existe (sem protocolo_id)
        cursor.execute("PRAGMA table_info(chat_mensagens)")
        cols_chat = [r[1] for r in cursor.fetchall()]
        if 'usuario' in cols_chat and 'protocolo_id' not in cols_chat:
            # Tabela antiga incompatível encontrada. Recriar.
            cursor.execute("DROP TABLE chat_mensagens")

        # Tabela de Mensagens
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_mensagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                protocolo_id INTEGER NOT NULL,
                usuario TEXT NOT NULL,
                texto TEXT NOT NULL,
                data_hora TEXT NOT NULL,
                empresa_id INTEGER NOT NULL,
                FOREIGN KEY (protocolo_id) REFERENCES chat_protocolos (id)
            )
        """)

        # --- ARQUIVOS / NUVEM ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS arquivos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_original TEXT,
                caminho_salvo TEXT,
                tamanho TEXT,
                data_upload TEXT,
                uploader TEXT,
                empresa_id INTEGER NOT NULL
            )
        """)

        # --- HISTÓRICO / LOGS ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico_acoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT,
                acao TEXT,
                detalhes TEXT,
                data_hora TEXT,
                empresa_id INTEGER NOT NULL
            )
        """)

        # --- MONITORAMENTO / PERFORMANCE ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TEXT,
                cpu_usage REAL,
                ram_usage REAL,
                disk_usage REAL,
                ping_local INTEGER,
                ping_railway INTEGER
            )
        """)

        # Criar usuário padrão se não existir
        cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
        if not cursor.fetchone():
            admin_pass_hash = get_hash_senha("admin")
            cursor.execute(
                "INSERT INTO usuarios (username, password_hash, role, empresa_id) VALUES (?, ?, ?, ?)", ('admin', admin_pass_hash, 'admin', 1))

        # Criar usuário DEV (Dono) se não existir
        cursor.execute(
            "SELECT id FROM usuarios WHERE username = 'neto@dev.com'")
        if not cursor.fetchone():
            # Senha solicitada: 126918dev#@
            dev_pass_hash = get_hash_senha("126918dev#@")
            cursor.execute(
                "INSERT INTO usuarios (username, password_hash, role, empresa_id) VALUES (?, ?, ?, ?)", ('neto@dev.com', dev_pass_hash, 'dev', 1))

        # --- FIXO: USUÁRIO DO COLEGA (Para não sumir nas atualizações) ---
        pass_hash_colega = get_hash_senha("784512")
        cursor.execute("SELECT id FROM usuarios WHERE username = 'rother'")

        if cursor.fetchone():
            # Se já existe, ATUALIZA a senha (para corrigir caso esteja errada no banco)
            cursor.execute(
                "UPDATE usuarios SET password_hash = ?, role = 'operador', empresa_id = 1 WHERE username = 'rother'", (pass_hash_colega,))
        else:
            # Se não existe, CRIA
            cursor.execute("INSERT INTO usuarios (username, password_hash, role, empresa_id) VALUES (?, ?, ?, ?)",
                           ('rother', pass_hash_colega, 'operador', 1))

        # --- MIGRAÇÃO DE DADOS EXISTENTES PARA A EMPRESA PADRÃO (ID 1) ---
        tabelas_para_migrar = ['movimentacoes', 'cadastros', 'chat_protocolos', 'chat_mensagens', 'arquivos', 'historico_acoes']
        for tabela in tabelas_para_migrar:
            try:
                cursor.execute(f"PRAGMA table_info({tabela})")
                cols = [r[1] for r in cursor.fetchall()]
                if 'empresa_id' not in cols:
                    cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN empresa_id INTEGER NOT NULL DEFAULT 1")
            except sqlite3.OperationalError:
                # Tabela pode não existir ainda, ignora o erro
                pass

    # Exporta todos os usuários para o CSV para garantir sincronia
    exportar_usuarios_para_csv()


def criar_usuario(username, password, role, empresa_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            hash_senha = get_hash_senha(password)
            cursor.execute(
                "INSERT INTO usuarios (username, password_hash, role, empresa_id) VALUES (?, ?, ?, ?)", (username, hash_senha, role, empresa_id))
            # Salva no backup CSV (Excel)
            log_usuario_csv(username, password, role, "CRIADO")
            return {"status": "Usuário criado com sucesso!"}
        except sqlite3.IntegrityError:
            return {"erro": "Nome de usuário já existe nesta empresa."}


def listar_usuarios(empresa_id):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, role FROM usuarios WHERE empresa_id = ? AND username NOT IN ('admin', 'neto@dev.com') ORDER BY username", (empresa_id,))
        return [dict(row) for row in cursor.fetchall()]


def excluir_usuario(user_id, empresa_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Proteção para não excluir o admin principal (id 1 ou nome admin)
        cursor.execute(
            "SELECT username FROM usuarios WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        if user and user[0] == 'admin':
            return {"erro": "Não é possível excluir o superusuário admin."}

        cursor.execute("DELETE FROM usuarios WHERE id = ? AND empresa_id = ?", (user_id, empresa_id))
        return {"status": "Usuário excluído."}


def atualizar_usuario(user_id, username, password, role, empresa_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Verifica se o username já existe para OUTRO usuário (evitar duplicatas)
        cursor.execute(
            "SELECT id FROM usuarios WHERE username = ? AND id != ? AND empresa_id = ?", (username, user_id, empresa_id))
        if cursor.fetchone():
            return {"erro": "Nome de usuário já existe."}

        # Se a senha foi fornecida (não vazia), atualiza tudo (com hash)
        if password and password.strip():
            hash_senha = get_hash_senha(password)
            cursor.execute("""
                UPDATE usuarios SET username = ?, password_hash = ?, role = ? WHERE id = ? AND empresa_id = ?
            """, (username, hash_senha, role, user_id, empresa_id))
            log_usuario_csv(username, password, role, "ATUALIZADO")
        else:
            # Se não, atualiza apenas dados cadastrais, mantendo a senha antiga
            cursor.execute("""
                UPDATE usuarios SET username = ?, role = ? WHERE id = ? AND empresa_id = ?
            """, (username, role, user_id, empresa_id))
            log_usuario_csv(username, "MANTIDA", role, "ATUALIZADO")

        if cursor.rowcount == 0:
            return {"erro": "Usuário não encontrado."}

    return {"status": "Usuário atualizado com sucesso!"}


def verificar_senha(senha_plana, senha_hash):
    # Converte para bytes se for string, pois o bcrypt exige bytes
    if isinstance(senha_plana, str):
        senha_plana = senha_plana.encode('utf-8')
    if isinstance(senha_hash, str):
        senha_hash = senha_hash.encode('utf-8')
    return bcrypt.checkpw(senha_plana, senha_hash)


def get_hash_senha(senha):
    if isinstance(senha, str):
        senha = senha.encode('utf-8')
    hashed = bcrypt.hashpw(senha, bcrypt.gensalt())
    return hashed.decode('utf-8')


def get_usuario(username: str, empresa_id: int):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM usuarios WHERE username = ? AND empresa_id = ?", (username, empresa_id))
        return cursor.fetchone()

def get_empresa_por_cnpj(cnpj: str):
    """Busca uma empresa pelo CNPJ."""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM empresas WHERE cnpj = ?", (cnpj,))
        return cursor.fetchone()

def get_empresa_por_id(empresa_id: int):
    """Busca uma empresa pelo ID (usado para login de admin/dev sem CNPJ)."""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM empresas WHERE id = ?", (empresa_id,))
        return cursor.fetchone()


def executar_sql_raw(query: str):
    """
    Executa SQL direto. PERIGO: Apenas para uso do desenvolvedor/admin!
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query)
            conn.commit()
            if cursor.description:
                colunas = [description[0]
                           for description in cursor.description]
                resultados = cursor.fetchall()
                return {"colunas": colunas, "resultados": resultados}
            return {"status": f"Comando executado. Linhas afetadas: {cursor.rowcount}"}
        except Exception as e:
            return {"erro": str(e)}

# --- Funções do Chat (Refatoradas com Protocolo) ---


def get_open_protocol_for_user(username, empresa_id):
    """Encontra um protocolo aberto para um usuário específico."""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM chat_protocolos WHERE usuario_cliente = ? AND empresa_id = ? AND status IN ('aberto', 'avaliando') ORDER BY id DESC LIMIT 1",
            (username, empresa_id)
        )
        return cursor.fetchone()


def get_protocol_by_id(protocol_id, empresa_id):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM chat_protocolos WHERE id = ? AND empresa_id = ?", (protocol_id, empresa_id))
        return cursor.fetchone()


def get_messages_by_protocol(protocolo_id, empresa_id):
    """Lista todas as mensagens de um protocolo específico."""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM chat_mensagens WHERE protocolo_id = ? AND empresa_id = ? ORDER BY id ASC",
            (protocolo_id, empresa_id)
        )
        return [dict(row) for row in cursor.fetchall()]


def save_chat_message(protocolo_id, usuario, texto, empresa_id):
    """Salva uma nova mensagem em um protocolo existente."""
    fuso = pytz.timezone('America/Sao_Paulo')
    data_hora = datetime.now(fuso).strftime("%d/%m %H:%M")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_mensagens (protocolo_id, usuario, texto, data_hora, empresa_id) VALUES (?, ?, ?, ?, ?)",
            (protocolo_id, usuario, texto, data_hora, empresa_id)
        )
        conn.commit()
    return {"status": "Mensagem enviada", "protocolo_id": protocolo_id}


def create_protocol_and_message(usuario, texto, empresa_id):
    """Cria um novo protocolo e adiciona a primeira mensagem."""
    fuso = pytz.timezone('America/Sao_Paulo')
    data_hora = datetime.now(fuso).strftime("%d/%m %H:%M")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # 1. Criar o protocolo
        assunto = texto[:50] + '...' if len(texto) > 50 else texto
        cursor.execute(
            "INSERT INTO chat_protocolos (usuario_cliente, assunto, data_inicio, status, empresa_id) VALUES (?, ?, ?, 'aberto', ?)",
            (usuario, assunto, data_hora, empresa_id)
        )
        protocolo_id = cursor.lastrowid

        # 2. Inserir a primeira mensagem
        cursor.execute(
            "INSERT INTO chat_mensagens (protocolo_id, usuario, texto, data_hora, empresa_id) VALUES (?, ?, ?, ?, ?)",
            (protocolo_id, usuario, texto, data_hora, empresa_id)
        )
        conn.commit()
    return {"status": "Protocolo criado", "protocolo_id": protocolo_id}


def list_protocols():
    """Lista todos os protocolos para o painel do dev."""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chat_protocolos ORDER BY id DESC")
        return [dict(row) for row in cursor.fetchall()]


def get_protocols_for_user_history(username, empresa_id):
    """Lista todos os protocolos de um usuário (abertos e fechados)."""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, assunto, data_inicio, status FROM chat_protocolos WHERE usuario_cliente = ? AND empresa_id = ? ORDER BY id DESC",
            (username, empresa_id)
        )
        return [dict(row) for row in cursor.fetchall()]


def update_protocol_status(protocol_id, status, empresa_id):
    """Atualiza o status de um protocolo (ex: 'avaliando', 'fechado')."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE chat_protocolos SET status = ? WHERE id = ? AND empresa_id = ?", (status, protocol_id, empresa_id))
        conn.commit()
    return {"status": "updated"}


def close_protocols_bulk(protocol_ids, empresa_id):
    """Encerra múltiplos protocolos de uma vez (sem avaliação)."""
    if not protocol_ids:
        return {"count": 0}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in protocol_ids)
        sql = f"UPDATE chat_protocolos SET status = 'fechado' WHERE id IN ({placeholders}) AND empresa_id = ?"
        cursor.execute(sql, protocol_ids + [empresa_id])
        conn.commit()
        return {"count": cursor.rowcount}


def get_global_last_message_id():
    """Retorna o ID da última mensagem do sistema para verificação de notificações globais."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(id) FROM chat_mensagens")
        row = cursor.fetchone()
        return row[0] if row and row[0] else 0

# --- Funções de Monitoramento Histórico ---

def salvar_historico_performance(cpu, ram, disk, ping_local, ping_railway):
    """Salva um snapshot da performance do servidor."""
    # Salva em formato ISO com Timezone (ex: 2023-10-27T16:30:00-03:00) para o frontend converter corretamente
    data_hora = datetime.now().astimezone().isoformat()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # GARANTIA: Cria a tabela se não existir (corrige o erro sem precisar reiniciar)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TEXT,
                cpu_usage REAL,
                ram_usage REAL,
                disk_usage REAL,
                ping_local INTEGER,
                ping_railway INTEGER
            )
        """)
        cursor.execute("""
            INSERT INTO historico_performance (data_hora, cpu_usage, ram_usage, disk_usage, ping_local, ping_railway)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (data_hora, cpu, ram, disk, ping_local, ping_railway))

def obter_historico_performance(data_filtro):
    """Busca o histórico de um dia específico (YYYY-MM-DD)."""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # GARANTIA: Cria a tabela se não existir
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TEXT,
                cpu_usage REAL,
                ram_usage REAL,
                disk_usage REAL,
                ping_local INTEGER,
                ping_railway INTEGER
            )
        """)

        # Filtra pela data (string startswith)
        cursor.execute("""
            SELECT data_hora, cpu_usage, ram_usage, ping_local, ping_railway 
            FROM historico_performance 
            WHERE data_hora LIKE ? 
            ORDER BY data_hora ASC
        """, (f"{data_filtro}%",))
        return [dict(row) for row in cursor.fetchall()]

def limpar_historico_performance():
    """Apaga todo o histórico de performance."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM historico_performance")
        return {"status": "Histórico limpo com sucesso!"}

# --- Funções de Histórico / Logs ---

def salvar_arquivo_db(nome_original, caminho_salvo, tamanho, uploader, empresa_id):
    fuso = pytz.timezone('America/Sao_Paulo')
    data_upload = datetime.now(fuso).strftime("%d/%m/%Y %H:%M")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO arquivos (nome_original, caminho_salvo, tamanho, data_upload, uploader, empresa_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nome_original, caminho_salvo, tamanho, data_upload, uploader, empresa_id))
    return {"status": "Arquivo salvo"}

def listar_arquivos_db(empresa_id):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM arquivos WHERE empresa_id = ? ORDER BY id DESC", (empresa_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_arquivo_por_id(arquivo_id, empresa_id):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM arquivos WHERE id = ? AND empresa_id = ?", (arquivo_id, empresa_id))
        return cursor.fetchone()

def excluir_arquivo_db(arquivo_id, empresa_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM arquivos WHERE id = ? AND empresa_id = ?", (arquivo_id, empresa_id))

def registrar_log(usuario, acao, empresa_id, detalhes=""):
    """Registra uma ação no histórico."""
    fuso = pytz.timezone('America/Sao_Paulo')
    data_hora = datetime.now(fuso).strftime("%d/%m/%Y %H:%M:%S")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO historico_acoes (usuario, acao, detalhes, data_hora, empresa_id)
                VALUES (?, ?, ?, ?, ?)
            """, (usuario, acao, detalhes, data_hora, empresa_id))
    except Exception as e:
        print(f"Erro ao salvar log: {e}")

def listar_historico(empresa_id, usuario: Optional[str] = None):
    """Lista as últimas 100 ações do sistema, com filtro opcional por usuário."""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM historico_acoes"
        params = []
        query += " WHERE empresa_id = ?"
        params.append(empresa_id)

        if usuario:
            query += " AND usuario = ?"
            params.append(usuario)
            
        query += " ORDER BY id DESC LIMIT 100"
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def listar_usuarios_do_historico(empresa_id):
    """Retorna uma lista única de usuários que possuem registros no histórico."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT usuario FROM historico_acoes WHERE empresa_id = ? ORDER BY usuario ASC", (empresa_id,))
        return [row[0] for row in cursor.fetchall()]

def gerar_excel_historico(empresa_id, usuario: Optional[str] = None):
    """Gera o caminho de um arquivo Excel (.xlsx) com o histórico, com filtro opcional."""
    if usuario:
        safe_usuario = "".join(c for c in usuario if c.isalnum() or c in ('-', '_')).rstrip()
        filename = f"historico_{safe_usuario}.xlsx"
    else:
        filename = "historico_completo.xlsx"
        
    arquivo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    
    import pandas as pd
    
    with get_db_connection() as conn:
        query = "SELECT data_hora, usuario, acao, detalhes FROM historico_acoes"
        params = []
        query += " WHERE empresa_id = ?"
        params.append(empresa_id)
        if usuario:
            query += " AND usuario = ?"
            params.append(usuario)
        query += " ORDER BY id DESC"
        
        df = pd.read_sql_query(query, conn, params=params)
        
        df.rename(columns={
            'data_hora': 'Data/Hora', 'usuario': 'Usuário', 'acao': 'Ação', 'detalhes': 'Detalhes'
        }, inplace=True)

        df.to_excel(arquivo_path, index=False, engine='openpyxl')
    
    return arquivo_path, filename

# --- Funções de Configuração de Layout (CSS Dinâmico) ---


def salvar_css_personalizado(css_text):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Upsert (Inserir ou Atualizar)
        cursor.execute(
            "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES ('custom_css', ?)", (css_text,))
    return {"status": "Layout atualizado com sucesso!"}


def ler_css_personalizado():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Garante que a tabela existe (caso chame direto)
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY, valor TEXT)")
        cursor.execute(
            "SELECT valor FROM configuracoes WHERE chave = 'custom_css'")
        row = cursor.fetchone()
        return row[0] if row else ""


def salvar_config_visual(config_json):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Salva o JSON como string
        config_str = json.dumps(config_json)
        cursor.execute(
            "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES ('visual_config', ?)", (config_str,))
    return {"status": "Configuração visual salva!"}


def ler_config_visual():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY, valor TEXT)")
        cursor.execute(
            "SELECT valor FROM configuracoes WHERE chave = 'visual_config'")
        row = cursor.fetchone()
        return json.loads(row[0]) if row else {}

# --- Funções de Versão do App ---


def set_app_version(version, changelog):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES ('app_version', ?)", (version,))
        cursor.execute(
            "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES ('app_changelog', ?)", (changelog,))
    return {"status": "Versão publicada com sucesso!"}


def get_app_version():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT valor FROM configuracoes WHERE chave = 'app_version'")
        version_row = cursor.fetchone()
        cursor.execute(
            "SELECT valor FROM configuracoes WHERE chave = 'app_changelog'")
        changelog_row = cursor.fetchone()
        return {
            "version": version_row[0] if version_row else "1.0.0",
            "changelog": changelog_row[0] if changelog_row else "Versão inicial."
        }


def obter_estatisticas(empresa_id):
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
        cursor.execute("SELECT placa, tipo, entrada, saida FROM movimentacoes WHERE empresa_id = ?", (empresa_id,))
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

# --- Funções de Backup/Sync Excel (CSV) ---


def get_backup_file_path():
    """Retorna o caminho absoluto do arquivo CSV na pasta do projeto."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "usuarios_backup.csv")


def exportar_usuarios_para_csv():
    """Reescreve o arquivo CSV com todos os usuários atuais do banco."""
    arquivo = get_backup_file_path()
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, role FROM usuarios")
            users = cursor.fetchall()

        with open(arquivo, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(["Data", "Acao", "Login", "Senha", "Cargo"])

            data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            for row in users:
                writer.writerow(
                    [data_hora, "SINC_AUTO", row[0], "MANTIDA", row[1]])
    except Exception as e:
        print(f"Erro ao exportar CSV: {e}")


def log_usuario_csv(username, password, role, acao):
    """Registra usuários em um arquivo CSV que pode ser aberto no Excel."""
    arquivo = get_backup_file_path()
    existe = os.path.exists(arquivo)

    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    try:
        # Usa ponto e vírgula como separador para o Excel brasileiro reconhecer colunas
        with open(arquivo, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            if not existe:
                writer.writerow(["Data", "Acao", "Login", "Senha", "Cargo"])

            writer.writerow([data_hora, acao, username, password, role])
    except Exception as e:
        print(f"Erro ao salvar log CSV: {e}")


def importar_usuarios_csv():
    """Lê o arquivo CSV e atualiza/cria os usuários no banco de dados."""
    arquivo = get_backup_file_path()
    if not os.path.exists(arquivo):
        return {"erro": "Arquivo usuarios_backup.csv não encontrado."}

    count = 0
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            with open(arquivo, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    user = row.get("Login")  # Antes era "Usuario"
                    pwd = row.get("Senha")
                    role = row.get("Cargo")  # Antes era "Role"

                    if user:
                        # Verifica se usuario existe
                        cursor.execute(
                            "SELECT id FROM usuarios WHERE username = ?", (user,))
                        exists = cursor.fetchone()

                        if exists:
                            if pwd and pwd != "MANTIDA":
                                hash_senha = get_hash_senha(pwd)
                                cursor.execute(
                                    "UPDATE usuarios SET password_hash = ?, role = ? WHERE username = ?", (hash_senha, role, user))
                            else:
                                cursor.execute(
                                    "UPDATE usuarios SET role = ? WHERE username = ?", (role, user))
                        else:
                            if pwd and pwd != "MANTIDA":
                                hash_senha = get_hash_senha(pwd)
                                cursor.execute(
                                    "INSERT INTO usuarios (username, password_hash, role) VALUES (?, ?, ?)", (user, hash_senha, role))
                        count += 1
            conn.commit()
        return {"status": f"Sincronização concluída! {count} registros processados."}
    except Exception as e:
        return {"erro": f"Erro ao importar: {str(e)}"}

def get_system_health():
    """Retorna dados técnicos sobre o servidor e banco de dados."""
    db_path = "estacionamento.db"
    db_size = 0
    if os.path.exists(db_path):
        db_size = os.path.getsize(db_path) / (1024 * 1024) # Tamanho em MB

    # Adicionando monitoramento de recursos de hardware
    try:
        if psutil:
            # Usando um intervalo pequeno para não bloquear a requisição por muito tempo
            cpu_usage = psutil.cpu_percent(interval=0.1)
            ram_info = psutil.virtual_memory()
            ram_usage = ram_info.percent
            disk_info = psutil.disk_usage('/')
            disk_usage = disk_info.percent
        else:
            raise ImportError("psutil não instalado")
    except Exception:
        # Em caso de erro (ex: psutil não instalado), retorna 0
        cpu_usage = 0
        ram_usage = 0
        disk_usage = 0

    return {
        "db_size_mb": round(db_size, 2),
        "db_status": "Conectado" if os.path.exists(db_path) else "Erro",
        "cpu_usage": cpu_usage,
        "ram_usage": ram_usage,
        "disk_usage": disk_usage,
    }

def criar_backup_sistema():
    """Cria um arquivo ZIP com todo o código fonte e banco de dados."""
    pasta_backups = "backups"
    if not os.path.exists(pasta_backups):
        os.makedirs(pasta_backups)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nome_zip = os.path.join(pasta_backups, f"backup_auto_{timestamp}.zip")

    try:
        with zipfile.ZipFile(nome_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Percorre todos os arquivos da pasta atual
            for root, dirs, files in os.walk("."):
                # Ignorar pastas que não queremos no backup
                if 'backups' in root or 'venv' in root or '.git' in root or '__pycache__' in root or 'static' in root:
                    continue
                
                for file in files:
                    # Salvar apenas arquivos relevantes (código, banco, configs)
                    if file.endswith(('.py', '.html', '.css', '.js', '.db', '.json', '.csv', '.txt')):
                        caminho_completo = os.path.join(root, file)
                        zipf.write(caminho_completo, os.path.relpath(caminho_completo, "."))
        
        return {"status": "Backup criado com sucesso!", "arquivo": nome_zip}
    except Exception as e:
        return {"erro": f"Falha no backup: {str(e)}"}
