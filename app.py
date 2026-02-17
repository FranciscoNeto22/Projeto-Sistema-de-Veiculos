# app.py
import os
import subprocess
from fastapi import FastAPI, HTTPException, Form, Request, Depends, Response
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
    update_protocol_status, get_global_last_message_id,
    close_protocols_bulk
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


app = FastAPI(title="API Controle de Veículos")

app.mount("/static", StaticFiles(directory="static"), name="static")

# Rota para ignorar o erro de favicon.ico no navegador e limpar o terminal


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.on_event("startup")
def on_startup():
    # Cria o usuário 'admin' com senha 'admin' no primeiro boot
    setup_usuarios()


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
    return RedirectResponse(url="/app", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")


@app.get("/app")
def main_app(user: str = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/")
    return FileResponse("index.html")

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
    return registrar_entrada(placa, tipo)


@app.post("/saida")
def saida(placa: str, user: str = Depends(get_logged_user)):
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
    return resetar_banco()


@app.post("/cadastro")
def novo_cadastro(dados: CadastroModel, user: str = Depends(get_logged_user)):
    return registrar_cadastro(dados.dict())


@app.put("/cadastro/{cadastro_id}")
def atualizar_cadastro_endpoint(cadastro_id: int, dados: CadastroModel, user: str = Depends(get_logged_user)):
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
    return service_excluir_cadastro(cadastro_id)


@app.get("/estatisticas")
def estatisticas(user: str = Depends(get_logged_user)):
    return obter_estatisticas()

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
    return criar_usuario(dados.username, dados.password, dados.role)

@app.put("/usuarios/{user_id}")
def api_atualizar_usuario(user_id: int, dados: UsuarioModel, request: Request, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role not in ['gerente', 'admin', 'dev']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    # Passamos a senha (pode ser vazia se não for alterar)
    return atualizar_usuario(user_id, dados.username, dados.password, dados.role)


@app.delete("/usuarios/{user_id}")
def api_excluir_usuario(user_id: int, request: Request, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role not in ['gerente', 'admin', 'dev']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return excluir_usuario(user_id)

@app.post("/usuarios/importar")
def api_importar_usuarios(request: Request, user: str = Depends(get_logged_user)):
    role = request.session.get("role")
    if role not in ['gerente', 'admin', 'dev']:
        raise HTTPException(status_code=403, detail="Acesso negado")
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
