# Travail pratique — Créer votre premier agent IA de codage

| | |
|---|---|
| **Cours** | Programmation et IA appliquée |
| **Durée** | 6 à 9 heures (2 à 3 séances) |
| **Niveau** | Étudiant en informatique (2ᵉ année) |
| **Matériel** | 100 % **gratuit** : Ollama, Python, votre ordinateur |
| **Mode** | Travail individuel ou en binôme |
| **Remise** | Dossier zippé `VotreNom_AgentIA.zip` (code + rapport) |

> **Objectif final** : à la fin de ce TP, vous serez capables de créer **vos propres
> agents IA** : des programmes qui utilisent un modèle de langage (LLM) pour
> comprendre une demande, agir sur votre ordinateur (lire/écrire des fichiers,
> lancer des commandes) et rendre compte du résultat.

---

## Table des matières

1. [Objectifs d'apprentissage](#1-objectifs-dapprentissage)
2. [Concepts à connaître (10 minutes)](#2-concepts-à-connaître)
3. [Étape 1 — Installer les outils gratuits](#3-étape-1--installer-les-outils-gratuits)
4. [Étape 2 — Prendre en main Ollama](#4-étape-2--prendre-en-main-ollama)
5. [Étape 3 — Comprendre l'API d'un LLM](#5-étape-3--comprendre-lapi-dun-llm)
6. [Étape 4 — Le « tool calling »](#6-étape-4--le-tool-calling)
7. [Étape 5 — Construire votre agent, étape par étape](#7-étape-5--construire-votre-agent)
8. [Étape 6 — Créez votre propre agent](#8-étape-6--créez-votre-propre-agent)
9. [Grille d'évaluation](#9-grille-dévaluation)
10. [Dépannage](#10-dépannage)
11. [Pour aller plus loin](#11-pour-aller-plus-loin)

---

## 1. Objectifs d'apprentissage

À la fin de ce TP, vous serez capables de :

| # | Compétence |
|---|---|
| 1 | Expliquer ce qu'est un agent IA et en quoi il se distingue d'un simple chatbot |
| 2 | Installer et utiliser un modèle de langage local gratuit (Ollama) |
| 3 | Envoyer un appel HTTP à un LLM et interpréter la réponse JSON |
| 4 | Définir des outils (tools) et comprendre le mécanisme du *tool calling* |
| 5 | Écrire la boucle « raisonner → agir → observer → réessayer » d'un agent |
| 6 | Créer un agent personnel fonctionnel et le présenter |

---

## 2. Concepts à connaître

Lisez ceci avant de commencer. C'est la théorie minimale, avec des analogies.

### 2.1 Qu'est-ce qu'un LLM ? Un « cerveau sans bras »

Un **LLM** (*Large Language Model*, ex. : GPT, Claude, Qwen) est un programme qui
prédit le mot suivant à partir du texte qu'il reçoit. Il a été entraîné sur
d'énormes quantités de texte.

> 🧠 **Analogie** : un LLM est un **cerveau très cultivé… mais sans bras ni
> jambes**. Il peut *réfléchir* et *écrire*, mais il ne peut pas toucher votre
> ordinateur. Il ne peut ni lire vos fichiers, ni exécuter vos commandes.

### 2.2 Qu'est-ce qu'un agent ? Un cerveau + des bras

Un **agent IA** = un LLM **+ des outils** + une **boucle de décision**.
C'est tout. Vraiment.

> 🦾 **Analogie** : donnez des bras au cerveau. Les « bras », ce sont des
> **fonctions Python** que *vous* écrivez (lire un fichier, lancer une commande…).
> Le LLM décide **quelle fonction appeler**, avec quels arguments, et nous — le
> code — l'exécutons vraiment.

```
┌────────────────────────────────────────────────┐
│  Le CERVEAU (LLM)                               │
│  - reçoit la demande + la liste des outils      │
│  - répond : "du texte"  OU  "j'appelle l'outil  │
│    bash avec {command: 'python test.py'}"       │
└───────────────┬────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────────┐
│  Les BRAS (vos fonctions Python)               │
│  - exécutent réellement l'action               │
│  - renvoient le résultat au cerveau            │
└────────────────────────────────────────────────┘
```

### 2.3 Le *tool calling* : du JSON, rien que du JSON

Le *tool calling* (appel d'outil) semble magique, mais c'est une mécanique très
simple :

1. Vous envoyez au LLM la liste de vos outils, **décrits en JSON** (nom,
   description, paramètres).
2. Le LLM décide d'utiliser un outil et renvoie un **JSON** du genre :
   ```json
   {"name": "write_file", "arguments": {"path": "hello.py", "content": "..."}}
   ```
3. **Votre code** lit ce JSON et appelle la fonction Python correspondante.
4. Vous renvoyez le **résultat** de la fonction au LLM, qui continue.

> ⚠️ **Point clé** : le LLM ne « prend pas le contrôle » de votre ordinateur.
> Il **propose** un appel d'outil. Si vous ne fournissez pas la fonction, rien ne
> s'exécute. C'est vous qui décidez ce que votre agent peut faire.

### 2.4 Le vocabulaire à retenir

| Terme | Définition |
|---|---|
| **LLM** | Modèle de langage (le « cerveau ») |
| **Prompt** | Le texte envoyé au modèle |
| **System prompt** | Les instructions de rôle données au modèle en premier |
| **Tool / outil** | Une fonction Python mise à la disposition du modèle |
| **Tool calling** | Le mécanisme où le modèle demande d'exécuter un outil |
| **Agent loop** | La boucle : raisonner → agir → observer → réessayer |
| **Contexte** | Tout l'historique des messages envoyé au modèle à chaque tour |

---

## 3. Étape 1 — Installer les outils gratuits

> ⏱️ 30 minutes | ✔️ Résultat : vous avez Ollama et Python fonctionnels

Vous n'avez besoin que de **deux outils**, tous deux gratuits et libres :

### 3.1 Python

Python est probablement déjà installé. Vérifiez :

```
python --version
```

- ✅ Si un numéro s'affiche (ex. `Python 3.11.5`) : parfait, continuez.
- ❌ Sinon : téléchargez Python depuis **https://www.python.org/downloads/**
  et, à l'installation, **cochez « Add Python to PATH »**.

### 3.2 Ollama (le LLM local gratuit)

Ollama permet de faire tourner des modèles de langage **sur votre propre
ordinateur**, gratuitement, sans connexion ni compte.

1. Téléchargez Ollama : **https://ollama.com/download**
2. Installez-le et lancez l'application (une icône de lama apparaît en bas à droite).
3. Ouvrez un **terminal** (PowerShell sur Windows) et vérifiez :
   ```
   ollama --version
   ```

### 3.3 Télécharger votre premier modèle

Ollama est un « magasin de modèles ». Vous en téléchargez un (quelques Go,
une seule fois) :

```
ollama pull llama3.2:latest
```

> **Pourquoi ce modèle ?** `llama3.2` est gratuit, tourne sur un ordinateur
> ordinaire, parle français et sait faire du *tool calling*, ce qui est
> indispensable pour créer un agent. Sa taille (3 milliards de paramètres) le
> rend **rapide même sans carte graphique** — important en classe.
>
> 🐢 **Si les réponses sont trop lentes** : tout se passe sur le CPU.
> Alternative plus éloquente : `qwen2.5:latest` (plus soigné en prose et
> fichiers, MAIS saute les appels d'outil de calcul). Essayez sans toucher au
> code : `set AGENT_MODEL=qwen2.5:latest && python main.py`.

✔️ **À vérifier** : `ollama list` affiche `llama3.2:latest`.

---

## 4. Étape 2 — Prendre en main Ollama

> ⏱️ 20 minutes | ✔️ Résultat : vous dialoguez avec un modèle

Ollama expose une **API web** (une interface HTTP) sur votre machine.
C'est par cette API que vos programmes parleront au modèle.

### 4.1 Tester en ligne de commande

```
ollama run llama3.2:latest
```

Posez une question, par exemple :
```
Pourquoi dit-on qu'un LLM est un "cerveau sans bras" ?
```
Puis quittez avec `/bye` ou Ctrl+D.

### 4.2 Vérifier que le serveur web tourne

Votre programme parlera à `http://localhost:11434`. Vérifiez que le serveur
répond :

- Ouvrez un **second** terminal et tapez :
  ```
  ollama serve
  ```
  *(si le serveur tourne déjà, Ollama vous le dira ; sinon il démarre)*

- Testez avec PowerShell :
  ```powershell
  Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get
  ```
  Vous devez voir la liste de vos modèles en JSON. ✔️

---

## 5. Étape 3 — Comprendre l'API d'un LLM

> ⏱️ 45 minutes | ✔️ Résultat : vous envoyez un JSON et vous lisez la réponse

Un LLM, c'est une **boîte noire HTTP** : on envoie un JSON, on reçoit un JSON.

### 5.1 Le message le plus simple

Copiez-collez ceci dans PowerShell (en remplaçant `bonjour` par ce que vous voulez) :

```powershell
$corps = @{
    model  = "llama3.2:latest"
    messages = @(
        @{ role = "system"; content = "Tu réponds en français, en une phrase." }
        @{ role = "user";   content = "Explique ce qu'est une variable en Python." }
    )
    stream = $false
} | ConvertTo-Json -Depth 5

$reponse = Invoke-RestMethod -Uri "http://localhost:11434/api/chat" `
                             -Method Post -Body $corps -ContentType "application/json"

$reponse.message.content
```

**Que voit-on ?**
- `messages` = la conversation (rôles `system`, `user`, `assistant`).
- Le `system` message = les consignes que le modèle suit en permanence.
- La réponse est un JSON dont on extrait `message.content`.

### 5.2 Le même appel, en Python (ce qui nous servira ensuite)

Créez un dossier `mon_agent` et un fichier `essai1.py` :

```python
# essai1.py — premier appel à un LLM local
import requests

reponse = requests.post(
    "http://localhost:11434/api/chat",
    json={
        "model": "llama3.2:latest",
        "messages": [
            {"role": "system", "content": "Tu réponds en une phrase, en français."},
            {"role": "user", "content": "Donne un exemple de fonction Python."},
        ],
        "stream": False,
    },
)
donnees = reponse.json()
print(donnees["message"]["content"])
```

Exécutez : `python essai1.py` ✔️

> 💡 **À retenir** : tout le travail d'un agent repose sur ce simple appel.
> On envoie des messages, on reçoit un message. La suite = des allers-retours
> entre votre code et cette API.

### 5.3 Exercice (à faire seul)

1. Modifiez `essai1.py` pour que le modèle soit « un professeur de mathématiques »
   et posez-lui une question de votre choix.
2. Ajoutez un second message `user` et observez : le modèle se souvient-il du
   premier échange ? *(Oui, car l'historique complet est renvoyé.)*
3. **Question** : pourquoi croit-on parfois qu'un chatbot « a de la mémoire »,
   alors qu'il ne stocke rien ? → *Parce que c'est NOUS qui lui renvoyons tout
   l'historique à chaque tour.*

---

## 6. Étape 4 — Le « tool calling »

> ⏱️ 1 heure | ✔️ Résultat : le modèle demande d'exécuter une fonction, vous l'exécutez

C'est **l'étape qui transforme un chatbot en agent**. Testons-la en direct.

### 6.1 Déclarer un outil au modèle

Un outil est décrit en JSON : son nom, son utilité, ses paramètres.

```python
# essai2.py — le modèle demande d'appeler une fonction
import requests
import json

outils = [
    {
        "type": "function",
        "function": {
            "name": "addition",
            "description": "Calcule la somme de deux nombres entiers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "integer", "description": "Premier nombre"},
                    "b": {"type": "integer", "description": "Second nombre"},
                },
                "required": ["a", "b"],
            },
        },
    }
]

reponse = requests.post(
    "http://localhost:11434/v1/chat/completions",   # notez /v1 : API compatible OpenAI
    json={
        "model": "llama3.2:latest",
        "messages": [
            {"role": "system", "content": "Utilise l'outil addition si besoin."},
            {"role": "user", "content": "Combien font 1234 + 5678 ?"},
        ],
        "tools": outils,
    },
)
message = reponse.json()["choices"][0]["message"]
print(json.dumps(message, indent=2, ensure_ascii=False))
```

**Résultat attendu** : le champ `tool_calls` contient la *demande* du modèle :

```json
"tool_calls": [
  { "function": { "name": "addition",
                  "arguments": "{\"a\": 1234, \"b\": 5678}" } }
]
```

> 🔑 **L'idée à 100 % de comprendre** : le modèle n'a **pas** fait le calcul.
> Il a renvoyé « je veux appeler `addition(1234, 5678)` ». **Vous** faites le
> calcul dans votre code, et vous lui renvoyez le résultat.

### 6.2 Exécuter l'outil et renvoyer le résultat

Complétez `essai2.py` :

```python
# --- Nous exécutons la demande du modèle ---
def addition(a: int, b: int) -> str:
    return f"{a} + {b} = {a + b}"

appel = message["tool_calls"][0]
args = json.loads(appel["function"]["arguments"])
resultat = addition(**args)

# --- Nous renvoyons le résultat au modèle ---
reponse2 = requests.post(
    "http://localhost:11434/v1/chat/completions",
    json={
        "model": "llama3.2:latest",
        "messages": [
            {"role": "system", "content": "Utilise l'outil addition si besoin."},
            {"role": "user", "content": "Combien font 1234 + 5678 ?"},
            message,                                   # la réponse avec tool_calls
            {"role": "tool",                           # le résultat de l'outil
             "tool_call_id": appel["id"],
             "content": resultat},
        ],
        "tools": outils,
    },
)
print("Réponse finale :",
      reponse2.json()["choices"][0]["message"]["content"])
```

**Résultat attendu** : `Réponse finale : 1234 + 5678 = 6812` ✔️

**Deux règles d'or de l'API, à mémoriser :**
1. Le message `assistant` qui contient `tool_calls` doit être **renvoyé tel quel**.
2. Chaque résultat d'outil est envoyé dans un message `role="tool"` portant le
   **même `tool_call_id`** que la demande.

### 6.3 Exercices (à faire seul)

1. Ajoutez un outil `soustrait` et demandez « 50 − 33 ».
2. Ajoutez un outil `bonjour` sans paramètre. Que renvoie le modèle ?
3. **Question** : à quoi sert la `description` d'un outil ? → *Le modèle s'en
   sert pour décider QUEL outil choisir. Plus elle est claire, mieux il choisit.*

---

## 7. Étape 5 — Construire votre agent

> ⏱️ 2 h 30 | ✔️ Résultat : un agent qui lit, écrit, exécute et teste du code

Nous allons maintenant construire un agent complet, **fichier par fichier**,
en réutilisant exactement les concepts vus aux étapes 3 et 4.

> ℹ️ Si vous êtes bloqué, le projet complet est fourni dans le dossier
> `agent-codage/` du cours — mais **copiez d'abord à la main** chaque fichier :
> c'est la meilleure façon d'apprendre. Résistez au copier-coller global.

### 7.1 Organiser votre projet

Dans `mon_agent/`, créez ces fichiers (noms imposés) :

```
mon_agent/
├── config.py     # les réglages
├── llm.py        # le client réseau vers le modèle
├── tools.py      # les outils (schémas + fonctions)
├── prompt.py     # le system prompt
├── agent.py      # la boucle
└── main.py       # l'interface terminal
```

### 7.2 `config.py` — les réglages

```python
# config.py — Tous les réglages au même endroit
import os

MODEL = os.environ.get("AGENT_MODEL", "llama3.2:latest")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
TEMPERATURE = 0.2

MAX_ITERATIONS = 25      # limite anti-boucle-infinie
BASH_TIMEOUT = 30        # secondes max pour une commande
MAX_READ_LINES = 400     # lignes max renvoyées par read_file

def api_url() -> str:
    """URL de l'endpoint compatible OpenAI."""
    return f"{OLLAMA_URL}/v1/chat/completions"
```

**Expliquons les choix :**
- `MAX_ITERATIONS` : chaque « tour d'outil » coûte un appel au modèle. On borne
  pour éviter qu'un modèle déraillé fasse 10 000 appels.
- La variable d'environnement permet de changer de modèle **sans éditer le code**.
- On cible l'endpoint `/v1/chat/completions` (format compatible OpenAI).

### 7.3 `llm.py` — le client réseau

C'est notre étape 5.2, industrialisée :

```python
# llm.py — Parler au modèle
import json
import requests
import config

def chat(messages, tools=None):
    """Envoie la conversation, renvoie le message de l'assistant."""
    payload = {
        "model": config.MODEL,
        "messages": messages,
        "temperature": config.TEMPERATURE,
    }
    if tools:
        payload["tools"] = tools          # on annonce les outils disponibles

    try:
        reponse = requests.post(config.api_url(), json=payload, timeout=300)
    except requests.ConnectionError:
        print("ERREUR : Ollama ne tourne pas. Lancez 'ollama serve'.")
        raise SystemExit(1)

    if reponse.status_code != 200:
        raise RuntimeError(f"Erreur HTTP {reponse.status_code}: {reponse.text}")

    return reponse.json()["choices"][0]["message"]


def parse_tool_calls(message):
    """Transforme les appels d'outils en liste de dicts Python."""
    result = []
    for appel in message.get("tool_calls") or []:
        fonction = appel["function"]
        brut = fonction.get("arguments", "{}")
        if isinstance(brut, str):          # "{"a":1}"  ->  {"a":1}
            args = json.loads(brut) if brut.strip() else {}
        else:
            args = brut
        result.append({
            "id": appel.get("id", ""),
            "name": fonction.get("name", ""),
            "arguments": args,
        })
    return result
```

**Points clés :**
- `chat()` retourne le message **tel que reçu** (format filaire) : on pourra le
  renvoyer tel quel dans l'historique (règle d'or n° 1).
- `parse_tool_calls()` convertit les arguments JSON en vrais dictionnaires Python.
- La gestion d'erreur est volontairement simple et lisible.

### 7.4 `tools.py` — les bras de l'agent

Deux parties : la **liste des schémas** (ce que le modèle voit) et les
**fonctions** (ce qui s'exécute).

```python
# tools.py — Les outils : schémas JSON + fonctions Python
import glob as globlib
import os
import subprocess
import config

# --- 1) Les schémas JSON (décrits au modèle) ---
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "Liste le contenu d'un répertoire.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lit un fichier, lignes numérotées.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Crée un fichier ou écrase son contenu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Exécute une commande du terminal (python, git...).",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]

# --- 2) Les fonctions Python (ce qui s'exécute) ---
def list_dir(path="."):
    if not os.path.isdir(path):
        return f"ERREUR: '{path}' n'est pas un dossier."
    return "\n".join(sorted(os.listdir(path)))


def read_file(path, offset=1, limit=None):
    limit = limit or config.MAX_READ_LINES
    if not os.path.isfile(path):
        return f"ERREUR: fichier introuvable: {path}"
    with open(path, encoding="utf-8", errors="replace") as fh:
        lignes = fh.readlines()[offset-1 : offset-1+limit]
    return "".join(f"{offset+i}: {l}" for i, l in enumerate(lignes))


def write_file(path, content):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return f"OK: {path} écrit."


def bash(command, timeout=None):
    timeout = timeout or config.BASH_TIMEOUT
    proc = subprocess.run(command, shell=True, capture_output=True,
                          text=True, timeout=timeout, encoding="utf-8",
                          errors="replace")
    sortie = proc.stdout + proc.stderr
    if len(sortie) > 4000:                    # on tronque pour protéger le contexte
        sortie = sortie[:4000] + "\n...[tronqué]"
    return f"$ {command} (code {proc.returncode})\n{sortie}".rstrip()


# --- Le dictionnaire qui relie nom d'outil -> fonction ---
EXECUTORS = {
    "list_dir": list_dir,
    "read_file": read_file,
    "write_file": write_file,
    "bash": bash,
}


def execute_tool(name, arguments):
    """Exécute un outil par son nom. Retourne toujours du texte."""
    if name not in EXECUTORS:
        return f"ERREUR: outil inconnu '{name}'."
    try:
        return EXECUTORS[name](**arguments)
    except TypeError as err:
        return f"ERREUR: mauvais arguments: {err}"
    except Exception as err:
        return f"ERREUR inattendue: {err}"
```

**À noter :**
- Les fonctions renvoient **du texte**, jamais d'objets : c'est ce texte que le
  modèle lira. Formatez-le bien (lignes numérotées, code de sortie…).
- `execute_tool` est le seul point d'entrée : l'agent ne peut exécuter QUE les
  outils que vous listez ici. C'est votre « périmètre de sécurité ».

### 7.5 `prompt.py` — le system prompt

C'est l'âme de l'agent. Le modèle le lit à chaque tour.

```python
# prompt.py — Le system prompt : la méthode de travail de l'agent
SYSTEM_PROMPT = """Tu es "Codeur", un agent logiciel expert dans un terminal.

## Méthode
1. EXPLORE  : liste et lis les fichiers concernés avant de coder.
2. PLANIFIE : explique brièvement ce que tu vas faire.
3. CODE     : crée/modifie les fichiers.
4. TESTE    : exécute et vérifie (bash: python, pytest...), corrige si erreur.

## Règles
- AGIS, ne raconte pas : utilise les outils pour faire le travail, puis écris
  ton texte final UNIQUEMENT quand la tâche est terminée et vérifiée.
- Lis toujours un fichier avant de le modifier.
- Si une commande échoue, lis l'erreur et corrige; ne simule jamais la réussite.
- Réponds en français, de façon concise et structurée.
"""


def build_messages(user_input, history=None):
    """Construit la liste de messages : system + historique + demande."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": user_input})
    return messages
```

> 🧪 **Expérience à montrer en classe** : retirez la ligne « AGIS, ne raconte
> pas ». Vous verrez le modèle *décrire* ce qu'il ferait… sans le faire. Ce
> simple prompt fait la différence entre un agent et un bavard.

### 7.6 `agent.py` — la boucle (le cœur)

Tout converge ici : une boucle qui tourne jusqu'à la réponse finale.

```python
# agent.py — La boucle : raisonner -> agir -> observer -> réessayer
import config
import llm
import tools
from prompt import build_messages


def run_agent(user_input, history=None, on_tool=None):
    """Exécute une demande complète. Retourne (réponse finale, historique)."""
    messages = build_messages(user_input, history)

    for etape in range(config.MAX_ITERATIONS):
        reponse = llm.chat(messages, tools=tools.TOOLS)
        messages.append(reponse)          # on conserve le message de l'assistant

        appels = llm.parse_tool_calls(reponse)
        if not appels:                    # le modèle répond en texte : fini !
            return reponse.get("content") or "(réponse vide)", messages

        for appel in appels:              # sinon on exécute les outils
            resultat = tools.execute_tool(appel["name"], appel["arguments"])
            if on_tool:
                on_tool(appel, resultat)  # affichage en direct (CLI)
            messages.append({
                "role": "tool",
                "tool_call_id": appel["id"],
                "content": resultat,      # on renvoie le résultat au modèle
            })

    return ("Limite d'itérations atteinte. Précisez votre demande."), messages
```

**Le diagramme de cette boucle (à recopier dans votre rapport) :**

```
Demande utilisateur
        │
        ▼
┌──► [1] Envoyer tous les messages au modèle
        │
        ▼
┌──► [2] Le modèle répond
        │
        ├── texte ──────────► RETOURNER ce texte (réponse finale)
        │
        └── appels d'outils
                │
                ▼
        [3] Exécuter chaque outil (votre code Python)
                │
                ▼
        [4] Ajouter les résultats au contexte
                └────────► retour au [1]
```

### 7.7 `main.py` — l'interface terminal

```python
# main.py — L'interface : on parle à l'agent dans le terminal
import os
import sys
import agent
import config

os.makedirs(config.WORKSPACE, exist_ok=True)
os.chdir(config.WORKSPACE)          # l'agent travaille ici

history = []                        # mémoire de la session

def afficher_outil(appel, resultat):
    print(f"  [outil] {appel['name']}({appel['arguments']})")
    for ligne in resultat.splitlines()[:6]:
        print(f"    {ligne}")

def main():
    print(f"Agent de codage — {config.MODEL}")
    while True:
        try:
            saisie = input("vous> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if saisie in ("/quit", "/exit"):
            break
        if saisie == "/new":
            history.clear()
            print("Mémoire effacée.")
            continue
        if not saisie:
            continue
        final, updated = agent.run_agent(saisie, history, on_tool=afficher_outil)
        history[:] = updated
        print(f"codeur> {final}\n")

if __name__ == "__main__":
    main()
```

### 7.8 Test final obligatoire

Lancez l'agent, puis donnez-lui cette tâche **exactement** :

```
Crée un fichier calcul.py contenant une fonction factorielle(n),
puis ajoute un test qui vérifie que factorielle(5) == 120,
et exécute ce test avec python. Corrige les erreurs si nécessaire.
```

✔️ **Vous devez voir** : l'agent utilise `write_file`, puis `bash`, exécute le
test, et vous donne un résumé en français. S'il se trompe, il se corrige seul.

> 🧪 **Pour tester les limites de votre agent** : demandez-lui de faire quelque
> chose qu'il ne peut pas (ex. « envoie un courriel »). Observez : il va
> s'expliquer, ou tenter un outil. Discussion : comment lui donner ce nouveau
> pouvoir ? *(Réponse : écrivez une fonction `envoyer_courriel` et ajoutez-la à
> `TOOLS` et à `EXECUTORS`.)*

### 7.9 Exercice bonus — ajoutez un outil `editer`

Le modèle écrit tout un fichier à chaque fois. Ajoutez l'outil **`edit_file`** :

- Schéma : `path`, `old_string` (texte exact à trouver), `new_string`.
- Fonction : lisez le fichier, vérifiez que `old_string` y figure **une seule
  fois** (sinon renvoyez une erreur explicite au modèle), remplacez, écrivez.
- Ajoutez-le à `TOOLS` et à `EXECUTORS`.

> 💡 **Pourquoi vérifier « une seule fois » ?** C'est une vraie technique de
> sécurité des agents : un remplacement ambigu doit être refusé, pas deviné.

### 7.10 Exercice bonus — `read_document` : lire un document Word/PDF/Excel/PowerPoint

Un agent qui ne sait lire que du code est **aveugle à vos cours**. Or un
`.docx` est un **ZIP** (du XML à l'intérieur) et un `.pdf` contient des **flux
compressés** — la bibliothèque standard Python suffit : `zipfile` et `zlib`,
**aucune dépendance en plus**.

Ajoutez le schéma à `TOOLS` :

```python
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Extrait le TEXTE lisible d'un document : Word "
                           "(.docx), PowerPoint (.pptx), Excel (.xlsx), "
                           "PDF (.pdf) ou fichier texte.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
```

Puis les fonctions (version simplifiée — la version complète, avec gestion des
accents CP1252 et de PowerPoint/Excel, est dans `agent-codage/tools.py`) :

```python
import re
import zipfile
import zlib

def _xml_to_text(xml):
    """Transforme du XML Word en texte lisible (balises retirées)."""
    texte = re.sub(r"</w:p>", "\n", xml)     # fin de paragraphe -> ligne
    texte = re.sub(r"<[^>]+>", "", texte)    # on retire les balises
    return texte.strip()


def _extrait_pdf(chemin):
    """Décompresse les flux texte d'un PDF et recolle les mots découpés."""
    with open(chemin, "rb") as fh:
        donnees = fh.read()
    lignes = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", donnees, re.DOTALL):
        try:
            brut = zlib.decompress(m.group(1), -15)   # -15 = deflate brut
        except zlib.error:
            continue
        for morceau in brut.decode("latin1").split("Td"):
            ops = re.findall(r"\((.*?)\)\s*Tj", morceau)
            if ops:
                lignes.append("".join(ops))
    return "\n".join(lignes)


def read_document(path):
    """Extrait le texte d'un document selon son extension."""
    if not os.path.isfile(path):
        return f"ERREUR: fichier introuvable: {path}"
    ext = path.split(".")[-1].lower()
    if ext == "docx":
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        return _xml_to_text(xml)
    if ext == "pdf":
        return _extrait_pdf(path)
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()
```

Ajoutez-le à `EXECUTORS`, puis testez en session :

```
Résume ce document : C:\Cours\plan_cours.docx
```

> 🧪 **Limite honnête à discuter** : un PDF **numérisé** (une image scannée)
> ne contient pas de texte à extraire. C'est pour ça qu'il existe l'OCR.
> Demandez à votre agent de résumer un PDF numérisé et observez sa réponse.

### 7.11 Exercice bonus — `search_in_files` : trouver où un mot est utilisé

L'outil préféré des développeurs : « où est utilisé `config` ? ». Il retourne
exactement `fichier:n°ligne: contenu` — comme le font `grep` et les bons éditeurs.

Ajoutez le schéma à `TOOLS` :

```python
    {
        "type": "function",
        "function": {
            "name": "search_in_files",
            "description": "Recherche un mot ou une expression dans tous les "
                           "fichiers texte d'un dossier (récursif). Retourne "
                           "les fichiers et les NUMÉROS DE LIGNE correspondants.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "Dossier à parcourir (défaut: .)"},
                    "term": {"type": "string", "description": "Mot ou expression à chercher"},
                },
                "required": ["term"],
            },
        },
    },
```

Puis la fonction :

```python
IGNORES = {"node_modules", ".git", "__pycache__"}   # dossiers à ignorer

def search_in_files(term, folder="."):
    """Cherche `term` (insensible à la casse). Retourne fichier:n°ligne: contenu."""
    resultats = []
    for racine, dossiers, fichiers in os.walk(folder):
        dossiers[:] = [d for d in dossiers if d not in IGNORES]
        for nom in fichiers:
            chemin = os.path.join(racine, nom)
            try:
                with open(chemin, encoding="utf-8", errors="replace") as fh:
                    lignes = fh.readlines()
            except OSError:
                continue                        # fichier illisible : on ignore
            for i, ligne in enumerate(lignes, 1):
                if term.lower() in ligne.lower():
                    resultats.append(f"{chemin}:{i}: {ligne.strip()}")
                    if len(resultats) >= 100:   # on protège le contexte du modèle
                        break
            if len(resultats) >= 100:
                break
        if len(resultats) >= 100:
            break
    return "\n".join(resultats) or f"Aucune occurrence de '{term}'."
```

Ajoutez-le à `EXECUTORS`, puis testez en session :

```
Où est utilisé "config" dans mon projet ? Donne les fichiers et les lignes.
```

> 💡 **Pourquoi la limite de 100 résultats ?** Chaque caractère renvoyé au
> modèle occupe de la « place » dans son contexte. Un outil bien conçu
> protège le contexte : on borne les résultats et on les trie par pertinence.

### 7.12 Bonus — l'interface web `web.py` : parler à l'agent depuis un navigateur

Le terminal (`main.py`) est très bien… pour vous. Pour qu'**une personne sans
accès au code** pose des questions à votre agent, servez-le sur le **web** :
`http.server` (bibliothèque standard) suffit, zéro dépendance.

Créez `public/index.html` (une simple page de chat : un champ de saisie, une
liste de messages, et un `fetch` vers `/api/chat`), puis ce serveur :

```python
# web.py — La même boucle d'agent, servie en HTTP pour un navigateur
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import agent
import config

os.makedirs(config.WORKSPACE, exist_ok=True)
os.chdir(config.WORKSPACE)          # l'agent travaille dans son espace

sessions = {}                       # id de navigateur -> historique

class Interface(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass                        # on garde la console propre

    def do_GET(self):
        if self.path == "/":
            page = open(os.path.join(os.path.dirname(__file__),
                                     "public", "index.html"),
                        encoding="utf-8").read()
            page = page.replace("__MODEL__", config.MODEL)
            self.envoyer(200, page, "text/html; charset=utf-8")
            return
        self.envoyer(404, "Introuvable.", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path == "/api/chat":
            longueur = int(self.headers.get("Content-Length", 0))
            message = json.loads(self.rfile.read(longueur)).get("message", "")
            sid = self.cookies()                # chaque navigateur a sa session
            historique = sessions.setdefault(sid, [])
            trace = []
            final, historique = agent.run_agent(
                message, historique,
                on_tool=lambda c, r: trace.append({"outil": c["name"], "resultat": r}))
            sessions[sid] = historique
            self.envoyer(200, json.dumps({"response": final, "tools": trace},
                                         ensure_ascii=False),
                         "application/json; charset=utf-8")
            return
        self.envoyer(404, "Introuvable.", "text/plain; charset=utf-8")

    def cookies(self):
        """Le cookie identifie le navigateur : sa mémoire de session."""
        cookie = self.headers.get("Cookie", "")
        sid = next((p.split("=", 1)[1] for p in cookie.split("; ")
                    if p.strip().startswith("session=")), None)
        if sid and sid in sessions:
            return sid
        sid = os.urandom(8).hex()               # nouveau navigateur
        sessions[sid] = []
        self._nouveau_cookie = f"session={sid}; Path=/"
        return sid

    def envoyer(self, statut, contenu, type_mime):
        corps = contenu.encode("utf-8") if isinstance(contenu, str) else contenu
        self.send_response(statut)              # la ligne de statut EN PREMIER
        self.send_header("Content-Type", type_mime)
        self.send_header("Content-Length", str(len(corps)))
        if getattr(self, "_nouveau_cookie", None):
            self.send_header("Set-Cookie", self._nouveau_cookie)
            self._nouveau_cookie = None
        self.end_headers()
        self.wfile.write(corps)

ThreadingHTTPServer(("127.0.0.1", 3000), Interface).serve_forever()
```

Lancez `python web.py`, ouvrez `http://127.0.0.1:3000` : votre agent est
utilisable **par n'importe qui**, sans éditeur. Fichiers hors du dossier ?
Donnez le chemin absolu : « Explique `C:\Cours\agent.py` ».

> ⚠️ **Sécurité (à discuter en classe)** : le serveur n'écoute QUE sur
> `127.0.0.1` (votre machine). Pour l'ouvrir au réseau local (salle de
> classe) : `AGENT_HOST=0.0.0.0 python web.py` — mais alors toute la classe
> peut utiliser vos outils, **dont `bash`**. Jamais sur Internet public.

> 🖱️ **Démo sans éditeur** : le fichier `demarrer-agent.bat` (à la racine du
> projet) permet à un enseignant non informaticien de lancer l'agent en
> **double-cliquant** : il démarre Ollama si besoin, lance `python web.py` et
> ouvre le navigateur sur `http://127.0.0.1:3000`. Rien ne passe par Internet
> à la démo — le modèle est local. (GitHub ne peut pas héberger l'agent : son
> cerveau et ses outils travaillent sur le disque local.)

#### En bonus — le streaming : la réponse apparaît au fil de l'eau

Avec le serveur ci-dessus, le navigateur attend la réponse **complète** avant
d'afficher quoi que ce soit : avec un modèle lent sur CPU, l'écran reste figé
30 à 90 secondes. On peut faire beaucoup mieux : **diffuser** la réponse
morceau par morceau, comme ChatGPT.

L'idée : demander `stream: true` au serveur LLM (il répond alors en SSE,
`data: {...}` par morceau), et renvoyer chaque morceau au navigateur dès qu'il
arrive.

1. **Côté modèle** — dans `llm.py`, une variante de `chat()` qui diffuse :
   ```python
   def chat_stream(messages, tools=None, on_delta=None):
       payload = {**base_payload, "stream": True}   # SSE demandé
       response = requests.post(config.api_url(), json=payload, stream=True)
       for ligne in response.iter_lines(decode_unicode=True):
           if not ligne.startswith("data:"):
               continue
           if ligne[5:].strip() == "[DONE]":
               break
           delta = json.loads(ligne[5:])["choices"][0]["delta"]
           texte = delta.get("content")
           if texte and on_delta:
               on_delta(texte)          # chaque morceau est transmis à l'appelant
       ...
   ```
2. **Côté agent** — dans `agent.py`, `run_agent_stream()` est la même boucle
   que `run_agent()`, mais chaque appel passe par `chat_stream` et transmet les
   morceaux.
3. **Côté serveur** — dans `web.py`, répondre avec
   `Content-Type: text/event-stream` puis envoyer un `data: {...}` par morceau
   (et `data: [DONE]` à la fin). La page web lit le flux avec
   `response.body.getReader()` et remplit la bulle en direct.

**Test** : relancez `python web.py`, demandez une réponse longue (« résume le
chapitre sur les boucles »). La réponse apparaît **au fil de l'eau** au lieu
d'un écran figé. Bonus : les outils utilisés s'affichent aussi en direct
(`🔧 write_file(...)`).

> 📡 **Le streaming est déjà intégré dans le `web.py` fourni en correction** :
> les fonctions `chat_stream`, `run_agent_stream` et les en-têtes SSE y sont
> présents. Ajouter le streaming est par ailleurs **l'exigence EXIG-8** de la
> version TypeScript (`agent-codeur-ts`).

### 7.13 Bonus — la porte de décision : répondre sans outils

Votre agent fonctionne. Posez-lui pourtant cette question innocente :

> « Donne-moi le code pour lire un fichier PDF »

Surprise : au lieu de répondre, il part **explorer le disque** pendant des
minutes, à la recherche d'un PDF qui n'a rien à voir. Pourquoi ? Parce qu'on
lui a annoncé des outils — et il a envie de les utiliser.

> 💡 **L'idée** : si la demande n'a pas besoin d'outils, on n'en annonce
> **AUCUN** au modèle. Sans outils dans la requête, il lui est *techniquement
> impossible* d'en appeler : la seule chose qu'il peut faire, c'est répondre en
> texte. Problème de recherche infinie réglé, par construction.

#### Le code (à ajouter dans `agent.py`)

```python
# agent.py — la porte de décision : certains messages n'ont pas besoin d'outils

DEMANDES_SANS_OUTILS = (
    "donne-moi le code", "donnez-moi le code",          # « donne le code »
    "le code en", "du code en", "un code en",            # « le code en python »
    "comment lire", "comment écrire", "comment créer",   # « comment faire X ? »
    "comment fonctionne", "c'est quoi", "qu'est-ce que", # demandes d'explication
    "explique-moi", "expliquez-moi", "explique",         # « explique-moi ce code »
    "expliquer", "explain", "à quoi sert", "a quoi sert",# demandes d'explication
)


def est_demande_de_code(demande):
    """Vrai si l'utilisateur veut du code ou une explication (pas une action)."""
    texte = demande.lower()
    return any(mot in texte for mot in DEMANDES_SANS_OUTILS)


def run_agent(user_input, history=None, on_tool=None):
    messages = build_messages(user_input, history)

    if est_demande_de_code(user_input):
        # On n'annonce AUCUN outil : le modèle ne peut pas chercher de fichier.
        messages[-1] = {
            **messages[-1],
            "content": ("L'utilisateur veut du code ou une explication. "
                        "Réponds DIRECTEMENT avec le code demandé et une courte "
                        "explication. Ne cherche aucun fichier, n'exécute rien.")
        }
        reponse = llm.chat(messages)     # sans tools=... : réponse immédiate
        messages.append(reponse)
        return reponse.get("content") or "(réponse vide)", messages

    # ... votre boucle habituelle de la section 7.6 continue ici
```

#### Pourquoi ça marche ?

1. **`est_demande_de_code()`** est une simple détection de mots-clés : si la
   phrase ressemble à une question de méthode, on bascule en mode « réponse
   directe ».
2. **`llm.chat(messages)` sans `tools=`** : la requête envoyée au modèle ne
   contient *aucune* définition d'outil. Il ne peut donc pas produire d'appels
   d'outils — il n'a d'autre choix que de répondre en texte.
3. Le code demandé est **toujours donné**, même si le fichier n'existe pas :
   on répond à la question posée, on ne part pas à l'aventure.

#### Test final

1. « Donne-moi le code en python pour lire un PDF » → l'agent répond
   **immédiatement** avec un exemple `PyPDF2`, sans aucune ligne `[outil]`.
2. « Expliquez-moi ce code, puis ceci est une fonction TypeScript… » → l'agent
   **explique pédagogiquement** (rôle de chaque partie, termes techniques,
   exemple simple) sans chercher de fichier : la liste des mots-clés couvre
   aussi « explique », « expliquer », « explain », « à quoi sert »…
3. « Et ce code <coller> » (suite de l'explication) → l'agent **continue
   d'expliquer** sans outils : les marqueurs de continuation (« ce code »,
   « ce script », « cette fonction »…) déclenchent aussi la porte, **sauf** si
   un verbe d'action est présent.
4. « Corrige ce code » → un verbe d'action (« corrige ») est détecté : la
   porte reste **ouverte aux outils**, c'est une action à réaliser.
5. « Crée un fichier `calcul.py` puis exécute-le » → l'agent utilise toujours
   `write_file` et `bash` : les **actions réelles ne sont pas bloquées**.

#### Discussion (limites)

- La détection est **par mots-clés** : elle n'est pas parfaite. « Corrige le
  code de `hello.py` » ne matchera aucun mot-clé → l'agent agira, ce qui est le
  bon comportement (il y a une action à faire).
- Les suites d'explication (« et ce code… ») sont traitées **sauf** si un
  verbe d'action apparaît : une petite liste `ACTION_VERBS` (corrige, exécute,
  modifie, lance, teste, supprime…) sert de garde-fou. C'est un compromis :
  « lis ce code » → explication, « exécute ce code » → action.
- Un **petit modèle peut parfois répondre en JSON d'appel d'outil**
  (`{"name": ..., "parameters": ...}`) même en mode direct : il imite la
  signature de la fonction collée. La correction ajoute un **filet de
  sécurité** : si la réponse commence par `{` et ressemble à un JSON d'outil,
  l'agent refait une demande (« réponds en texte normal »), au plus une fois.
- Améliorations possibles : une expression régulière plus riche, ou un second
  appel au modèle pour **classer** la demande (« est-ce une action ou une
  question ? ») avant de choisir la voie.

---

## 8. Étape 6 — Créez votre propre agent

> ⏱️ 2 à 3 heures | ✔️ Résultat : VOTRE agent, présenté en classe

Vous allez maintenant créer **votre propre agent**, en partant de votre code.
Choisissez **un** projet parmi ceux-ci (ou proposez le vôtre à l'enseignant).

### Projet A — L'agent « correcteur d'exercices »
**Outils** : `read_file`, `bash`, `write_file`.
**Comportement** : vous lui donnez un programme Python (avec une erreur), il
exécute, lit l'erreur, corrige le fichier et explique ce qui n'allait pas.
**Livrable** : 3 programmes à corriger fournis + la correction expliquée.

### Projet B — L'agent « générateur de mini-jeux »
**Outils** : `write_file`, `bash`.
**Comportement** : il crée un mini-jeu jouable en terminal (devinette, pendu,
nombre mystère) **sans interface graphique**, puis le lance pour vérifier.
**Livrable** : 2 jeux fonctionnels + capture d'écran du fonctionnement.

### Projet C — L'agent « résumeur de projets »
**Outils** : `list_dir`, `read_file`, `read_document` (bonus 7.10), `write_file`.
**Comportement** : il explore un dossier de code **ou un document de cours**
(`.docx`/`.pdf`) et rédige `RESUME.md` : architecture, fichiers importants,
fonctionnement général.
**Livrable** : appliqué à un projet existant (le vôtre ou un exemple fourni).

### Projet D — L'agent « rapport de laboratoire »
**Outils** : `bash`, `write_file`, `read_file`.
**Comportement** : il exécute une série d'expériences de votre choix, collecte
les sorties, et rédige un rapport structuré en français (hypothèse, résultats,
conclusion) dans `rapport.md`.
**Livrable** : le rapport généré + la transcription de l'exécution.

### Exigences communes (quel que soit le projet)

1. **Repartez de votre code** de l'étape 5. Adaptez `SYSTEM_PROMPT` au rôle de
   votre agent.
2. Ajoutez **au moins un outil personnel** (dont l'idée n'est pas déjà dans les
   outils du cours) ou une variante utile.
3. Votre agent doit **tester lui-même** son travail avant de conclure.
4. Rédigez un **rapport** (2-3 pages) contenant :
   - Le rôle de votre agent et son system prompt.
   - Le diagramme de la boucle adapté à votre projet.
   - Une **démonstration** : transcription d'une session réelle avec votre agent.
   - Une **limite** constatée et une amélioration envisagée.
5. **Présentation** : 5 minutes en classe, démo à l'écran.

---

## 9. Grille d'évaluation

| Critère | Détail | Points |
|---|---|---|
| Fonctionnement | L'agent répond et utilise les outils correctement | /20 |
| Tool calling | Outils bien déclarés (schémas) et bien exécutés | /15 |
| Boucle agent | Historique correct, pas de boucle infinie, gestion d'erreurs | /15 |
| Outil personnel | Outil ajouté, utile, décrit et testé | /15 |
| System prompt | Rôle clair, règles efficaces, adaptation au projet | /10 |
| Rapport | Structure, diagramme, démo réelle, limite + amélioration | /15 |
| Présentation | Clarté, démo qui fonctionne, réponses aux questions | /10 |
| **Total** | | **/100** |

---

## 10. Dépannage

| Problème | Solution |
|---|---|
| `python` n'est pas reconnu | Réinstallez Python en cochant « Add to PATH » |
| `ollama --version` échoue | L'app Ollama doit être installée ET lancée |
| « connection refused » | Le serveur ne tourne pas : `ollama serve` |
| « model not found » | `ollama pull llama3.2:latest` (ou `ollama pull qwen2.5:latest` pour une prose plus soignée) |
| Accents affichés `�` (Windows) | `set PYTHONIOENCODING=utf-8` avant `python main.py` |
| Le modèle ne s'arrête pas de boucler | Baissez `MAX_ITERATIONS` ou clarifiez le prompt ; ajoutez la porte de décision (7.13) |
| L'agent explore le disque au lieu de répondre à une question de code | Ajoutez la porte de décision (7.13) : il répond alors sans outils |
| Le modèle ne veut pas utiliser d'outil | Décrivez mieux les outils ; ajoutez « utilise les outils fournis » au prompt |
| Le modèle invente un fichier existant | Règle du prompt : « lis d'abord » ; les erreurs doivent remonter au modèle |
| Un `.docx` est lu comme du charabia | C'est un fichier binaire ZIP : utilisez l'outil `read_document` (7.10) |
| Le modèle cherche « où est utilisé X ? » sans succès | Ajoutez l'outil `search_in_files` (7.11) qui retourne fichiers + lignes |
| On veut un accès depuis un navigateur | Ajoutez `web.py` (7.12) : l'agent tourne sur http://127.0.0.1:3000 |

---

## 11. Pour aller plus loin

- **Changer de fournisseur sans changer de code** : l'API « compatible OpenAI »
  signifie que remplacer `OLLAMA_URL` par `https://api.openai.com/v1` (avec une
  clé) fonctionne… mais coûte de l'argent. Comparer local vs cloud.
- **Mémoire longue** : sauvegarder l'historique dans un fichier JSON pour
  reprendre une session plus tard.
- **Retrieval** : faire lire à l'agent un gros document (mode RAG).
- **Interface web** : servez votre agent sur `http://localhost` (bonus 7.12)
  pour que d'autres l'utilisent dans un navigateur, sans toucher au code.
- **Agents multi-outils avancés** : planification en deux phases
  (plan d'abord, exécution ensuite).
- **Sécurité** : faire tourner l'agent dans un dossier « bac à sable » ou une
  machine virtuelle, limiter les commandes `bash` autorisées.
- **Éthique** : que se passe-t-il si on demande une action destructrice ?
  Discuter des garde-fous (votre agent ne supprime rien sans confirmation).

---

*Bon TP ! Souvenez-vous : un agent IA, ce n'est pas de la magie — c'est une
boucle Python, des fonctions que vous écrivez, et un modèle qui choisit
quelle fonction appeler.*
