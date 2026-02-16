@echo off
echo --- Atualizando Repositorio Git ---
git add .

set /p msg="Digite a mensagem da atualizacao (ou aperte Enter para padrao): "
if "%msg%"=="" set msg=Atualizacao automatica do sistema

git commit -m "%msg%"
git push
echo.
echo --- Enviado com sucesso! ---
pause