# Agent de codage pédagogique — « Codeur »

Un **agent IA de codage** complet, en **Python**, fonctionnant sur **Ollama**
(modèle local et gratuit). Construit pour être montré de A à Z en classe :
chaque fichier correspond à un concept précis, et le code est volontairement
court et commenté.

Il sait lire/écrire/modifier des fichiers, chercher des fichiers, exécuter des
commandes, voir le résultat, puis **continuer seul** jusqu'à terminer la tâche
— c'est exactement le principe d'un agent comme *opencode*, *Cline*, *Copilot*…

---

## Démarrage rapide (pour l'enseignant ou l'étudiant)

```bash
# 1. Installer Ollama (une fois) : https://ollama.com  puis:
ollama pull llama3.2:latest   # défaut : tool-calling fiable pour les calculs (SymPy)
#    (qwen2.5:latest = plus éloquent mais saute les calculs par outils)
# 2. Lancer le serveur Ollama (l'app le fait automatiquement)
ollama serve

# 3. Installer la dépendance du projet
pip install requests

# 4. Lancer l'agent
python main.py
```

Puis tapez, par exemple :

```
Crée un script Python qui affiche les 20 premiers nombres de Fibonacci,
puis exécute-le pour vérifier qu'il fonctionne.
```

Vous verrez l'agent **explorer → planifier → coder → tester** en direct,
outil par outil.

## Interface web (local)

Même agent, mais accessible depuis un **navigateur** : une personne qui n'a
pas accès à l'éditeur peut poser ses questions au Codeur sans toucher au code.

```bash
python web.py        # démarre le serveur sur http://127.0.0.1:3000
```

Ouvrez `http://127.0.0.1:3000` : page de chat avec historique, trace des
outils utilisés (🔧) et bouton « Nouvelle session ». Zéro dépendance en plus :
tout vient de la bibliothèque standard (`http.server`, `http.cookies`).

- **Chaque navigateur a sa propre session** (cookie + mémoire serveur).
- **Fichiers hors du dossier** : fonctionne — donnez simplement le chemin
  absolu, ex. « Explique `C:\Cours\agent.py` ».
- **Réseau local (salle de classe)** : pour que d'autres postes se connectent,
  lancez `AGENT_HOST=0.0.0.0 python web.py` et ouvrez `http://IP-du-poste:3000`.
  ⚠️ Cela expose aussi les outils (dont `bash`) — à réserver à une classe de
  confiance, jamais sur Internet public.
- Réglages : `AGENT_PORT` (défaut `3000`), `AGENT_HOST` (défaut `127.0.0.1`).

### Lancement sans éditeur (pour l'enseignant en classe)

**Double-cliquez sur `demarrer-agent.bat`** : le script démarre Ollama s'il ne
tourne pas, lance `python web.py` et ouvre automatiquement
`http://127.0.0.1:3000` dans le navigateur. Aucun éditeur, aucune commande,
**aucun Internet nécessaire** au moment de la démo (le modèle et les documents
sont sur la machine).

> GitHub ne peut pas héberger cet agent : son « cerveau » (Ollama) et ses
> outils travaillent sur le **disque local** de la machine qui le fait tourner.
> GitHub sert à **distribuer** le code source ; pour la démo, on copie le
> dossier sur le poste (Python + Ollama installés) et on double-clique.

### Installer sur un autre ordinateur (poste étudiant, salle de classe)

Pour faire tourner l'agent sur un autre PC, il faut y mettre le code **une
fois**, puis lancer l'installation **une fois** ; ensuite l'agent tourne
**sans Internet**.

**Option A — via GitHub** (après avoir mis le code sur votre compte GitHub) :
```bash
git clone https://github.com/votre-compte/agent-codage.git
cd agent-codage
installer.bat        # une seule fois : Python, Ollama, modèle, requests
demarrer-agent.bat   # à chaque fois : serveur + navigateur
```

**Option B — via un fichier ZIP** (Teams, clé USB, courriel) :
1. Compressez le dossier `agent-codage` en `.zip` (sans `__pycache__`).
2. Transférez-le, décompressez-le sur l'autre poste.
3. Double-cliquez sur `installer.bat` (une seule fois), puis `demarrer-agent.bat`.

> ℹ️ L'installation demande Internet **une seule fois** (téléchargement du
> modèle, ~2 Go). L'**utilisation** ensuite est 100 % hors ligne.

**Option C — exécutable autonome `Codeur.exe`** (aucun Python, aucun terminal) :
1. Copiez `dist\Codeur.exe` (ou `Codeur-etudiant.zip`) sur le poste.
2. Double-cliquez : la première fois, il **installe tout seul** Ollama
   (~1,6 Go) + le modèle (~2 Go), puis crée une **icône « Codeur » sur le
   bureau**.
3. Ensuite, on lance l'agent en double-cliquant sur l'icône, comme une
   application normale — chaque lancement vérifie seulement que tout est là
   (aucune réinstallation).

Reconstruire l'exécutable après une modification de l'agent :
`creer-executable.bat` (un double-clic, PyInstaller requis une fois).

