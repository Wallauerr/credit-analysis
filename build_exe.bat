@echo off
REM ============================================================
REM  Generate the standalone EXE with PyInstaller
REM  (run ONCE on Windows; the EXE already includes all libraries)
REM ============================================================
title Gerador de Executavel (Analise de Credito)
chcp 65001 >nul

echo.
echo  Gerando o executavel "Analise de Credito.exe"...
echo  Todos os recursos ficarao embutidos no arquivo.
echo.

python -m pip install -r requirements.txt
pip install pyinstaller
python -m PyInstaller --clean --noconfirm app.spec

echo.
if exist "dist\Analise de Credito.exe" (
    echo  Sucesso! O executavel foi criado em:
    echo    dist\Analise de Credito.exe
    echo.
    echo  Para distribuir, basta enviar esse arquivo.
    echo  O destino "dist\Analise de Credito" e uma pasta,
    echo  mas o arquivo .exe dentro dela e o standalone.
) else (
    echo  Erro: arquivo nao encontrado. Veja o log acima.
)

echo.
pause
