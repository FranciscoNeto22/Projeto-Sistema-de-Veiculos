@echo off
cls
echo =================================================
echo   FINALIZANDO SERVIDORES ANTIGOS (PORTA 8000)
echo =================================================
FOR /F "tokens=5" %%P IN ('netstat -a -n -o ^| findstr ":8000"') DO (
    IF "%%P" NEQ "0" (
        echo Matando processo com PID %%P...
        taskkill /F /PID %%P >nul 2>&1
    )
)
echo.
echo ==========================================
echo   INICIANDO SERVIDOR PARA ACESSO CELULAR
echo ==========================================
echo.
echo INSTALANDO/VERIFICANDO DEPENDENCIAS (pode levar um minuto na primeira vez)...
py -m pip install -r requirements.txt
echo.
echo SEU ENDERECO IP (Tente os que aparecem abaixo):
ipconfig | findstr /i "IPv4"
echo.
echo TENTANDO LIBERAR FIREWALL AUTOMATICAMENTE...
netsh advfirewall firewall add rule name="AutoGate Server" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1
if %errorLevel% == 0 (
    echo [SUCESSO] Porta 8000 liberada!
) else (
    echo [AVISO] Nao foi possivel liberar o firewall automaticamente.
    echo         Se nao conectar, feche e execute este arquivo como ADMINISTRADOR.
)
echo.
echo ACESSE NO CELULAR: http://SEU_IP_ACIMA:8000
echo.
py -m uvicorn app:app --host 0.0.0.0 --port 8000
pause