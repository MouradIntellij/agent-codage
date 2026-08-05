"""Interface terminal de l'agent codeur.

Lancez avec:  python main.py
Puis tapez vos demandes en français. Exemples:
    "Crée un script Python qui affiche les nombres premiers < 100"
    "Ajoute un test pytest dans tests/ et exécute-le"
    "Explique ce que fait le fichier agent.py"

Commandes:  /quit, /exit   -> quitter
            /new           -> effacer la mémoire de la session
            /model         -> afficher le modèle actif
"""

import os
import sys

import agent
import config

# L'agent travaille dans l'espace de travail déclaré (tous ses outils
# et ses commandes bash s'y exécutent).
os.makedirs(config.WORKSPACE, exist_ok=True)
os.chdir(config.WORKSPACE)

# --- Petites couleurs ANSI pour un terminal agréable (optionnel) -----------
_CYAN = "\033[36m"
_GRAY = "\033[90m"
_GREEN = "\033[32m"
_RESET = "\033[0m"

history: list = []          # mémoire de session, partagée par tous les tours


def display_tool(call: dict, result: str) -> None:
    """Affiche en direct l'outil que l'agent utilise (transparence totale)."""
    args = ", ".join(f"{k}={v!r}" for k, v in call["arguments"].items())
    print(f"{_GRAY}  [outil] {call['name']}({args}){_RESET}")
    for line in result.splitlines()[:8]:          # aperçu tronqué du résultat
        print(f"{_GRAY}    {line}{_RESET}")


def main() -> None:
    print(f"{_CYAN}Codeur{_RESET} — agent de codage local ({config.MODEL})")
    print(f"Espace de travail: {config.WORKSPACE}")
    print("Tapez une demande, ou /help pour les commandes.\n")

    while True:
        try:
            user_input = input(f"{_GREEN}vous> {_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAu revoir !")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit", "/quit "):
            print("Au revoir !")
            break
        if user_input.lower() == "/new":
            history.clear()
            print("Mémoire de session effacée.\n")
            continue
        if user_input.lower() == "/model":
            print(f"Modèle actif: {config.MODEL} (Ollama: {config.OLLAMA_URL})\n")
            continue
        if user_input.lower() == "/help":
            print("Demandes en français, ou: /quit /exit /new /model /help\n")
            continue

        try:
            print(f"{_GRAY}...{_RESET}")
            final, updated = agent.run_agent(user_input, history,
                                             on_tool=display_tool)
            history[:] = updated          # mise à jour en place de la mémoire
            print(f"{_CYAN}codeur> {_RESET}{final}\n")
        except Exception as err:                  # filet de sécurité
            print(f"{_GRAY}[erreur] {err}{_RESET}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
