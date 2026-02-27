# app.py
from datetime import datetime
import os
import asyncio
import uvicorn
import subprocess
import shutil
import uuid
import time
import urllib.request
from fastapi import FastAPI, HTTPException, Form, Request, Depends, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
# Importar o middleware de sessão
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from services import (
    registrar_entrada, registrar_saida, listar_veiculos, listar_saidas,
    resetar_banco, obter_estatisticas, registrar_cadastro,
    listar_cadastros as service_listar_cadastros,
    excluir_cadastro as service_excluir_cadastro,
    get_cadastro_por_id as service_get_cadastro_por_id,
    atualizar_cadastro as service_atualizar_cadastro,
    setup_usuarios,
    get_usuario,
    verificar_senha,
    criar_usuario,
    listar_usuarios,
    excluir_usuario,
    atualizar_usuario,
    executar_sql_raw,
    salvar_css_personalizado,
    ler_css_personalizado,
    salvar_config_visual,
    ler_config_visual, get_protocols_for_user_history,
    get_open_protocol_for_user, get_messages_by_protocol, save_chat_message,
    create_protocol_and_message, list_protocols,
    get_protocol_by_id,
    set_app_version,
    get_app_version,
    importar_usuarios_csv,
    update_protocol_status,
    get_global_last_message_id, registrar_log, listar_historico,
    gerar_excel_historico, listar_usuarios_do_historico,
    close_protocols_bulk, salvar_arquivo_db, listar_arquivos_db,
    get_arquivo_por_id, excluir_arquivo_db,
    get_system_health, salvar_historico_performance,
    obter_historico_performance, limpar_historico_performance
)


class CadastroModel(BaseModel):
    nome: Optional[str] = None
    data_nascimento: Optional[str] = None
    telefone: Optional[str] = None
    cep: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    cargo: Optional[str] = None
    email: Optional[str] = None
    cpf: Optional[str] = None
    empresa: Optional[str] = None
    placa: Optional[str] = None
    tipo_veiculo: Optional[str] = None


class UsuarioModel(BaseModel):
    username: str
    password: str
    role: str = "operador"  # operador, gerente, admin


class SqlQuery(BaseModel):
    query: str


class ChatMessage(BaseModel):
    texto: str
    protocolo_id: Optional[int] = None  # For dev replies


class BulkCloseRequest(BaseModel):
    ids: list[int]


class CssModel(BaseModel):
    css: str


class VisualConfigModel(BaseModel):
    config: dict


class AppVersionModel(BaseModel):
    version: str
    changelog: str


async def log_performance_periodically():
    """Tarefa de fundo que salva a performance do servidor a cada minuto, 24/7."""
    while True:
        await asyncio.sleep(60)  # Espera 1 minuto
        try:
            health = get_system_health()
            ping_railway = 0
            try:
                start_time = time.time()
                # Tenta conectar em um endpoint leve para medir latência
                urllib.request.urlopen(
                    "https://projeto-sistema-de-veiculos-production.up.railway.app/app-version", timeout=5)
                ping_railway = int((time.time() - start_time) * 1000)
            except Exception:
                ping_railway = 0  # Marca como 0 se falhar

            salvar_historico_performance(
                health.get("cpu_usage", 0),
                health.get("ram_usage", 0),
                health.get("disk_usage", 0),
                1,  # Ping local (irrelevante no servidor)
                ping_railway
            )
        except Exception as e:
            # Imprime o erro no console do servidor para debug, mas não para a tarefa
            print(f"ERRO NA TAREFA DE HISTÓRICO: {e}")


app = FastAPI(title="API Controle de Veículos")

if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

if not os.path.exists("uploads"):
    os.makedirs("uploads")

# Rota para ignorar o erro de favicon.ico no navegador e limpar o terminal


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

START_TIME = datetime.now()


@app.on_event("startup")
def on_startup():
    # Cria o usuário 'admin' com senha 'admin' no primeiro boot
    global START_TIME
    START_TIME = datetime.now()
    setup_usuarios()
    # Inicia a tarefa de fundo para coletar dados de performance continuamente
    asyncio.create_task(log_performance_periodically())


# Adicionar o middleware de sessão
# É ESSENCIAL para que o login (request.session) funcione.
# A chave agora vem do ambiente ou usa uma padrão para testes locais
secret_key = os.getenv("SECRET_KEY", "chave-padrao-desenvolvimento-123")

