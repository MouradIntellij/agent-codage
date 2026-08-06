@echo off
chcp 65001 >nul
title Codeur - Installation
echo ============================================================
echo   Codeur - Installation sur ce poste, a faire UNE SEULE fois
echo ============================================================
echo.
cd /d "%~dp0"

where python >nul 2>&1
if not errorlevel 1 goto python_ok
echo [ERREUR] Python introuvable.
echo Installez Python depuis python.org en cochant Add to PATH.
echo Puis relancez ce script.
pause
exit /b 1
:python_ok

where ollama >nul 2>&1
if not errorlevel 1 goto ollama_ok
echo [ERREUR] Ollama introuvable.
echo Installez Ollama depuis ollama.com - gratuit, fonctionne ensuite sans Internet.
pause
exit /b 1
:ollama_ok

echo [1/3] Verification du modele local qwen2.5...
ollama list | findstr /i "qwen2.5" >nul
if not errorlevel 1 goto modele_ok
echo [INFO] Modele absent : telechargement 2 Go, Internet requis une seule fois.
ollama pull qwen2.5:latest
:modele_ok

echo [2/3] Installation de la dependance Python requests...
python -m pip install requests

echo [3/3] Installation terminee.
echo.
echo Pour lancer l'agent : double-cliquez sur demarrer-agent.bat
echo Aucun Internet necessaire pour l'utilisation.
pause
