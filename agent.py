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


# ---------------------------------------------------------------------------
# Demande de CALCUL mathématique : on force l'outil `calcul_symbolique`.
# Le petit modèle est incapable de calculer de tête ou d'écrire le code SymPy
# sans faute de transcription (ex: `ln(x)+1` au lieu de `ln(x+1)`). On lui
# impose donc de COPIER l'expression en texte brut et de recopier le résultat
# VÉRIFIÉ par SymPy.
# ---------------------------------------------------------------------------

MATH_REQUEST_MARKERS = (
    "intégrale", "integrale", "intégral", "integral", "primitive",
    "dérivée", "derivee", "dérive", "derive",
    "équation", "equation", "résous", "resous", "résoudre", "resoudre",
    "résolvez", "resolvez", "factorise", "factorisation", "factoriser",
    "limite", "calcul", "calcule", "mathématiques", "mathematiques",
    "mathématique", "mathematique", "maths", "sympy",
)

MATH_REQUEST_DIRECTIVE = (
    "[Calcul mathématique] RÈGLE ABSOLUE : ne réponds JAMAIS de mémoire pour "
    "un calcul. Exécute l'outil `calcul_symbolique` avec l'expression COPIÉE "
    "TELLE QUELLE de la demande (ex: expression=\"ln(x+1)\", operation=\"integrale\"). "
    "Ne transforme JAMAIS l'expression : ln(x+1) est UNE seule fonction, ce "
    "n'est PAS ln(x) + 1. "
    "1) Copie l'expression exacte de l'étudiant et appelle l'outil. "
    "2) Compare 'Expression interprétée' renvoyée par l'outil avec la fonction "
    "demandée : si elles diffèrent, CORRIGE l'expression et relance l'outil. "
    "3) Dans ta réponse finale, recopie EXACTEMENT la ligne de résultat de "
    "l'outil (ex: '∫ f(x) dx = x*log(x + 1) - x + log(x + 1) + C'), sans la "
    "modifier ni la simplifier : perdre un terme est interdit. "
    "4) Si l'étudiant demande la MÉTHODE (ex: 'par parties'), recopie la "
    "section 'MÉTHODE PAR PARTIES' de la sortie de l'outil calcul_symbolique, "
    "telle quelle. N'invente JAMAIS de règle, de formule ou de dérivation de "
    "ton cru : tout vient de la sortie VÉRIFIÉE de l'outil. "
    "5) Si l'outil signale une ERREUR d'interprétation, corrige la copie de "
    "l'expression et relance : ne réponds jamais sans résultat VÉRIFIÉ."
)


MATH_NUDGE = (
    "Rappel : l'utilisateur a demandé un CALCUL mathématique. Tu DOIS exécuter "
    "l'outil `calcul_symbolique` (l'expression en texte brut, copiée telle "
    "quelle) AVANT de donner ton résultat : ne réponds jamais de mémoire. "
    "Exécute-le maintenant, puis recopie son résultat VÉRIFIÉ."
)


KIND_PREFIXES = {
    "integrale": ("∫ f(",),
    "derivee": ("f'(",),
    "limite": ("lim ",),
    "equation": ("Solution(s",),
}


def _infer_kind(user_input: str) -> str:
    """Déduit le type de calcul demandé (pour extraire le bon résultat vérifié)."""
    t = (user_input or "").lower()
    if any(m in t for m in ("équation", "equation", "résous", "resous",
                            "résoudre", "resoudre", "résolvez", "resolvez")):
        return "equation"
    if "dériv" in t or "deriv" in t:
        return "derivee"
    if "limite" in t:
        return "limite"
    return "integrale"


def _extract_method_section(result: str) -> str:
    """Extrait la section 'MÉTHODE PAR PARTIES' (générée et vérifiée par SymPy)."""
    lines = (result or "").splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if ln.strip().startswith("MÉTHODE PAR PARTIES")), None)
    if start is None:
        return ""
    body = []
    for ln in lines[start:]:
        if ln.strip().startswith("VÉRIFICATION"):
            break
        body.append(ln)
    return "\n".join(body).strip()


def _ensure_verified_math(final_text: str, history: list,
                          kind: str = "integrale",
                          want_method: bool = False) -> str:
    """Garantit que la réponse finale contient le résultat VÉRIFIÉ de l'outil.

    Le petit modèle « résume » parfois la sortie de calcul_symbolique et en
    perd un terme (ex: ln(x+1) -> ln(x)+1). On ajoute donc, par le CODE, la
    ligne exacte vérifiée par SymPy à la réponse finale, si elle manque. On ne
    garde que le résultat du type demandé (équation, dérivée, intégrale...)
    pour ne pas capter un appel parasite. Si l'utilisateur demande la MÉTHODE,
    on y ajoute aussi la section par parties (générée par SymPy).
    """
    prefixes = KIND_PREFIXES.get(kind, KIND_PREFIXES["integrale"])
    for h in reversed(history):
        if h.get("role") != "tool":
            continue
        content = h.get("content") or ""
        if "VÉRIFICATION : CORRECT" not in content:
            continue
        lines = [ln.strip() for ln in content.splitlines()
                 if ln.strip().startswith(prefixes)]
        if not lines:
            continue
        for ln in lines:
            if ln not in (final_text or ""):
                final_text = f"{final_text}\n\n✅ Résultat vérifié (SymPy) : {ln}"
        if want_method:
            method = _extract_method_section(content)
            if method and method not in (final_text or ""):
                final_text = f"{final_text}\n\n{method}"
        break
    return final_text


