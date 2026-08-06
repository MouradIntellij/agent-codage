"""Interface WEB de l'agent (en plus du terminal).

Lancez avec:   python web.py
Puis ouvrez:   http://127.0.0.1:3000  (ou la page affichée)

Une personne sans accès au code peut alors poser ses questions au "Codeur"
dans son navigateur, même hors du dossier d'exécution (donner un chemin absolu).

Zéro nouvelle dépendance : tout vient de la bibliothèque standard
(http.server, http.cookies). Seul `requests` (déjà utilisé pour le LLM) est
nécessaire.

Sécurité : par défaut, on n'écoute QUE sur 127.0.0.1 (local).
Pour ouvrir à toute la classe (réseau local) :
    AGENT_HOST=0.0.0.0 python web.py
⚠️  Cela expose les outils (bash inclus) à tout le réseau local — réservez-le
    à une classe de confiance, jamais sur Internet public.
"""

import base64
import json
import os
import secrets
import threading
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import agent
import config
import tools

# L'agent travaille dans l'espace de travail déclaré (comme main.py).
os.makedirs(config.WORKSPACE, exist_ok=True)
os.chdir(config.WORKSPACE)

HOST = os.environ.get("AGENT_HOST", "127.0.0.1")
PORT = int(os.environ.get("AGENT_PORT", "3000"))

HTML_PATH = Path(__file__).resolve().parent / "public" / "index.html"

# Mémoire de session : id de session -> historique des messages.
sessions: dict[str, list] = {}
_lock = threading.Lock()

# --- pièces jointes (fichiers téléversés depuis le navigateur) --------------

UPLOAD_DIR_NAME = "uploads"
MAX_FILE_SIZE = 8 * 1024 * 1024  # 8 Mo par fichier
MAX_FILES = 8                    # 8 fichiers par message
_SAFE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            " .-_éàèêëïîôûùçÉÀÈÊËÏÎÔÛÙÇ()")


def _safe_filename(name: str) -> str:
    """Garde un nom de fichier inoffensif (supprime tout chemin ou caractère
    dangereux). Retourne une chaîne vide si rien ne survit."""
    base = os.path.basename((name or "").replace("\\", "/")).strip()
    clean = "".join(c for c in base if c in _SAFE).strip().rstrip(". ")
    return clean


def _save_attachments(sid: str, files: list) -> list[str]:
    """Sauvegarde les pièces jointes dans uploads/<session>/ et renvoie la
    liste des chemins absolus enregistrés."""
    if not files:
        return []
    if len(files) > MAX_FILES:
        raise ValueError(f"Trop de fichiers joints (max {MAX_FILES}).")
    sess_dir = os.path.join(os.path.abspath(config.WORKSPACE),
                            UPLOAD_DIR_NAME, sid)
    os.makedirs(sess_dir, exist_ok=True)
    saved: list[str] = []
    for f in files:
        name = _safe_filename(f.get("name") or "")
        raw = f.get("data") or ""
        if not name or not raw:
            continue
        try:
            blob = base64.b64decode(raw, validate=True)
        except Exception:
            continue
        if not blob:
            continue
        if len(blob) > MAX_FILE_SIZE:
            raise ValueError(f"Fichier trop volumineux '{name}' "
                             f"(max {MAX_FILE_SIZE // (1024 * 1024)} Mo).")
        dest = os.path.join(sess_dir, name)
        with open(dest, "wb") as fh:
            fh.write(blob)
        saved.append(dest)
    return saved