### Modèles recommandés (selon la machine)

| Modèle | Taille | Pourquoi |
|---|---|---|
| `llama3.2:latest` | ~2 Go | **Défaut** : tool-calling fiable, calcule et vérifie réellement (SymPy : intégrales, dérivées, équations), ~14 tok/s CPU |
| `qwen2.5:latest` | ~4,7 Go | Belle prose, bons fichiers, MAIS saute les appels d'outil de calcul (réponse vide) |
| `gemma2:9b` | ~6 Go | Très bon niveau de langue, à télécharger, plus lent |
| `llava:7b` | ~4,7 Go | **Vision** : lit les images/captures d'écran (auto-installé par `Codeur.exe`, sautable) |

Changer de modèle : variable d'environnement `AGENT_MODEL`, ou éditer `config.py`.

---

## Architecture : un agent, c'est 5 idées

```
agent-codage/
├── main.py        # 6. INTERFACE  : le terminal où l'on parle à l'agent
├── web.py         #    INTERFACE  : le serveur HTTP (interface web) 🆕
├── agent.py       # 4. BOUCLE     : le cycle "raisonner puis agir"
├── llm.py         # 2. RÉSEAU     : le client HTTP vers le modèle
├── tools.py       # 3. OUTILS     : schémas JSON + implémentations Python
├── dessin.py      #    IMAGES     : illustrations locales (Pillow) 🆕
├── prompt.py      # 1. PERSONNALITÉ : le system prompt (règles de travail)
├── config.py      # 0. RÉGLAGES   : modèle, URL, limites de sécurité
└── public/
    └── index.html #    page de chat servie par web.py 🆕
```

### 0. `config.py` — les réglages
Modèle, URL du serveur, température, limites (nb max d'itérations, timeout des
commandes). Le « tableau de bord » du projet.

### 1. `prompt.py` — le system prompt
Un texte lu par le modèle à chaque tour. C'est **l'ingrédient le plus
important** : il définit la méthode (explorer → planifier → coder → tester)
et les règles. Deux consignes clés pour un agent codeur fiable :
> « AGIS, ne raconte pas » et « VÉRIFIE ton travail en exécutant du code ».

### 2. `llm.py` — le client réseau
Un simple `POST` JSON vers `/v1/chat/completions` (le même format que l'API
ChatGPT). C'est volontairement **sans SDK officiel** pour que les étudiants
voient la mécanique HTTP : `requests.post(url, json={model, messages, tools})`.

Deux fonctions importantes :
- `chat()` → renvoie le message de l'assistant, *tel quel* (format filaire),
  pour pouvoir le ré-injecter dans l'historique.
- `parse_tool_calls()` → transforme les appels d'outils du JSON en dictionnaires
  Python exploitables.

