# services.py
import sqlite3
from datetime import datetime
from typing import Optional
import bcrypt
import json


def get_db_connection():
    return sqlite3.connect("estacionamento.db", timeout=10, check_same_thread=False)


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


def listar_saidas():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT placa, tipo, entrada, saida, responsavel, cpf_responsavel
            FROM movimentacoes
            WHERE saida IS NOT NULL
            ORDER BY id DESC
        """)
        return cursor.fetchall()


def resetar_banco():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movimentacoes")
    return {"status": "banco de dados resetado com sucesso"}


def registrar_cadastro(dados):
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
                tipo_veiculo TEXT
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
            INSERT INTO cadastros (nome, data_nascimento, telefone, cep, endereco, numero, cargo, email, cpf, empresa, placa, tipo_veiculo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (dados.get('nome'), dados.get('data_nascimento'), dados.get('telefone'),
              dados.get('cep'), dados.get('endereco'), dados.get('numero'),
              dados.get('cargo'), dados.get('email'), dados.get('cpf'),
              dados.get('empresa'), dados.get('placa'), dados.get('tipo_veiculo')))

    # Registrar entrada automaticamente se houver placa informada
    if dados.get('placa'):
        tipo = dados.get('tipo_veiculo') if dados.get(
            'tipo_veiculo') else "Carro"
        registrar_entrada(dados.get('placa'), tipo,
                          dados.get('nome'), dados.get('cpf'))

    return {"status": "Cadastro realizado com sucesso!"}


def listar_cadastros(busca: Optional[str] = None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Garante que a tabela exista antes de consultar
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cadastros (
                id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, data_nascimento TEXT, telefone TEXT, cep TEXT,
                endereco TEXT, numero TEXT, cargo TEXT, email TEXT, cpf TEXT,
                empresa TEXT, placa TEXT, tipo_veiculo TEXT
            )
        """)

        if busca:
            query = """
                SELECT id, nome, cpf, telefone, email, cargo, empresa, placa
                FROM cadastros
                WHERE nome LIKE ? OR placa LIKE ?
                ORDER BY nome
            """
            params = (f"%{busca}%", f"%{busca}%")
            cursor.execute(query, params)
        else:
            query = """
                SELECT id, nome, cpf, telefone, email, cargo, empresa, placa
                FROM cadastros
                ORDER BY nome
            """
            cursor.execute(query)

        return cursor.fetchall()


