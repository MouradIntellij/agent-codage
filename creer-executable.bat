@echo off
chcp 65001 >nul
title Creation de l'executable Codeur
cd /d "%~dp0"

echo ============================================
echo  Creation de l'executable Codeur.exe
echo  (a lancer uniquement sur la machine de
echo   l'enseignant, pas chez les etudiants)
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERREUR] Python est introuvable sur ce poste.
  echo           Installez Python depuis python.org puis relancez ce script.
  pause
  exit /b 1
)

python -m pip show pyinstaller >nul 2>nul
if errorlevel 1 (
  echo Installation de PyInstaller en cours...
  python -m pip install pyinstaller
  if errorlevel 1 (
    echo [ERREUR] Impossible d'installer PyInstaller.
    pause
    exit /b 1
  )
)

echo.
echo Nettoyage des anciens resultats...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Construction en cours, patientez une a deux minutes...
python -m PyInstaller --onefile --console --name Codeur --icon "%~dp0codeur.ico" --add-data "%~dp0public;public" --distpath dist --workpath build --specpath build demarrer.py
if errorlevel 1 (
  echo [ERREUR] La construction a echoue.
  pause
  exit /b 1
)

copy /y "Lisezmoi.txt" "dist\Lisezmoi.txt" >nul

echo Creation du paquet pour les etudiants...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\Codeur.exe','dist\Lisezmoi.txt' -DestinationPath 'Codeur-etudiant.zip' -Force"

echo.
echo ============================================
echo  Termine :
echo    - dist\Codeur.exe       executable seul
echo    - Codeur-etudiant.zip   paquet a distribuer
echo ============================================
pause
