import os
import sys
import subprocess
import time


def install(package):
    print(f"📦 Instalando {package}...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package])
        print(f"✅ {package} OK.")
    except:
        print(
            f"❌ Erro ao instalar {package}. Tente manualmente: pip install {package}")


def main():
    print("--- 🛠️ INICIANDO REPARO DO SISTEMA ---")

    # 1. Apagar arquivos que causam erro no VS Code
    arquivos_lixo = [
        "filename",
        "filename.css",
        "monitor.html.txt",
        "monitor.txt",
        "static/manifest.json.txt"
    ]

    cwd = os.getcwd()
    print(f"📂 Pasta do projeto: {cwd}")

    for arquivo in arquivos_lixo:
        caminho = os.path.join(cwd, arquivo)
        if os.path.exists(caminho):
            try:
                os.remove(caminho)
                print(f"🗑️ Removido arquivo problemático: {arquivo}")
            except Exception as e:
                print(f"⚠️ Não foi possível remover {arquivo}: {e}")
        else:
            print(f"ℹ️ Arquivo {arquivo} já não existe (limpo).")

    # 2. Instalar dependências obrigatórias
    print("\n--- 📦 VERIFICANDO BIBLIOTECAS ---")
    libs = ["fastapi", "uvicorn", "bcrypt", "pytz", "httpx", "psutil",
            "pandas", "openpyxl", "itsdangerous", "python-multipart"]

    for lib in libs:
        try:
            __import__(lib)
            print(f"✅ {lib} já instalado.")
        except ImportError:
            install(lib)

    print("\n--- ✅ CONCLUÍDO ---")
    print("1. O arquivo 'filename' foi apagado (os erros vermelhos devem sumir).")
    print("2. As bibliotecas foram instaladas.")
    print("3. Tente rodar o servidor agora: python app.py")
    print("4. No navegador, dê um REFRESH FORÇADO (Ctrl + F5) para carregar o menu corrigido.")

    time.sleep(5)


if __name__ == "__main__":
    main()
