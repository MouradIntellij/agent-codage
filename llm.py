"""Client HTTP minimal vers un serveur LLM compatible OpenAI.

Pourquoi `requests` et pas le SDK officiel `openai` ?
Pour que les étudiants voient exactement ce qui circule sur le réseau :
un simple POST JSON vers /v1/chat/completions, comme avec ChatGPT.
"""

import json

import requests

import config


def chat(messages: list, tools: list | None = None) -> dict:
    """Envoie la conversation au modèle et retourne LE MESSAGE de l'assistant.

    Le message est renvoyé dans son FORMAT FILAIRE (prêt à être ré-utilisé
    dans l'historique), c'est-à-dire:
        {"role": "assistant", "content": "...",
         "tool_calls": [{"id": "...", "function": {"name": "...",
                         "arguments": "{...}"}}]}

    `tool_calls` n'est présent que si le modèle décide d'appeler un outil.
    """

    payload = {
        "model": config.MODEL,
        "messages": messages,
        "temperature": config.TEMPERATURE,
        "max_tokens": config.MAX_TOKENS,   # borne la réponse = borne l'attente
        "options": {                       # extensions Ollama (acceptées par /v1)
            "num_ctx": config.NUM_CTX,     # fenêtre de contexte (RAM)
            "keep_alive": config.KEEP_ALIVE,  # modèle gardé chargé entre demandes
        },
    }
    if tools:                       # si des outils sont fournis, on les annonce
        payload["tools"] = tools

    try:
        response = requests.post(config.api_url(), json=payload, timeout=300)
    except requests.ConnectionError as err:
        raise SystemExit(
            f"Impossible de joindre Ollama sur {config.OLLAMA_URL}.\n"
            "Lancez 'ollama serve' (ou ouvrez l'app Ollama) puis réessayez."
        ) from err

    if response.status_code != 200:
        raise RuntimeError(f"Erreur HTTP {response.status_code}: {response.text}")

    response.encoding = "utf-8"  # Ollama répond toujours en UTF-8 (les accents)
    data = response.json()
    return _clean_message(data["choices"][0]["message"])


def _clean_message(message: dict) -> dict:
    """Garde uniquement les champs connus, pour un écho sûr dans l'historique."""
    cleaned = {"role": "assistant", "content": message.get("content")}
    if message.get("tool_calls"):
        calls = []
        for call in message["tool_calls"]:
            function = call.get("function", {})
            args = function.get("arguments", {})
            calls.append({
                "id": call.get("id", ""),
                "type": "function",
                "function": {
                    "name": function.get("name", ""),
                    "arguments": args if isinstance(args, str) else json.dumps(args),
                },
            })
        cleaned["tool_calls"] = calls
    return cleaned


def parse_tool_calls(message: dict) -> list:
    """Transforme les tool_calls du message en liste normalisée pour le code.

    Résultat: [{"id": "...", "name": "...", "arguments": {dict}}]
    Ici `arguments` devient un vrai dictionnaire Python, exploitable.
    """
    result = []
    for call in message.get("tool_calls") or []:
        function = call["function"]
        raw = function.get("arguments", "{}")
        if isinstance(raw, str):
            try:
                args = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                args = {"_raw": raw}
        else:
            args = raw
        result.append({"id": call.get("id", ""), "name": function.get("name", ""),
                       "arguments": args})
    return result


def chat_stream(messages: list, tools: list | None = None,
                on_delta=None) -> dict:
    """Comme chat(), mais la réponse arrive MORCEAU PAR MORCEAU (streaming).

    - on_delta(chunk) : fonction appelée à chaque bout de texte reçu (str).
      L'utilisateur voit la réponse apparaître PENDANT qu'elle est générée,
      au lieu d'attendre la fin (crucial quand le modèle est lent sur CPU).
    - Retourne le message assistant COMPLET (même format filaire que chat()),
      donc utilisable à l'identique dans l'historique de la boucle.

    Côté réseau : un POST avec `stream: true` ; le serveur répond alors en
    SSE (Server-Sent Events), une ligne `data: {...}` par morceau.
    """
    payload = {
        "model": config.MODEL,
        "messages": messages,
        "temperature": config.TEMPERATURE,
        "max_tokens": config.MAX_TOKENS,
        "stream": True,
        "options": {                       # extensions Ollama (acceptées par /v1)
            "num_ctx": config.NUM_CTX,
            "keep_alive": config.KEEP_ALIVE,
        },
    }
    if tools:
        payload["tools"] = tools

    try:
        response = requests.post(config.api_url(), json=payload,
                                 stream=True, timeout=300)
    except requests.ConnectionError as err:
        raise SystemExit(
            f"Impossible de joindre Ollama sur {config.OLLAMA_URL}.\n"
            "Lancez 'ollama serve' (ou ouvrez l'app Ollama) puis réessayez."
        ) from err

    if response.status_code != 200:
        raise RuntimeError(f"Erreur HTTP {response.status_code}: {response.text}")

    # Sans cela, `requests` suppose ISO-8859-1 pour les flux text/event-stream
    # et les accents UTF-8 du modèle arrivent brouillés (« crÃ©ons » au lieu de
    # « créons »). Ollama sert toujours de l'UTF-8 : on le force.
    response.encoding = "utf-8"

    content_parts: list[str] = []
    tool_calls = None
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        delta = ((chunk.get("choices") or [{}])[0].get("delta")) or {}
        text = delta.get("content")
        if text:
            content_parts.append(text)
            if on_delta:
                on_delta(text)
        if delta.get("tool_calls"):        # Ollama envoie l'objet complet
            tool_calls = delta["tool_calls"]

    message = {"role": "assistant", "content": "".join(content_parts) or None}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return _clean_message(message)