def _wants_method(user_input: str) -> bool:
    """Vrai si l'utilisateur demande une MÉTHODE de calcul ('par parties')."""
    return "par partie" in (user_input or "").lower()


def is_math_request(user_input: str) -> bool:
    """Vrai si la demande exige un calcul mathématique réel (pas de réponse de mémoire)."""
    text = user_input.lower()
    return any(marker in text for marker in MATH_REQUEST_MARKERS)


def _apply_directive(messages: list, user_input: str) -> list:
    """Injette la directive adaptée dans le dernier message utilisateur."""
    messages[-1] = {
        **messages[-1],
        "content": MATH_REQUEST_DIRECTIVE + "\n\n" + user_input,
    }
    return messages


def _looks_like_tool_json(text: str) -> bool:
    """Vrai si la réponse ressemble à un JSON d'appel d'outil ({\"name\": ...}).

    Filet de sécurité : le modèle ne doit jamais renvoyer ce format en mode
    « explication » — s'il le fait, on redemande une réponse en texte normal.
    """
    t = (text or "").strip()
    return t.startswith("{") and '"name"' in t and (
        '"parameters"' in t or '"arguments"' in t)


# ---------------------------------------------------------------------------
# Filet de sécurité « plan sans action » : le modèle annonce un calcul ou une
# vérification mais s'arrête SANS exécuter d'outil. On le repère (marqueur de
# promesse + vocabulaire d'outil) et on lui renvoie une injonction de
# réellement exécuter, au plus une fois.
# ---------------------------------------------------------------------------

PENDING_MARKERS = (
    "je vais exécuter", "je vais executer", "je vais vérifier", "je vais verifier",
    "je vais calculer", "je vais utiliser", "je vais lancer", "je vais commencer",
    "je vais vous montrer", "je vais te montrer", "je vais montrer",
    "si vous souhaitez, je peux", "si tu veux, je peux", "je peux vous montrer",
    "je peux exécuter", "je peux executer", "je peux calculer", "je peux vérifier",
    "je peux verifier",
)

TOOL_WORDS = (
    "sympy", "python", "bash", "command", "intégr", "integr", "dériv", "deriv",
    "équation", "equation", "calcul", "outil", "calcul_symbolique",
)

PENDING_NUDGE = (
    "Tu as annoncé un calcul ou une vérification sans exécuter aucun outil. "
    "C'est interdit : exécute MAINTENANT l'outil `calcul_symbolique` (pour un "
    "calcul mathématique, l'expression en texte brut) ou l'outil adapté, puis "
    "donne le résultat réellement vérifié. Ne te contente pas de promettre ou "
    "de montrer du code."
)

MAX_NUDGES = 1


def _suggests_pending_action(text: str) -> bool:
    """Vrai si le texte promet une action (calcul/vérification) sans la faire."""
    t = (text or "").lower()
    return any(m in t for m in PENDING_MARKERS) and any(w in t for w in TOOL_WORDS)


# ---------------------------------------------------------------------------
# Garde anti-répétition : si le modèle réexécute EXACTEMENT la même commande
# qui vient d'échouer, on lui insuffle un conseil au lieu de le laisser
# tourner en boucle.
# ---------------------------------------------------------------------------

REPEAT_HINT = (
    "Tu viens d'exécuter EXACTEMENT la même commande qui a échoué. C'est "
    "inutile : corrige vraiment la commande avant de la relancer. Rappel : "
    "pour Python, mets des guillemets DOUBLES autour de la commande "
    "(python -c \"...\") et des apostrophes simples pour les chaînes à "
    "l'intérieur ; définis le symbole via sympy.symbols(...)."
)

MAX_REPEAT_HINTS = 2


def _call_key(name: str, arguments: dict) -> str:
    return f"{name}::{sorted((k, str(v)) for k, v in (arguments or {}).items())}"


def _looks_failed(result: str) -> bool:
    r = result or ""
    if "ERREUR" in r:
        return True
    return "code de sortie" in r and "code de sortie 0" not in r