class Handler(BaseHTTPRequestHandler):
    """Répond aux requêtes du navigateur : page web + API JSON."""

    server_version = "Codeur/1.0"

    # --- petites aides -----------------------------------------------------

    def log_message(self, format, *args):  # noqa: A002 - on garde la console propre
        return

    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        new_cookie = getattr(self, "_new_cookie", None)
        if new_cookie:
            self.send_header("Set-Cookie", new_cookie)
            self._new_cookie = None
        self.end_headers()
        self.wfile.write(payload)

    def _session_id(self) -> str:
        """Retrouve (ou crée) la session du navigateur grâce au cookie."""
        try:
            cookie = SimpleCookie()
            cookie.load(self.headers.get("Cookie", ""))
            sid = cookie.get("session")
            if sid is not None and sid.value in sessions:
                return sid.value
        except CookieError:
            pass
        sid = secrets.token_hex(8)
        with _lock:
            sessions[sid] = []
        # Envoyé par _json() APRÈS la ligne de statut (sinon HTTP est invalide).
        self._new_cookie = f"session={sid}; Path=/; HttpOnly; SameSite=Strict"
        return sid

    # --- streaming SSE (réponse affichée au fil de l'eau) --------------------

    def _start_sse(self) -> None:
        """En-têtes HTTP pour une réponse en continu (Server-Sent Events)."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")   # la fin du flux ferme la connexion
        new_cookie = getattr(self, "_new_cookie", None)
        if new_cookie:
            self.send_header("Set-Cookie", new_cookie)
            self._new_cookie = None
        self.end_headers()
        self.wfile.flush()

    def _send_event(self, data: dict) -> None:
        """Envoie un événement JSON au navigateur (`data: {...}` + ligne vide)."""
        payload = "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"
        self.wfile.write(payload.encode("utf-8"))
        self.wfile.flush()

    def _end_sse(self) -> None:
        """Marque la fin du flux et ferme la connexion HTTP."""
        self.wfile.write("data: [DONE]\n\n".encode("utf-8"))
        self.wfile.flush()
        self.close_connection = True

    # --- routes ------------------------------------------------------------

    def do_GET(self):
        if self.path.split("?")[0] == "/":
            html = HTML_PATH.read_text(encoding="utf-8")
            html = html.replace("__MODEL__", config.MODEL)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._json(404, {"error": "Introuvable."})

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/reset":
            sid = self._session_id()
            with _lock:
                sessions[sid] = []
            self._json(200, {"ok": True})
            return
        if path == "/api/chat":
            self._handle_chat()
            return
        self._json(404, {"error": "Introuvable."})

    def _handle_chat(self):
        """Reçoit {message}, fait tourner l'agent, renvoie réponse + trace.

        Deux modes :
          - flux SSE  (le navigateur envoie `Accept: text/event-stream`) :
            la réponse est diffusée morceau par morceau + les outils en direct ;
          - JSON classique (anciens clients) : réponse complète à la fin.
        """
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b""
            data = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            self._json(400, {"error": "JSON invalide."})
            return

        message = str(data.get("message", "")).strip()
        files = data.get("files") or []
        if not message and not files:
            self._json(400, {"error": "Message vide."})
            return

        sid = self._session_id()

        # Pièces jointes -> fichiers sur le disque -> mentionnés au modèle.
        attachments: list[str] = []
        try:
            paths = _save_attachments(sid, files)
        except ValueError as err:
            self._json(400, {"error": str(err)})
            return
        for path in paths:
            is_img = os.path.splitext(path)[1].lower() in tools.IMAGE_EXTS
            kind = "image" if is_img else "fichier"
            attachments.append(f"- {path}  ({kind}, {os.path.getsize(path):,} o)")
        if attachments:
            block = ("\n".join(attachments)
                     + "\n\n[Tu DOIS lire chaque pièce jointe pour répondre : "
                       "read_document / read_file pour un document, read_image "
                       "pour une image. Ne devine jamais leur contenu.]")
            message = (message + "\n\n" if message else "") + block

        wants_stream = "text/event-stream" in (self.headers.get("Accept") or "")

        history = None
        with _lock:
            history = list(sessions.get(sid, []))

        trace: list[dict] = []

        def on_tool(call: dict, result: str) -> None:
            trace.append({
                "name": call["name"],
                "arguments": call["arguments"],
                "result": result,
            })
            if wants_stream:
                # Indicateur léger en direct ; le détail complet part dans "done".
                self._send_event({"type": "tool", "name": call["name"],
                                  "arguments": call["arguments"]})

        def on_delta(chunk: str) -> None:
            if wants_stream:
                self._send_event({"type": "text", "content": chunk})

        try:
            if wants_stream:
                self._start_sse()
                response, updated = agent.run_agent_stream(
                    message, history, on_delta=on_delta, on_tool=on_tool)
                with _lock:
                    sessions[sid] = updated
                self._send_event({"type": "done", "response": response,
                                  "tools": trace})
                self._end_sse()
            else:
                response, updated = agent.run_agent(message, history, on_tool=on_tool)
                with _lock:
                    sessions[sid] = updated
                self._json(200, {"response": response, "tools": trace})
        except Exception as err:  # filet de sécurité
            if wants_stream:
                self._send_event({"type": "error", "error": str(err)})
                self._end_sse()
            else:
                self._json(500, {"error": str(err)})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print(f"Codeur (web) — modèle {config.MODEL}")
    print(f"  Page de chat : http://{HOST}:{PORT}")
    print("  Ctrl+C pour arrêter.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")


if __name__ == "__main__":
    main()