### 3. `tools.py` — les outils
Chaque outil = **schéma JSON** (ce que le modèle voit : nom, description,
paramètres) + **fonction Python** (ce qui s'exécute réellement).

| Outil | Rôle |
|---|---|
| `list_dir` | explorer un dossier |
| `read_file` | lire un fichier (lignes numérotées, refuse les binaires) |
| `read_document` | extraire le texte de **Word (.docx), PowerPoint (.pptx), Excel (.xlsx), PDF (.pdf)** et fichiers texte |
| `search_in_files` | chercher un mot/expression dans un dossier → `fichier:n°ligne: contenu` |
| `count_occurrences` | compter **exactement** (mots entiers, sans casse) combien de fois un mot apparaît dans un fichier |
| `write_file` | créer / écraser un fichier |
| `edit_file` | remplacer une portion exacte |
| `glob` | trouver des fichiers par motif |
| `bash` | exécuter une commande (python, git, pytest…) |
| `read_image` | décrire une image + transcrire son texte (vision ou OCR) |
| `generer_image` | générer une image : Stable Diffusion local si présent, sinon illustration locale (graphiques, schémas, mind-maps) 🆕 |
| `creer_powerpoint` | créer un `.pptx` de cours : puces, notes, images, liens vidéo 🆕 |

> Les formats Office sont des **ZIP** (`zipfile`), les PDF des **flux déflatés**
> (`zlib`) : tout vient de la bibliothèque standard, zéro dépendance. Limite
> connue : un PDF **numérisé** (image) n'a pas de texte à extraire.
> `creer_powerpoint` utilise **python-pptx** (seule dépendance ajoutée, hors ligne).

### 4. `agent.py` — la boucle ReAct
Le cœur. Une simple boucle `for` :

```
envoyer les messages au modèle
   └─ le modèle répond …
      ├─ en texte        → c'est la réponse finale, on s'arrête
      └─ avec des outils → exécuter chaque outil
                           renvoyer les résultats au modèle
                           RETOUR en haut de la boucle
```

Sécurisé par `MAX_ITERATIONS` (anti boucle infinie). L'historique complet est
conservé : l'agent a une mémoire de session.

### 5. `main.py` — l'interface terminal
Boucle de saisie interactive, affichage coloré des outils en direct,
commandes `/quit`, `/new` (efface la mémoire), `/model`, `/help`.

### 6. `web.py` — l'interface web 🆕
Le **même agent** servi sur HTTP (`http.server` de la bibliothèque standard).
Chaque navigateur reçoit un cookie = sa propre mémoire de session. La page
(`public/index.html`) appelle deux endpoints : `POST /api/chat`
(demande → réponse + trace des outils) et `POST /api/reset` (nouvelle session).
On peut l'utiliser en parallèle du terminal : les deux ne partagent pas la
même mémoire, c'est par design.

**Pièces jointes** : le bouton 📎 (ou un glisser-déposer, ou un copier-coller
de capture d'écran avec **Ctrl+V**) envoie des fichiers
et des images avec la question. Ils sont sauvegardés dans `uploads/<session>/`
et l'agent les lit avec ses outils. Pour les **images**, l'ordre des moyens
disponibles (100 % hors ligne) est :
1. le modèle de vision **`llava:7b`, téléchargé automatiquement au premier
   lancement** de `Codeur.exe` (sautable avec `CODEUR_NO_VISION=1`) ;
2. sinon l'OCR Tesseract (`pytesseract` + `Pillow`), s'il est installé ;
3. sinon un message honnête — l'agent ne devine **jamais** le contenu d'une image.

**Génération d'images** (`generer_image`, hors ligne) : moteurs testés dans
l'ordre — (1) Stable Diffusion déjà lancé sur le poste (ComfyUI / Automatic1111,
via `AGENT_SD_URL`), (2) `stable-diffusion.cpp` + modèle (`AGENT_SDCPP` +
`AGENT_SD_MODEL`), (3) sinon **illustrations locales** (graphiques en barres ou
en secteurs, organigrammes, mind-maps, tableaux de comparaison, formules) —
toujours disponibles sur CPU. L'agent rapporte honnêtement le moteur utilisé.

**PowerPoint de cours** (`creer_powerpoint`) : l'enseignant décrit son cours,
l'agent construit le plan JSON et génère le `.pptx` avec puces, notes, images
réelles et liens vidéo cliquables. Les URLs de vidéo ne sont **jamais**
inventées : seuls les liens fournis sont utilisés.

---

## Points pédagogiques forts (à montrer en classe)

1. **Le modèle est un « cerveau sans bras »** : il ne peut ni lire vos fichiers
   ni taper des commandes. Les *outils* sont ses bras. Le `tool calling` est le
   pont entre les deux.
2. **Le tool calling, c'est du JSON structuré** : le modèle ne « programme pas
   votre PC », il répond « j'appelle `write_file` avec ces arguments » — c'est
   notre code Python qui exécute réellement.
3. **Le system prompt vaut de l'or** : un même modèle devient un agent fiable
   ou un bavard inefficace selon les 20 lignes qu'on lui donne. Exemple vécu :
   le modèle « racontait » son plan sans l'exécuter ; un prompt plus ferme
   (« AGIS, ne raconte pas ») a suffi.
4. **L'agent se corrige tout seul** : quand `edit_file` échoue (texte introuvable),
   l'erreur est renvoyée au modèle, qui relit le fichier et recommence. C'est la
   boucle « raisonner → agir → observer → réessayer ».
5. **Transparence** : chaque appel d'outil est affiché dans le terminal.
   Les étudiants voient le raisonnement se construire.

### Limites et questions à poser aux étudiants
- **Pas de planification longue** : l'agent décide pas à pas. Que se passe-t-il
  sur une tâche de 50 étapes ? (→ penser au *planning*, à la mémoire longue.)
- **Contexte limité** : toute l'historique est renvoyé à chaque tour. Que faire
  quand ça dépasse ? (→ *résumé*, *mémoire vectorielle*, *retrieval*.)
- **Sécurité** : l'agent exécute du code réel. Il faut un bac à sable
  (VM, conteneur, permissions). Question : que se passe-t-il si on lui demande
  `rm -rf /` ?
- **Coût / latence** : chaque tour d'outil = un appel au modèle.

---

## Tests

```bash
python -m unittest discover -s tests -v
```

Les tests ne touchent pas à Ollama : ils vérifient les outils et la
normalisation des messages (les parties 100 % déterministes).
**86 tests** (dont un vrai `.docx`, un `.pptx`, un `.xlsx` et un `.pdf`
construits à la main — `zipfile` + `zlib` natifs).

## Détails Windows

Si les accents s'affichent mal dans la console (`�`), exécutez :

```bash
set PYTHONIOENCODING=utf-8
```

## Aller plus loin (pistes de projets étudiants)

- Ajouter un outil `write_test` qui génère automatiquement les tests.
- Ajouter le streaming des réponses (affichage mot à mot).
- Ajouter une mémoire persistante (`sqlite3` ou un fichier JSON).
- Brancher l'agent sur un autre fournisseur : changer `OLLAMA_URL`
  pour `https://api.openai.com/v1` (avec clé API) fonctionne sans rien coder !
  C'est le pouvoir des API « compatible OpenAI ».