def excluir_cadastro(cadastro_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cadastros WHERE id = ?", (cadastro_id,))
        if cursor.rowcount == 0:
            return {"erro": "Cadastro não encontrado."}
    return {"status": "Cadastro excluído com sucesso!"}


def get_cadastro_por_id(cadastro_id: int):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cadastros WHERE id = ?", (cadastro_id,))
        cadastro = cursor.fetchone()
        return cadastro


def atualizar_cadastro(cadastro_id: int, dados):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE cadastros SET
                nome = ?, data_nascimento = ?, telefone = ?, cep = ?, endereco = ?,
                numero = ?, cargo = ?, email = ?, cpf = ?, empresa = ?, placa = ?, tipo_veiculo = ?
            WHERE id = ?
        """, (
            dados.get('nome'), dados.get(
                'data_nascimento'), dados.get('telefone'),
            dados.get('cep'), dados.get('endereco'), dados.get('numero'),
            dados.get('cargo'), dados.get('email'), dados.get('cpf'),
            dados.get('empresa'), dados.get(
                'placa'), dados.get('tipo_veiculo'),
            cadastro_id
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
                role TEXT DEFAULT 'operador'
            )
        """)

        # Migração: Adicionar coluna role se não existir
        cursor.execute("PRAGMA table_info(usuarios)")
        cols = [r[1] for r in cursor.fetchall()]
        if 'role' not in cols:
            cursor.execute(
                "ALTER TABLE usuarios ADD COLUMN role TEXT DEFAULT 'operador'")
            # Atualiza o admin para ter permissão total
            cursor.execute(
                "UPDATE usuarios SET role = 'admin' WHERE username = 'admin'")

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
                status TEXT NOT NULL DEFAULT 'aberto' -- aberto, fechado
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
                FOREIGN KEY (protocolo_id) REFERENCES chat_protocolos (id)
            )
        """)

        # Criar usuário padrão se não existir
        cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
        if not cursor.fetchone():
            admin_pass_hash = get_hash_senha("admin")
            cursor.execute(
                "INSERT INTO usuarios (username, password_hash, role) VALUES (?, ?, ?)", ('admin', admin_pass_hash, 'admin'))

        # Criar usuário DEV (Dono) se não existir
        cursor.execute(
            "SELECT id FROM usuarios WHERE username = 'neto@dev.com'")
        if not cursor.fetchone():
            # Senha solicitada: 126918dev#@
            dev_pass_hash = get_hash_senha("126918dev#@")
            cursor.execute(
                "INSERT INTO usuarios (username, password_hash, role) VALUES (?, ?, ?)", ('neto@dev.com', dev_pass_hash, 'dev'))


def criar_usuario(username, password, role='operador'):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            hash_senha = get_hash_senha(password)
            cursor.execute(
                "INSERT INTO usuarios (username, password_hash, role) VALUES (?, ?, ?)", (username, hash_senha, role))
            return {"status": "Usuário criado com sucesso!"}
        except sqlite3.IntegrityError:
            return {"erro": "Nome de usuário já existe."}


def listar_usuarios():
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, role FROM usuarios WHERE username NOT IN ('admin', 'neto@dev.com') ORDER BY username")
        return [dict(row) for row in cursor.fetchall()]


def excluir_usuario(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Proteção para não excluir o admin principal (id 1 ou nome admin)
        cursor.execute(
            "SELECT username FROM usuarios WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        if user and user[0] == 'admin':
            return {"erro": "Não é possível excluir o superusuário admin."}

        cursor.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
        return {"status": "Usuário excluído."}


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


def get_usuario(username: str):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM usuarios WHERE username = ?", (username,))
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


def get_open_protocol_for_user(username):
    """Encontra um protocolo aberto para um usuário específico."""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM chat_protocolos WHERE usuario_cliente = ? AND status IN ('aberto', 'avaliando') ORDER BY id DESC LIMIT 1",
            (username,)
        )
        return cursor.fetchone()


def get_protocol_by_id(protocol_id):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chat_protocolos WHERE id = ?", (protocol_id,))
        return cursor.fetchone()


def get_messages_by_protocol(protocolo_id):
    """Lista todas as mensagens de um protocolo específico."""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM chat_mensagens WHERE protocolo_id = ? ORDER BY id ASC",
            (protocolo_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def save_chat_message(protocolo_id, usuario, texto):
    """Salva uma nova mensagem em um protocolo existente."""
    data_hora = datetime.now().strftime("%d/%m %H:%M")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_mensagens (protocolo_id, usuario, texto, data_hora) VALUES (?, ?, ?, ?)",
            (protocolo_id, usuario, texto, data_hora)
        )
        conn.commit()
    return {"status": "Mensagem enviada", "protocolo_id": protocolo_id}


def create_protocol_and_message(usuario, texto):
    """Cria um novo protocolo e adiciona a primeira mensagem."""
    data_hora = datetime.now().strftime("%d/%m %H:%M")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # 1. Criar o protocolo
        assunto = texto[:50] + '...' if len(texto) > 50 else texto
        cursor.execute(
            "INSERT INTO chat_protocolos (usuario_cliente, assunto, data_inicio, status) VALUES (?, ?, ?, 'aberto')",
            (usuario, assunto, data_hora)
        )
        protocolo_id = cursor.lastrowid

        # 2. Inserir a primeira mensagem
        cursor.execute(
            "INSERT INTO chat_mensagens (protocolo_id, usuario, texto, data_hora) VALUES (?, ?, ?, ?)",
            (protocolo_id, usuario, texto, data_hora)
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


def get_protocols_for_user_history(username):
    """Lista todos os protocolos de um usuário (abertos e fechados)."""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, assunto, data_inicio, status FROM chat_protocolos WHERE usuario_cliente = ? ORDER BY id DESC",
            (username,)
        )
        return [dict(row) for row in cursor.fetchall()]

def update_protocol_status(protocol_id, status):
    """Atualiza o status de um protocolo (ex: 'avaliando', 'fechado')."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chat_protocolos SET status = ? WHERE id = ?", (status, protocol_id))
        conn.commit()
    return {"status": "updated"}

def close_protocols_bulk(protocol_ids):
    """Encerra múltiplos protocolos de uma vez (sem avaliação)."""
    if not protocol_ids:
        return {"count": 0}
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in protocol_ids)
        sql = f"UPDATE chat_protocolos SET status = 'fechado' WHERE id IN ({placeholders})"
        cursor.execute(sql, protocol_ids)
        conn.commit()
        return {"count": cursor.rowcount}

def get_global_last_message_id():
    """Retorna o ID da última mensagem do sistema para verificação de notificações globais."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(id) FROM chat_mensagens")
        row = cursor.fetchone()
        return row[0] if row and row[0] else 0

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