def _clean_repetition(text: str, threshold: int = 3) -> str:
    """Coupe une réponse du modèle qui se répète en boucle.

    Parfois un petit modèle local « coince » et génère plusieurs fois le même
    paragraphe (dégénérescence). On détecte le bloc répété et on ne garde que
    la première occurrence, avec une note explicative. L'information utile
    (en tête de réponse) est conservée.
    """
    text = (text or "").strip()
    if not text:
        return text
    lines = text.splitlines()
    # On cherche la plus petite unité de répétition (1 à 8 lignes) dont le
    # texte contient au moins `threshold` occurrences.
    for unit in range(1, min(9, len(lines) + 1)):
        block = "\n".join(lines[:unit])
        if not block.strip():
            continue
        count = text.count(block)
        if count >= threshold:
            end = text.find(block) + len(block)
            note = ("\n\n[... réponse tronquée automatiquement : "
                    "le modèle se répétait]")
            return text[:end].rstrip() + note
    return text


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

    if is_math_request(user_input):
        # Demande de calcul : on force l'outil calcul_symbolique (outils actifs).
        messages = _apply_directive(messages, user_input)

    history = messages                    # on travaille sur la liste complète

    nudges = 0
    repeat_hints = 0
    prev_key = None
    any_tool = False
    used_math_tool = False
    for step in range(config.MAX_ITERATIONS):
        reply = llm.chat(history, tools=tools.TOOLS)
        history.append(reply)             # le message de l'assistant est conservé

        calls = llm.parse_tool_calls(reply)
        if not calls:                     # le modèle a fini de travailler
            if nudges < MAX_NUDGES:
                if is_math_request(user_input) and not used_math_tool:
                    # Un calcul demandé SANS outil : on refuse la réponse de mémoire.
                    history.append({"role": "user", "content": MATH_NUDGE})
                    nudges += 1
                    continue
                if (not any_tool
                        and _suggests_pending_action(reply.get("content") or "")):
                    history.append({"role": "user", "content": PENDING_NUDGE})
                    nudges += 1
                    continue
            final = reply.get("content") or "(réponse vide)"
            final = _clean_repetition(final)
            return (_ensure_verified_math(final, history,
                                          kind=_infer_kind(user_input),
                                          want_method=_wants_method(user_input)),
                    history)

        for call in calls:                # exécution des outils demandés
            any_tool = True
            if call["name"] == "calcul_symbolique":
                used_math_tool = True
            result = tools.execute_tool(call["name"], call["arguments"])
            if on_tool:
                on_tool(call, result)
            # La réponse de l'outil est renvoyée au modèle avec son id.
            history.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": result,
            })
            # Anti-boucle : même commande qui échoue deux fois -> conseil.
            key = _call_key(call["name"], call["arguments"])
            if (key == prev_key and repeat_hints < MAX_REPEAT_HINTS
                    and _looks_failed(result)):
                history.append({"role": "user", "content": REPEAT_HINT})
                repeat_hints += 1
            prev_key = key

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

    if is_math_request(user_input):
        # Demande de calcul : on force l'outil calcul_symbolique (outils actifs).
        messages = _apply_directive(messages, user_input)

    history = messages
    nudges = 0
    repeat_hints = 0
    prev_key = None
    any_tool = False
    used_math_tool = False
    for step in range(config.MAX_ITERATIONS):
        reply = llm.chat_stream(history, tools=tools.TOOLS, on_delta=on_delta)
        history.append(reply)

        calls = llm.parse_tool_calls(reply)
        if not calls:                     # le modèle a fini : texte diffusé
            if nudges < MAX_NUDGES:
                if is_math_request(user_input) and not used_math_tool:
                    history.append({"role": "user", "content": MATH_NUDGE})
                    nudges += 1
                    continue
                if (not any_tool
                        and _suggests_pending_action(reply.get("content") or "")):
                    history.append({"role": "user", "content": PENDING_NUDGE})
                    nudges += 1
                    continue
            final = reply.get("content") or "(réponse vide)"
            final = _clean_repetition(final)
            return (_ensure_verified_math(final, history,
                                          kind=_infer_kind(user_input),
                                          want_method=_wants_method(user_input)),
                    history)

        for call in calls:                # exécution des outils demandés
            any_tool = True
            if call["name"] == "calcul_symbolique":
                used_math_tool = True
            result = tools.execute_tool(call["name"], call["arguments"])
            if on_tool:
                on_tool(call, result)
            history.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": result,
            })
            # Anti-boucle : même commande qui échoue deux fois -> conseil.
            key = _call_key(call["name"], call["arguments"])
            if (key == prev_key and repeat_hints < MAX_REPEAT_HINTS
                    and _looks_failed(result)):
                history.append({"role": "user", "content": REPEAT_HINT})
                repeat_hints += 1
            prev_key = key

    return ("J'ai atteint la limite d'itérations. Décrivez votre besoin "
            "plus précisément ou divisez la tâche."), history
