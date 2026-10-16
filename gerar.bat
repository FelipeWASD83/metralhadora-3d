@echo off
rem Gera a metralhadora em modelo\ (blend, glb, obj) e as imagens em render\ com o Blender instalado.
rem Use "gerar.bat --sem-render" para pular as imagens (leva uns segundos em vez de minutos).
setlocal
set "BLENDER="
for /d %%D in ("C:\Program Files\Blender Foundation\Blender *") do (
    if exist "%%D\blender.exe" set "BLENDER=%%D\blender.exe"
)
if not defined BLENDER (
    echo Blender nao encontrado em "C:\Program Files\Blender Foundation".
    pause
    exit /b 1
)
echo Usando %BLENDER%
"%BLENDER%" -b --factory-startup --python "%~dp0gerar.py" -- %*
echo.
chcp 65001 >nul
type "%~dp0modelo\relatorio.txt"
pause
