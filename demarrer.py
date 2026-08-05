"""Codeur.exe — point d'entrée de l'exécutable autonome.

Vérifie qu'Ollama tourne (le lance sinon), démarre le serveur web et ouvre
le navigateur. Construit avec PyInstaller : tout Python est embarqué, le poste
de l'étudiant n'a besoin que d'Ollama + un modèle local (déjà installés par
installer.bat, ou voir la console ici).

Variables utiles :
  CODEUR_NO_BROWSER=1   n'ouvre pas le navigateur (tests / serveur seul)
"""

import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

import web  # importe aussi config, agent, llm, tools


def ollama_ok() -> bool:
    try:
        urllib.request.urlopen("http://127.0.0.1:11434", timeout=2).close()
        return True
    except Exception:
        return False


def ensure_ollama() -> bool:
    """Ollama doit répondre. S'il est installé mais pas lancé, on le démarre."""
    if ollama_ok():
        return True
    print("[Ollama] ne repond pas sur http://127.0.0.1:11434")
    try:
        probe = subprocess.run(["where", "ollama"], capture_output=True, text=True)
    except Exception:
        probe = None
    if probe is not None and probe.returncode == 0:
        print("[Ollama] demarrage en arriere-plan...")
        subprocess.Popen(["ollama", "serve"],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for _ in range(40):
            time.sleep(1)
            if ollama_ok():
                return True
    print("[Ollama] introuvable ou indisponible.")
    print("         Installez Ollama depuis ollama.com puis tirez un modele :")
    print("         ollama pull llama3.2:latest")
    return False


def main() -> None:
    print("=" * 58)
    print("  Codeur - agent IA de codage local, pret a l'emploi")
    print("=" * 58)
    if not ensure_ollama():
        input("\nAppuyez sur Entree pour quitter...")
        sys.exit(1)

    print("\nDemarrage du serveur web...")
    thread = threading.Thread(target=web.main, daemon=True)
    thread.start()
    time.sleep(2.5)
    if os.environ.get("CODEUR_NO_BROWSER") != "1":
        webbrowser.open("http://127.0.0.1:3000")
    print("  Page de chat : http://127.0.0.1:3000")
    print("  Fermez cette fenetre pour arreter l'agent.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nArret.")


if __name__ == "__main__":
    main()
