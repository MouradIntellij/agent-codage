"""Configuration de l'agent.

Tous les réglages sont regroupés ici pour être faciles à modifier,
ou surchargeables par variables d'environnement (pour les CI / tests).
"""

import os

# --- Serveur LLM ----------------------------------------------------------
# Ollama expose une API compatible OpenAI sur http://localhost:11434/v1
# -> on peut donc lui envoyer exactement le même format JSON que ChatGPT.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

# Modèle utilisé (doit savoir faire du "tool calling").
# Par défaut llama3.2:latest : 2x-3x plus rapide sur CPU seul (pas de GPU).
# Pour une qualité maximale : qwen2.5:latest (3x plus lent).
MODEL = os.environ.get("AGENT_MODEL", "llama3.2:latest")

# Température du modèle (0 = déterministe, 1 = créatif)
TEMPERATURE = 0.2

# --- Performance (modèle local sur CPU) ---------------------------------------
# Nombre maximum de tokens générés par réponse (0 = illimité).
# C'est LE levier anti-lenteur : une réponse bornée = une attente bornée.
MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "1200"))

# Fenêtre de contexte demandée. 4096 suffit pour l'historique d'une session ;
# les modèles par défaut montent à 32k/128k et occupent beaucoup de RAM
# (portable 16 Go). On la borne pour rester léger.
NUM_CTX = int(os.environ.get("AGENT_NUM_CTX", "8192"))

# Durée (en secondes) pendant laquelle Ollama garde le modèle chargé en
# mémoire. 30 min = pas de rechargement entre deux demandes pendant un TP.
KEEP_ALIVE = int(os.environ.get("AGENT_KEEP_ALIVE", "1800"))

# Modèle utilisé. Pour un ordinateur SANS carte graphique (CPU seul) :
#   - llama3.2:latest  (~14 tokens/s) rapide, déjà installé         <-- défaut
#   - qwen2.5:latest   (~7  tokens/s) qualité + tool calling fiables
#   - qwen2.5:3b       (à télécharger) bon compromis vitesse/qualité
# Surcharger avec la variable d'environnement AGENT_MODEL.

# --- Sécurité / limites -----------------------------------------------------
# Nombre maximum d'étapes "agent -> outil -> agent" avant de s'arrêter.
# Évite qu'une boucle infinie coûte de l'argent (ou du temps).
MAX_ITERATIONS = 25

# Durée maximale (en secondes) pour une commande du terminal exécutée par l'agent.
BASH_TIMEOUT = 30

# Nombre maximum de lignes retournées par read_file / list_dir.
MAX_READ_LINES = 400

# Emplacement par défaut sur lequel l'agent travaille.
WORKSPACE = os.environ.get("AGENT_WORKSPACE", ".")


def api_url() -> str:
    """URL de l'endpoint chat compatible OpenAI."""
    return f"{OLLAMA_URL}/v1/chat/completions"