app.add_middleware(SessionMiddleware,
                   secret_key=secret_key)


# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite requisições de qualquer origem
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_current_user(request: Request):
    username = request.session.get("user")
    if not username:
        return None
    return username

# Dependência para exigir login nas rotas da API


async def get_logged_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=401, detail="Você precisa estar logado para realizar esta ação.")
    return user


@app.get("/")
def login_page(request: Request):
    if request.session.get("user"):
        return RedirectResponse(url="/app", status_code=303)
    return FileResponse("login.html")


@app.post("/login")
async def login_form(request: Request, username: str = Form(...), password: str = Form(...)):
    user = get_usuario(username)
    if not user or not verificar_senha(password, user["password_hash"]):
        return RedirectResponse(url="/?error=1", status_code=303)

    request.session["user"] = user["username"]
    request.session["role"] = user["role"] if "role" in user.keys(
    ) else "operador"

    registrar_log(user["username"], "LOGIN", "Acesso ao sistema realizado.")
    
    # Se for vigilante, manda direto para o scanner
    if request.session["role"] == "vigilante":
        return RedirectResponse(url="/scanner", status_code=303)
        
    return RedirectResponse(url="/app", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    user = request.session.get("user", "Desconhecido")
    registrar_log(user, "LOGOUT", "Saída do sistema.")
    request.session.clear()
    return RedirectResponse(url="/")


@app.get("/app")
def main_app(request: Request, user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/")
        
    # Segurança: Se vigilante tentar acessar o app principal, joga de volta pro scanner
    if request.session.get("role") == "vigilante":
        return RedirectResponse(url="/scanner")
        
    # Força o navegador a não usar cache para o app principal, garantindo que as
    # alterações no HTML sejam vistas imediatamente.
    response = FileResponse("index.html", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    })
    return response

# Rota para o frontend saber quem é o usuário logado e suas permissões


@app.get("/me")
def get_me(request: Request):
    user = request.session.get("user")
    role = request.session.get("role")
    if not user:
        return {"authenticated": False}
    return {"authenticated": True, "username": user, "role": role}


@app.post("/entrada")
def entrada(placa: str, tipo: str, user: str = Depends(get_logged_user)):
    res = registrar_entrada(placa, tipo)
    if "status" in res:
        registrar_log(user, "ENTRADA VEÍCULO",
                      f"Placa: {placa} | Tipo: {tipo}")
    return res


@app.post("/saida")
def saida(placa: str, user: str = Depends(get_logged_user)):
    registrar_log(user, "SAÍDA VEÍCULO", f"Placa: {placa}")
    return registrar_saida(placa)


@app.get("/veiculos")
def veiculos(user: str = Depends(get_logged_user)):
    dados = listar_veiculos()
    return [
        {"placa": v[0], "tipo": v[1], "entrada": v[2], "responsavel": v[3]}
        for v in dados
    ]


@app.get("/saidas")
def saidas(user: str = Depends(get_logged_user)):
    dados = listar_saidas()
    return [
        {"placa": v[0], "tipo": v[1], "entrada": v[2],
            "saida": v[3], "responsavel": v[4]}
        for v in dados
    ]


@app.post("/reset")
def reset(user: str = Depends(get_logged_user)):
    registrar_log(user, "RESET BANCO", "Limpou todos os veículos do pátio.")
    return resetar_banco()


@app.post("/cadastro")
def novo_cadastro(dados: CadastroModel, user: str = Depends(get_logged_user)):
    registrar_log(user, "NOVO CADASTRO", f"Nome: {dados.nome}")
    return registrar_cadastro(dados.dict())


@app.put("/cadastro/{cadastro_id}")
def atualizar_cadastro_endpoint(cadastro_id: int, dados: CadastroModel, user: str = Depends(get_logged_user)):
    registrar_log(user, "ATUALIZAR CADASTRO", f"ID: {cadastro_id}")
    return service_atualizar_cadastro(cadastro_id, dados.dict())


@app.get("/cadastros")
def listar_cadastros_endpoint(busca: Optional[str] = None, user: str = Depends(get_logged_user)):
    registros = service_listar_cadastros(busca)
    return [
        {
            "id": r[0], "nome": r[1], "cpf": r[2], "telefone": r[3],
            "email": r[4], "cargo": r[5], "empresa": r[6], "placa": r[7]
        }
        for r in registros
    ]


@app.get("/cadastro/{cadastro_id}")
def get_cadastro_endpoint(cadastro_id: int, user: str = Depends(get_logged_user)):
    cadastro = service_get_cadastro_por_id(cadastro_id)
    if not cadastro:
        raise HTTPException(status_code=404, detail="Cadastro não encontrado")
    return cadastro


@app.delete("/cadastro/{cadastro_id}")
def excluir_cadastro_endpoint(cadastro_id: int, user: str = Depends(get_logged_user)):
    registrar_log(user, "EXCLUIR CADASTRO", f"ID: {cadastro_id}")
    return service_excluir_cadastro(cadastro_id)


@app.get("/estatisticas")
def estatisticas(user: str = Depends(get_logged_user)):
    return obter_estatisticas()

# --- Rotas de Histórico (Logs) ---


@app.get("/api/historico")
def api_get_historico(request: Request, usuario: Optional[str] = None, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role not in ['gerente', 'admin', 'dev']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return listar_historico(usuario)


@app.get("/api/historico/usuarios")
def api_get_historico_usuarios(request: Request, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role not in ['gerente', 'admin', 'dev']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return listar_usuarios_do_historico()


@app.get("/api/historico/exportar")
def api_exportar_historico(request: Request, usuario: Optional[str] = None, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role not in ['gerente', 'admin', 'dev']:
        raise HTTPException(status_code=403, detail="Acesso negado")

    caminho, nome_arquivo = gerar_excel_historico(usuario)

    log_details = f"Exportou histórico de ações para o usuário '{usuario}'." if usuario else "Exportou histórico de ações completo."
    registrar_log(user, "EXPORTAÇÃO", log_details)

    return FileResponse(caminho, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=nome_arquivo)


# --- Rotas de Gestão de Usuários (Apenas Gerente/Admin) ---


@app.get("/usuarios")
def api_listar_usuarios(request: Request, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role not in ['gerente', 'admin', 'dev']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return listar_usuarios()


@app.post("/usuarios")
def novo_usuario(dados: UsuarioModel, request: Request, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role not in ['gerente', 'admin', 'dev']:
        raise HTTPException(
            status_code=403, detail="Apenas gerentes podem criar usuários.")
    registrar_log(user, "CRIAR USUÁRIO",
                  f"Novo user: {dados.username} | Cargo: {dados.role}")
    return criar_usuario(dados.username, dados.password, dados.role)


@app.put("/usuarios/{user_id}")
def api_atualizar_usuario(user_id: int, dados: UsuarioModel, request: Request, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role not in ['gerente', 'admin', 'dev']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    # Passamos a senha (pode ser vazia se não for alterar)
    registrar_log(user, "EDITAR USUÁRIO", f"ID: {user_id}")
    return atualizar_usuario(user_id, dados.username, dados.password, dados.role)


@app.delete("/usuarios/{user_id}")
def api_excluir_usuario(user_id: int, request: Request, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role not in ['gerente', 'admin', 'dev']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    registrar_log(user, "EXCLUIR USUÁRIO", f"ID: {user_id}")
    return excluir_usuario(user_id)


@app.post("/usuarios/importar")
def api_importar_usuarios(request: Request, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role not in ['gerente', 'admin', 'dev']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    registrar_log(user, "IMPORTAR USUÁRIOS", "Via CSV Backup")
    return importar_usuarios_csv()


# --- Rotas do Chat (Nova Lógica com Protocolos) ---


@app.get("/chat/my-protocol")
def get_my_open_protocol(request: Request, user: str = Depends(get_logged_user)):
    """Busca o protocolo aberto do usuário logado e suas mensagens."""
    protocol = get_open_protocol_for_user(user)
    if not protocol:
        return {"protocolo_id": None, "messages": []}

    messages = get_messages_by_protocol(protocol['id'])
    return {"protocolo_id": protocol['id'], "messages": messages, "status": protocol['status']}


@app.post("/chat/send-message")
def send_chat_message(dados: ChatMessage, request: Request, user: str = Depends(get_logged_user)):
    """Envia uma mensagem. Cria um protocolo se não existir."""
    try:
        role = request.session.get("role")

        # Se vier um ID de protocolo (resposta do dev ou continuação), usa ele
        if dados.protocolo_id:
            return save_chat_message(dados.protocolo_id, user, dados.texto)

        # Se não vier ID, busca um aberto (para clientes) ou cria novo
        open_protocol = get_open_protocol_for_user(user)
        if open_protocol:
            return save_chat_message(open_protocol['id'], user, dados.texto)
        else:
            return create_protocol_and_message(user, dados.texto)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

# --- Rotas de Chat para DEV/Admin ---


@app.get("/chat/protocols")
def get_all_protocols(request: Request, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role not in ['dev', 'admin']:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    return list_protocols()


@app.get("/chat/protocols/{protocol_id}")
def get_protocol_messages(protocol_id: int, request: Request, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role not in ['dev', 'admin']:
        raise HTTPException(status_code=403, detail="Acesso negado.")

    messages = get_messages_by_protocol(protocol_id)

    proto = get_protocol_by_id(protocol_id)
    status = proto['status'] if proto else 'aberto'

    return {"protocolo_id": protocol_id, "messages": messages, "status": status}


@app.post("/chat/protocol/{protocol_id}/close")
def close_protocol_endpoint(protocol_id: int, request: Request, user: str = Depends(get_logged_user)):
    """Encerra o atendimento e solicita avaliação (Apenas Admin/Dev)."""
    role = request.session.get("role")
    # Garante que cliente não possa encerrar
    if role not in ['dev', 'admin', 'gerente']:
        raise HTTPException(
            status_code=403, detail="Apenas suporte pode encerrar.")

    update_protocol_status(protocol_id, 'avaliando')
    return {"status": "Protocolo enviado para avaliação"}


@app.post("/chat/protocol/{protocol_id}/rate")
def rate_protocol_endpoint(protocol_id: int, dados: dict, request: Request, user: str = Depends(get_logged_user)):
    """Recebe a avaliação do cliente e fecha o protocolo."""
    # Aqui você poderia salvar a nota no banco se tivesse a coluna, por enquanto apenas fecha.
    update_protocol_status(protocol_id, 'fechado')
    return {"status": "Avaliação recebida e protocolo fechado."}


@app.post("/chat/protocols/bulk-close")
def bulk_close_endpoint(dados: BulkCloseRequest, request: Request, user: str = Depends(get_logged_user)):
    """Encerra múltiplos protocolos selecionados (Brute-force)."""
    role = request.session.get("role")
    if role not in ['dev', 'admin']:
        raise HTTPException(status_code=403, detail="Acesso negado.")

    result = close_protocols_bulk(dados.ids)
    return {"status": f"{result['count']} protocolos encerrados."}


# --- Rotas de Arquivos (Nuvem) ---

@app.post("/api/arquivos/upload")
async def upload_arquivo(file: UploadFile = File(...), user: str = Depends(get_logged_user)):
    try:
        # Gera nome único para não sobrescrever
        extensao = os.path.splitext(file.filename)[1]
        nome_fisico = f"{uuid.uuid4()}{extensao}"
        caminho_completo = os.path.join("uploads", nome_fisico)

        # Salva no disco
        with open(caminho_completo, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Calcula tamanho legível
        tamanho_bytes = os.path.getsize(caminho_completo)
        if tamanho_bytes < 1024:
            tamanho_str = f"{tamanho_bytes} B"
        elif tamanho_bytes < 1024 * 1024:
            tamanho_str = f"{round(tamanho_bytes/1024, 1)} KB"
        else:
            tamanho_str = f"{round(tamanho_bytes/(1024*1024), 1)} MB"

        salvar_arquivo_db(file.filename, nome_fisico, tamanho_str, user)
        registrar_log(user, "UPLOAD ARQUIVO", f"Arquivo: {file.filename}")

        return {"status": "Upload realizado com sucesso!"}
    except Exception as e:
        return {"erro": str(e)}


@app.get("/api/arquivos")
def api_listar_arquivos(user: str = Depends(get_logged_user)):
    return listar_arquivos_db()


@app.get("/api/arquivos/download/{arquivo_id}")
def download_arquivo(arquivo_id: int, user: str = Depends(get_logged_user)):
    arquivo = get_arquivo_por_id(arquivo_id)
    if not arquivo:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    caminho = os.path.join("uploads", arquivo['caminho_salvo'])
    if not os.path.exists(caminho):
        raise HTTPException(
            status_code=404, detail="Arquivo físico não encontrado no servidor")

    return FileResponse(caminho, filename=arquivo['nome_original'])


@app.delete("/api/arquivos/{arquivo_id}")
def delete_arquivo(arquivo_id: int, request: Request, user: str = Depends(get_logged_user)):
    arquivo = get_arquivo_por_id(arquivo_id)
    if not arquivo:
        return {"erro": "Arquivo não encontrado"}

    # Remove do disco
    caminho = os.path.join("uploads", arquivo['caminho_salvo'])
    if os.path.exists(caminho):
        os.remove(caminho)

    excluir_arquivo_db(arquivo_id)
    registrar_log(user, "EXCLUIR ARQUIVO", f"ID: {arquivo_id}")
    return {"status": "Arquivo excluído"}


@app.get("/chat/last-message-id")
def get_last_msg_id(user: str = Depends(get_logged_user)):
    """Retorna o ID da última mensagem para notificação."""
    return {"id": get_global_last_message_id()}


@app.get("/chat/my-history")
def get_my_protocol_history(request: Request, user: str = Depends(get_logged_user)):
    """Busca o histórico de protocolos do usuário logado."""
    return get_protocols_for_user_history(user)

# --- Rotas de Layout Dinâmico (Apenas DEV) ---


@app.get("/config/css")
def get_custom_css():
    # Aberto para todos lerem (para o cliente ver o design novo)
    return {"css": ler_css_personalizado()}


@app.post("/config/css")
def post_custom_css(dados: CssModel, request: Request, user: str = Depends(get_logged_user)):
    # Apenas o DEV pode salvar alterações de layout
    role = request.session.get("role")
    if role != 'dev':
        raise HTTPException(
            status_code=403, detail="Apenas o desenvolvedor pode alterar o layout do sistema.")
    return salvar_css_personalizado(dados.css)

# --- Rotas de Configuração Visual (No-Code) ---


@app.get("/config/visual")
def get_visual_config():
    return ler_config_visual()


@app.post("/config/visual")
def post_visual_config(dados: VisualConfigModel, request: Request, user: str = Depends(get_logged_user)):
    # Apenas DEV pode salvar
    role = request.session.get("role")
    if role != 'dev':
        raise HTTPException(status_code=403, detail="Acesso negado.")
    return salvar_config_visual(dados.config)

# --- Rotas de Versionamento do App (Apenas DEV) ---


@app.get("/app-version")
def app_version():
    return get_app_version()


@app.post("/dev/publish-update")
def publish_update(dados: AppVersionModel, request: Request, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role != 'dev':
        raise HTTPException(
            status_code=403, detail="Apenas o desenvolvedor pode publicar atualizações.")
    return set_app_version(dados.version, dados.changelog)

# --- Rota de Auto-Atualização (Git Pull) ---


@app.post("/system/git-pull")
def git_pull_system(user: str = Depends(get_logged_user)):
    """Executa um reset forçado para atualizar o código com a versão do GitHub."""
    try:
        # 1. Busca as últimas informações do repositório remoto.
        subprocess.check_output(
            ["git", "fetch"], shell=True, stderr=subprocess.STDOUT)

        # 2. Tenta fazer o reset para o branch 'main'.
        result = subprocess.check_output(
            ["git", "reset", "--hard", "origin/main"], shell=True, stderr=subprocess.STDOUT)
        log_message = result.decode('utf-8')
        return {"status": "Sistema atualizado com sucesso!", "log": log_message}
    except subprocess.CalledProcessError as e:
        # Se falhar com 'main', tenta com 'master' como alternativa.
        try:
            result = subprocess.check_output(
                ["git", "reset", "--hard", "origin/master"], shell=True, stderr=subprocess.STDOUT)
            log_message = result.decode('utf-8')
            return {"status": "Sistema atualizado com sucesso (usando branch 'master')!", "log": log_message}
        except subprocess.CalledProcessError as e2:
            error_output = e2.output.decode('utf-8')
            return {"erro": f"Falha ao atualizar. Não foi possível encontrar 'origin/main' ou 'origin/master'. Detalhes: {error_output}"}
    except Exception as e:
        return {"erro": f"Erro inesperado durante a atualização: {str(e)}"}

# --- Rota do Painel do Desenvolvedor ---


@app.get("/dev")
def dev_panel(request: Request, user: str = Depends(get_current_user)):
    # Primeiro, verifica se o usuário está logado
    if not user:
        return RedirectResponse(url="/")
    # Proteção extra: apenas o usuário 'admin' pode acessar essa tela
    # Agora permitimos 'admin' e 'dev' acessarem, mas o dev tem mais poderes no index
    role = request.session.get("role")
    if role not in ["admin", "dev"]:
        return RedirectResponse(url="/app")
    return FileResponse("dev.html")


@app.post("/dev/sql")
def run_sql(dados: SqlQuery, request: Request, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role not in ["admin", "dev"]:
        raise HTTPException(
            status_code=403, detail="Acesso negado. Apenas admin.")
    return executar_sql_raw(dados.query)

# --- Rota do APP de Monitoramento (Mobile PWA) ---


@app.get("/monitor")
def monitor_panel(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/")

    role = request.session.get("role")
    if role not in ["admin", "dev"]:
        return RedirectResponse(url="/app")

    # Força o navegador a não usar cache para o monitor
    response = FileResponse("monitor.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# --- Rota do Scanner (Vigilante) ---
@app.get("/scanner")
def scanner_interface(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/")
    return FileResponse("scanner.html")


# Variável global para controlar a frequência de salvamento no banco (evitar spam)
# LAST_DB_SAVE = 0 # REMOVIDO: A tarefa de fundo agora controla isso.
LAST_NET_IO = None
LAST_NET_TIME = None


@app.get("/api/monitor/history")
def api_monitor_history(date: str, user: str = Depends(get_logged_user)):
    """Retorna o histórico de performance para uma data específica (YYYY-MM-DD)."""
    return obter_historico_performance(date)


@app.post("/api/monitor/history/clear")
def api_clear_monitor_history(user: str = Depends(get_logged_user)):
    """Limpa o histórico de performance."""
    role = get_usuario(user)['role']
    if role not in ['admin', 'dev']:
        raise HTTPException(
            status_code=403, detail="Apenas admin/dev pode limpar histórico.")
    return limpar_historico_performance()


@app.get("/api/server-status")
def api_server_status(user: str = Depends(get_logged_user)):
    global LAST_NET_IO, LAST_NET_TIME
    # Calcula tempo de atividade (Uptime)
    now = datetime.now()
    uptime = now - START_TIME

    # Dados do sistema
    health = get_system_health()

    # Medir Ping do Railway (Backend side)
    ping_railway = 0
    try:
        start = time.time()
        # Tenta conectar na raiz ou em um endpoint leve
        urllib.request.urlopen(
            "https://projeto-sistema-de-veiculos-production.up.railway.app/app-version", timeout=2)
        ping_railway = int((time.time() - start) * 1000)
    except:
        ping_railway = 0  # Offline ou timeout

    # --- Novos Recursos: Rede e Processos ---
    upload_speed = 0
    download_speed = 0
    top_processes = []

    # Verifica se psutil está disponível (importado no topo ou services)
    # Como services.py importa psutil, podemos tentar usar aqui se estiver no escopo ou reimportar
    try:
        import psutil
        # Cálculo de Velocidade de Rede
        net_io = psutil.net_io_counters()
        current_time = time.time()
        if LAST_NET_IO and LAST_NET_TIME:
            time_delta = current_time - LAST_NET_TIME
            if time_delta > 0:
                upload_speed = (net_io.bytes_sent -
                                LAST_NET_IO.bytes_sent) / time_delta
                download_speed = (net_io.bytes_recv -
                                  LAST_NET_IO.bytes_recv) / time_delta
        LAST_NET_IO = net_io
        LAST_NET_TIME = current_time

        # Top 5 Processos por Memória
        for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
            try:
                top_processes.append(proc.info)
            except:
                pass
        top_processes = sorted(
            top_processes, key=lambda p: p['memory_percent'], reverse=True)[:5]
    except:
        pass

    # O bloco de salvamento de histórico foi removido daqui e movido para a tarefa
    # em segundo plano (log_performance_periodically) para garantir coleta contínua.
    return {
        "uptime": str(uptime).split('.')[0],  # Remove milissegundos
        "db_size": f"{health['db_size_mb']} MB",
        "db_status": health['db_status'],
        "server_time": now.strftime("%H:%M:%S"),
        "cpu_usage": health.get("cpu_usage", 0),
        "ram_usage": health.get("ram_usage", 0),
        "disk_usage": health.get("disk_usage", 0),
        "railway_ping_backend": ping_railway,
        "net_upload_kb": round(upload_speed / 1024, 1),
        "net_download_kb": round(download_speed / 1024, 1),
        "top_processes": top_processes
    }


if __name__ == "__main__":
    # Permite acesso externo (celular) na porta 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
