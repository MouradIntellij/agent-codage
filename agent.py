"""La BOUCLE de l'agent (le coeur du système).

C'est un simple cycle "raisonner puis agir" (ReAct) :

    ┌─────────────────────────────────────────────┐
    │  1. envoie les messages au modèle            │
    │  2. le modèle répond: texte ? ou appels ?    │
    │     ├─ texte final ──────────► retourne      │
    │     └─ appels d'outils                       │
    │        └─ exécute chaque outil               │
    │           └─ renvoie le résultat au modèle   │
    │              └─ RETOUR à l'étape 1 (boucle)  │
    └─────────────────────────────────────────────┘

Pas de magie : c'est une boucle `for` qui s'arrête soit quand le modèle
répond en texte, soit après MAX_ITERATIONS tours (anti-boucle infinie).
"""

import config
import llm
import tools
from prompt import build_messages

# ---------------------------------------------------------------------------
# Porte de décision : certaines demandes n'ont besoin d'AUCUN outil.
# « Donne-moi le code / comment faire ... ? » → réponse DIRECTE.
# Si on n'annonce pas d'outils au modèle, il ne peut PAS chercher sur le
# disque : c'est la garantie anti « recherche infinie ».
# ---------------------------------------------------------------------------

CODE_REQUEST_MARKERS = (
    # « donne-moi le code »
    "donne-moi le code", "donnez-moi le code", "donne moi le code", "donnez moi le code",
    # « le code en python/typescript ... »
    "le code en", "du code en", "un code en", "le code typescript", "le code python",
    "le code javascript", "code en python", "code en typescript", "code en javascript",
    "code en ts", "code en js",
    # « le code pour ... », « un exemple de code »
    "le code pour", "un code pour", "un exemple de code",
    # « comment lire / écrire / créer ... ? »
    "comment lire", "comment ecrire", "comment écrire", "comment creer", "comment créer",
    "comment ouvrir", "comment fonctionne", "comment ca marche", "comment ça marche",
    # demandes d'explication
    "c'est quoi", "c est quoi", "qu'est-ce que", "qu est ce que",
    "que veut dire", "que signifie", "différence entre",
    # « explique moi / expliquer / explain »
    "explique-moi", "expliquez-moi", "explique moi", "expliquez moi",
    "explique", "expliquez", "expliquer", "explain",
    # « que fait ce code », « à quoi sert ... »
    "que fait ce code", "que fait cette fonction", "que fait cette ligne",
    "à quoi sert", "a quoi sert", "pourquoi ce code", "pourquoi cette ligne",
)

# Suites d'une demande d'explication : « et ce code », « ce script »…
# MAIS si un verbe d'action est présent (« corrige ce code »), c'est une
# ACTION : la porte reste ouverte aux outils.
CODE_PASTE_MARKERS = (
    "ce code", "ce script", "cette fonction", "cette classe",
    "ce programme", "cet extrait",
)

ACTION_VERBS = (
    "crée", "cree", "crées", "crees", "creez", "corrige", "corriges",
    "corrigez", "exécute", "execute", "exécutez", "executez", "modifie",
    "modifies", "modifiez", "lance", "lances", "lancez", "lancer", "compile",
    "compilez", "teste", "testes", "testez", "supprime", "supprimes",
    "supprimez", "écris", "ecris", "écrivez", "ecrivez", "renomme",
    "renommez", "copie", "déplace", "deplace", "déplacez", "deplacez",
    "analyse", "analyses", "analysez", "analyser", "résume", "resume",
    "résumez", "installe", "installes", "installez", "enregistre",
    "enregistrez", "sauvegarde", "sauve", "fixe", "fixes", "fixez",
)

CODE_REQUEST_DIRECTIVE = (
    "[Demande de code ou d'explication] L'utilisateur veut du code ou une "
    "explication, pas que tu agisses sur le disque. Réponds DIRECTEMENT. "
    "Écris en texte normal en français : JAMAIS de JSON, ni de format "
    "d'appel d'outil comme {\"name\": ...}. "
    "Si c'est une demande d'EXPLICATION de code : explique de façon "
    "pédagogique, étape par étape, le rôle de chaque partie, les termes "
    "techniques et la syntaxe, avec un exemple simple si utile. "
    "Ne cherche aucun fichier, n'exécute rien."
)


def is_code_request(user_input: str) -> bool:
    """Vrai si la demande est « comment faire » ou « donne-moi le code »."""
    text = user_input.lower()
    if any(marker in text for marker in CODE_REQUEST_MARKERS):
        return True
    # Suite d'une explication (« et ce code ») : réponse directe, à condition
    # qu'aucun verbe d'action ne montre que l'utilisateur veut AGIR.
    if any(p in text for p in CODE_PASTE_MARKERS) and not any(
            v in text for v in ACTION_VERBS):
        return True
    return False


