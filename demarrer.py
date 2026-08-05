"""Codeur.exe — point d'entrée de l'exécutable autonome.

Comportement (l'ordre compte, tout est détecté, jamais réinstallé) :
  1. Ollama est-il déjà installé ? Non  -> télécharge OllamaSetup.exe
     (officiel, une seule fois) et l'installe en silence (sans admin).
  2. Ollama répond-il ? Non -> on le démarre.
  3. Le modèle existe-t-il ? Non -> ollama pull (une seule fois).
  4. Le raccourci bureau "Codeur" existe-t-il ? Non -> on le crée.
  5. Serveur web + navigateur.

Ensuite, chaque double-clic sur l'icône est rapide : les vérifications
ci-dessus prennent moins d'une seconde une fois tout installé.

Variables utiles :
  CODEUR_NO_BROWSER=1   n'ouvre pas le navigateur (tests / serveur seul)
"""

import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser

import web

MODEL = "llama3.2:latest"
OLLAMA_URL = "https://ollama.com/download/OllamaSetup.exe"
OLLAMA_EXE = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "Programs", "Ollama", "ollama.exe",
)
SHORTCUT_NAME = "Codeur.lnk"
MIN_INSTALLER_SIZE = 500 * 1048576  # réutiliser un téléchargement déjà complet


def ollama_running() -> bool:
    try:
        urllib.request.urlopen("http://127.0.0.1:11434", timeout=2).close()
        return True
    except Exception:
        return False


def ollama_installed() -> bool:
    if os.path.exists(OLLAMA_EXE):
        return True
    try:
        r = subprocess.run(["where", "ollama"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _ollama_cmd() -> str:
    if os.path.exists(OLLAMA_EXE):
        return OLLAMA_EXE
    return "ollama"


def start_ollama() -> bool:
    print("[Ollama] demarrage du moteur...")
    try:
        subprocess.Popen([_ollama_cmd(), "serve"],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e:
        print(f"[Erreur] demarrage Ollama : {e}")
        return False
    for _ in range(60):
        if ollama_running():
            return True
        time.sleep(1)
    return False


def _download(url: str, dest: str, label: str) -> bool:
    print(f"[Telechargement] {label} (Internet requis, une seule fois)")
    tmp = dest + ".part"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Codeur-agent/1.0"})
        with urllib.request.urlopen(req, timeout=60) as src:
            length = int(src.headers.get("Content-Length") or 0)
            done = 0
            last_pct = -1
            last_print = time.time()
            with open(tmp, "wb") as out:
                while True:
                    chunk = src.read(262144)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if length:
                        pct = int(done * 100 // length)
                        if pct >= last_pct + 5 or pct == 100:
                            print(f"  {pct:3d}%   {done / 1048576:7.1f} Mo", flush=True)
                            last_pct = pct
                    elif time.time() - last_print >= 8:
                        print(f"  ...   {done / 1048576:7.1f} Mo", flush=True)
                        last_print = time.time()
        os.replace(tmp, dest)
        print(f"  Termine : {done / 1048576:7.1f} Mo")
        return True
    except Exception as e:
        print(f"[Erreur] telechargement interrompu : {e}")
        return False


def install_ollama() -> bool:
    install_dir = os.path.join(tempfile.gettempdir(), "Codeur-install")
    os.makedirs(install_dir, exist_ok=True)
    dest = os.path.join(install_dir, "OllamaSetup.exe")
    if os.path.exists(dest) and os.path.getsize(dest) > MIN_INSTALLER_SIZE:
        print("[Ollama] installateur deja telecharge, reutilise.")
    elif not _download(OLLAMA_URL, dest, "Ollama (installateur officiel)"):
        return False
    print("[Ollama] installation silencieuse en cours (sans droits admin)...")
    try:
        r = subprocess.run([dest, "/SP-", "/VERYSILENT", "/NORESTART"],
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                           timeout=900)
        if r.returncode != 0:
            print(f"[Erreur] l'installateur a echoue (code {r.returncode}).")
            return False
    except Exception as e:
        print(f"[Erreur] installation : {e}")
        return False
    for _ in range(120):
        if os.path.exists(OLLAMA_EXE):
            break
        time.sleep(1)
    if not os.path.exists(OLLAMA_EXE):
        print("[Erreur] Ollama installe mais introuvable dans son dossier.")
        return False
    try:
        os.remove(dest)
    except OSError:
        pass
    return True


def model_installed(model: str) -> bool:
    try:
        r = subprocess.run([_ollama_cmd(), "list"], capture_output=True,
                           text=True, timeout=60)
        return model in (r.stdout or "")
    except Exception:
        return False


def ensure_model(model: str) -> bool:
    if model_installed(model):
        return True
    print(f"[Modele] '{model}' absent -> telechargement (~2 Go, une seule fois).")
    try:
        r = subprocess.run([_ollama_cmd(), "pull", model], timeout=7200)
        return r.returncode == 0
    except Exception as e:
        print(f"[Erreur] modele : {e}")
        return False


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def create_shortcut() -> str:
    """Crée l'icône bureau 'Codeur' si absente. Renvoie son chemin."""
    exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
    exe_dir = os.path.dirname(exe)
    ps = (
        "$s = New-Object -ComObject WScript.Shell;"
        "$p = $s.SpecialFolders('Desktop') + '\\" + SHORTCUT_NAME + "';"
        "if (Test-Path $p) { Write-Output $p; exit };"
        "$d = $s.CreateShortcut($p);"
        "$d.TargetPath = " + _ps_quote(exe) + ";"
        "$d.Arguments = '';"
        "$d.WorkingDirectory = " + _ps_quote(exe_dir) + ";"
        "$d.IconLocation = " + _ps_quote(exe + ",0") + ";"
        "$d.Description = 'Codeur - agent IA de codage local, hors ligne';"
        "$d.Save();"
        "Write-Output $p"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True, text=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        path = (r.stdout or "").strip()
        return path if path else ""
    except Exception as e:
        print(f"[Erreur] creation du raccourci : {e}")
        return ""


def ensure_all() -> bool:
    """Vérifie tout une fois ; ne réinstalle jamais ce qui est présent."""
    if not ollama_running():
        if not ollama_installed():
            print("[Ollama] absent de ce poste -> installation (une seule fois).")
            if not install_ollama():
                return False
        if not start_ollama():
            print("[Erreur] impossible de demarrer Ollama.")
            return False
    if not ensure_model(MODEL):
        print("[Erreur] le modele IA n'est pas disponible.")
        return False
    lnk = create_shortcut()
    if lnk:
        print(f"[Raccourci] icone bureau creee : {lnk}")
    return True


def main() -> None:
    print("=" * 58)
    print("  Codeur - agent IA de codage local, hors ligne")
    print("=" * 58)
    if not ensure_all():
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