def _looks_like_tool_json(text: str) -> bool:
    """Vrai si la réponse ressemble à un JSON d'appel d'outil ({\"name\": ...}).

    Filet de sécurité : le modèle ne doit jamais renvoyer ce format en mode
    « explication » — s'il le fait, on redemande une réponse en texte normal.
    """
    t = (text or "").strip()
    return t.startswith("{") and '"name"' in t and (
        '"parameters"' in t or '"arguments"' in t)


def _direct_answer(messages: list, on_delta=None) -> dict:
    """Réponse DIRECTE, sans outil.

    Si le modèle renvoie malgré tout du JSON d'appel d'outil (petit modèle
    qui imite le code collé), on refait une demande en texte normal, au plus
    une fois.
    """
    reply = None
    for _ in range(2):
        reply = (llm.chat_stream(messages, on_delta=on_delta)
                 if on_delta else llm.chat(messages))
        if not _looks_like_tool_json(reply.get("content") or ""):
            return reply
        messages = [*messages, reply, {
            "role": "user",
            "content": ("Ta réponse précédente était un JSON d'appel d'outil, "
                        "interdit ici. Réponds maintenant en texte français "
                        "normal : une explication pédagogique, sans aucun JSON."),
        }]
    return reply


def run_agent(user_input: str, history: list | None = None,
              on_tool=None) -> tuple[str, list]:
    """Exécute une demande utilisateur complète.

    - user_input : la demande (str)
    - history    : messages précédents pour garder la mémoire de session
    - on_tool    : callback optionnel affiché par la CLI (trace des outils)

    Retourne (réponse finale, historique mis à jour).
    """
    messages = build_messages(user_input, history)

    if is_code_request(user_input):
        # Demande de code / explication : on répond DIRECTEMENT. Comme on ne
        # fournit AUCUN outil, le modèle ne peut pas chercher de fichier.
        messages[-1] = {
            **messages[-1],
            "content": CODE_REQUEST_DIRECTIVE + "\n\n" + user_input,
        }
        reply = _direct_answer(messages)          # tools=None par défaut
        messages.append(reply)
        return reply.get("content") or "(réponse vide)", messages

    history = messages                    # on travaille sur la liste complète

    for step in range(config.MAX_ITERATIONS):
        reply = llm.chat(history, tools=tools.TOOLS)
        history.append(reply)             # le message de l'assistant est conservé

        calls = llm.parse_tool_calls(reply)
        if not calls:                     # le modèle a fini de travailler
            return reply.get("content") or "(réponse vide)", history

        for call in calls:                # exécution des outils demandés
            result = tools.execute_tool(call["name"], call["arguments"])
            if on_tool:
                on_tool(call, result)
            # La réponse de l'outil est renvoyée au modèle avec son id.
            history.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": result,
            })

    return ("J'ai atteint la limite d'itérations. Décrivez votre besoin "
            "plus précisément ou divisez la tâche."), history


def run_agent_stream(user_input: str, history: list | None = None,
                     on_delta=None, on_tool=None) -> tuple[str, list]:
    """Même boucle que run_agent(), mais la réponse est DIFFUSÉE en direct.

    - on_delta(chunk) : appelé à chaque morceau de texte généré (str).
    - on_tool(call, result) : appelé à chaque utilisation d'un outil.

    La page web s'en sert pour afficher la réponse au fil de l'eau pendant
    qu'elle est générée : plus d'attente muette devant une page blanche.
    """
    messages = build_messages(user_input, history)

    if is_code_request(user_input):
        # Porte de décision : réponse directe, sans aucun outil.
        messages[-1] = {
            **messages[-1],
            "content": CODE_REQUEST_DIRECTIVE + "\n\n" + user_input,
        }
        reply = _direct_answer(messages, on_delta=on_delta)
        messages.append(reply)
        return reply.get("content") or "(réponse vide)", messages

    history = messages
    for step in range(config.MAX_ITERATIONS):
        reply = llm.chat_stream(history, tools=tools.TOOLS, on_delta=on_delta)
        history.append(reply)

        calls = llm.parse_tool_calls(reply)
        if not calls:                     # le modèle a fini : texte diffusé
            return reply.get("content") or "(réponse vide)", history

        for call in calls:                # exécution des outils demandés
            result = tools.execute_tool(call["name"], call["arguments"])
            if on_tool:
                on_tool(call, result)
            history.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": result,
            })

    return ("J'ai atteint la limite d'itérations. Décrivez votre besoin "
            "plus précisément ou divisez la tâche."), history
