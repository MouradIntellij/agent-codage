"""Outils de l'agent codeur.

Un outil, c'est deux choses :
  1. Un SCHÉMA JSON  -> décrit l'outil au modèle (nom, paramètres, utilité).
  2. Une FONCTION     -> fait réellement le travail quand le modèle l'appelle.

Le modèle ne "voit" que les schémas. Il décide d'appeler un outil en
renvoyant un JSON. Notre code exécute la fonction correspondante et
renvoie le résultat textuel au modèle. C'est ça, un "tool" d'agent.
"""

import glob as globlib
import os
import re
import subprocess
import time
import zipfile
import zlib

import config


# --------------------------------------------------------------------------
# 1) Schémas JSON des outils (format "function calling" de OpenAI/Ollama)
# --------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "Liste le contenu d'un répertoire (fichiers + dossiers). "
                           "À utiliser pour explorer un projet avant de travailler.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Chemin du dossier (défaut: .)"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lit le contenu d'un fichier, lignes numérotées. "
                           "TOUJOURS lire un fichier avant de le modifier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Chemin du fichier"},
                    "offset": {"type": "integer", "description": "Ligne de départ (1 = début)"},
                    "limit": {"type": "integer", "description": "Nombre de lignes à lire"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Extrait le TEXTE lisible d'un document : Word (.docx), "
                           "PowerPoint (.pptx), Excel (.xlsx), PDF (.pdf) ou fichier texte. "
                           "À utiliser pour tout fichier qui n'est pas du code simple.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Chemin du fichier document"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_files",
            "description": "Recherche un mot ou une expression dans tous les fichiers texte "
                           "d'un dossier (récursif). Retourne les fichiers et les NUMÉROS DE "
                           "LIGNE contenant l'expression. Idéal pour 'où est utilisé X ?'.",
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
    {
        "type": "function",
        "function": {
            "name": "count_occurrences",
            "description": "Compte EXACTEMENT combien de fois un mot ou une expression apparaît "
                           "dans un fichier (décompte précis par le code, pas à la main). "
                           "Compte les mots entiers, sans tenir compte des majuscules.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Chemin du fichier à analyser"},
                    "term": {"type": "string", "description": "Mot ou expression à compter"},
                },
                "required": ["path", "term"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Crée un fichier ou ÉCRASE son contenu complet avec le texte fourni. "
                           "À utiliser pour créer de nouveaux fichiers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Chemin du fichier"},
                    "content": {"type": "string", "description": "Contenu complet à écrire"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Remplace une portion EXACTE d'un fichier par un nouveau texte. "
                           "Pour modifier sans réécrire tout le fichier. "
                           "Échoue si l'ancien texte n'est pas trouvé à l'identique.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Chemin du fichier"},
                    "old_string": {"type": "string", "description": "Texte EXACT à remplacer"},
                    "new_string": {"type": "string", "description": "Nouveau texte"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "Trouve des fichiers par motif de nom, ex: '**/*.py' ou 'src/**'. "
                           "Comme la commande glob de VS Code.",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string", "description": "Motif à rechercher"}},
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calcul_symbolique",
            "description": "Calcule et VÉRIFIE une expression mathématique avec SymPy "
                           "(intégrale, dérivée, équation, limite, simplification). "
                           "À utiliser pour TOUT calcul mathématique. L'expression doit être "
                           "copiée EN TEXTE BRUT telle qu'écrite par l'étudiant, ex: "
                           "'ln(x+1)', 'x^2 - 5*x + 6 = 0'. Ne jamais écrire le code SymPy "
                           "à la main : c'est l'outil qui interprète et vérifie.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string",
                                   "description": "La fonction mathématique EN TEXTE BRUT, copiée telle quelle (ex: 'ln(x+1)')"},
                    "operation": {"type": "string",
                                  "description": "Type de calcul: 'integrale' (défaut), 'derivee', 'equation', 'limite', 'simplifier', 'factoriser'"},
                    "variable": {"type": "string", "description": "Variable d'intégration (défaut: x)"},
                    "point": {"type": "string", "description": "Point pour une limite (défaut: oo)"},
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Exécute une commande dans le terminal (python, git, pip, pytest...). "
                           "Retourne la sortie, les erreurs et le code de sortie. "
                           "Pour un CALCUL MATHÉMATIQUE (intégrale, dérivée, équation...), "
                           "n'écris PAS le code SymPy à la main : utilise l'outil dédié "
                           "`calcul_symbolique` avec l'expression en texte brut.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Commande shell à exécuter"},
                    "timeout": {"type": "integer", "description": "Délai max en secondes"},
                },
                "required": ["command"],
            },
        },
    },
]


# --------------------------------------------------------------------------
# 2) Implémentations Python des outils
# --------------------------------------------------------------------------

def _repair_path(path: str) -> str:
    """Corrige un chemin à racine dupliquée (erreur de copier-coller).

    Ex: 'C:\\LaSalle\\C:\\LaSalle\\f.pdf' -> 'C:\\LaSalle\\f.pdf'
    On garde la racine la plus à droite (le dernier 'X:\\').
    """
    if not path:
        return path
    norm = path.replace("/", "\\")
    roots = re.findall(r"[A-Za-z]:\\", norm)
    if len(roots) >= 2:
        return norm[norm.rfind(roots[-1]):]
    return path


def _existing_path(path: str) -> str:
    """Renvoie un chemin existant (réparé si besoin), sinon le chemin d'origine."""
    if os.path.exists(path):
        return path
    repaired = _repair_path(path)
    return repaired if os.path.exists(repaired) else path


def list_dir(path: str = ".") -> str:
    path = _existing_path(path)
    if not os.path.isdir(path):
        return f"ERREUR: '{path}' n'est pas un dossier."
    rows = []
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        kind = "📁" if os.path.isdir(full) else "📄"
        size = "" if os.path.isdir(full) else f"  {os.path.getsize(full):,} o"
        rows.append(f"{kind}  {name}{size}")
    return "\n".join(rows) or "(dossier vide)"


def read_file(path: str, offset: int = 1, limit: int | None = None) -> str:
    path = _existing_path(path)
    if not os.path.isfile(path):
        parent = os.path.dirname(os.path.abspath(path))
        try:
            listing = "\n".join(
                f"  - {name}" for name in sorted(os.listdir(parent))[:40])
        except OSError:
            listing = ""
        hint = (f"\nListe du dossier {parent}:\n{listing}" if listing else "")
        return (f"ERREUR: fichier introuvable: {path}"
                f"\nVérifiez le chemin ou cherchez le fichier.{hint}")
    limit = limit or config.MAX_READ_LINES
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as err:
        return f"ERREUR: {err}"
    if len(data) > 5 * 1024 * 1024:                  # on protège le contexte du modèle
        return f"ERREUR: fichier trop volumineux ({len(data)} octets)."
    if b"\0" in data[:8192]:                         # un .docx (binaire ZIP) contient des NUL
        return (f"ERREUR: '{path}' est un fichier BINAIRE (non texte). "
                f"Pour un document, utilisez l'outil read_document.")
    lines = data.decode("utf-8", errors="replace").split("\n")
    chunk = lines[offset - 1: offset - 1 + limit]
    return "".join(f"{offset + i}: {line}\n" for i, line in enumerate(chunk))


def write_file(path: str, content: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return f"OK: {path} écrit ({len(content)} caractères)."


def edit_file(path: str, old_string: str, new_string: str) -> str:
    if not os.path.isfile(path):
        return f"ERREUR: fichier introuvable: {path}"
    with open(path, encoding="utf-8") as fh:
        content = fh.read()
    count = content.count(old_string)
    if count == 0:
        return f"ERREUR: texte à remplacer INTROUVABLE dans {path}. Relisez le fichier."
    if count > 1:
        return f"ERREUR: texte trouvé {count} fois. Donnez plus de contexte."
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content.replace(old_string, new_string, 1))
    return f"OK: {path} modifié (1 remplacement)."


def glob(pattern: str) -> str:
    matches = globlib.glob(pattern, recursive=True)
    return "\n".join(matches) if matches else f"Aucun fichier pour '{pattern}'."


def bash(command: str, timeout: int | None = None) -> str:
    timeout = timeout or config.BASH_TIMEOUT
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return f"ERREUR: commande interrompue après {timeout} s."
    elapsed = time.monotonic() - started
    output = proc.stdout + proc.stderr
    if len(output) > 4000:                       # tronque pour ne pas saturer le contexte
        output = output[:4000] + "\n...[sortie tronquée]"
    return (f"$ {command}  ({elapsed:.1f}s, code de sortie {proc.returncode})\n"
            f"{output}".rstrip())


# --------------------------------------------------------------------------
# Calcul symbolique VÉRIFIÉ (SymPy).
#
# Le modèle NE DOIT JAMAIS écrire le code SymPy à la main (il fait des fautes
# de transcription : `sympy.ln(x)+1` au lieu de `sympy.ln(x+1)`). Il passe
# l'expression EN TEXTE BRUT, copiée telle quelle, et SymPy se charge de
# l'interpréter, de calculer ET de vérifier par dérivation.
# --------------------------------------------------------------------------

# Noms de fonctions connus : on n'y insère pas de multiplication implicite.
_FUNC_NAMES = {
    "ln", "log", "exp", "sin", "cos", "tan", "asin", "acos", "atan",
    "sinh", "cosh", "tanh", "sqrt", "abs", "erf", "sec", "csc", "cot",
}


def _norm_op(operation: str) -> str:
    """Normalise le nom de l'opération demandée ('intégrale', 'dérivée'...)."""
    op = (operation or "").lower()
    for a, b in (("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"),
                 ("ô", "o"), ("î", "i"), ("û", "u"), ("ç", "c")):
        op = op.replace(a, b)
    if not op:
        return "integrale"
    if op.startswith("integr") or op.startswith("primitive"):
        return "integrale"
    if op.startswith("deriv"):
        return "derivee"
    if op.startswith("equat") or op.startswith("resoud") or op.startswith("resol"):
        return "equation"
    if op.startswith("simpl"):
        return "simplifier"
    if op.startswith("factor"):
        return "factoriser"
    if op.startswith("limit"):
        return "limite"
    return "integrale"


def _prepare_expr(s: str) -> str:
    """Petits accommodements avant l'interprétation SymPy : x^2 -> x**2,
    multiplication implicite (2x -> 2*x, x(x+1) -> x*(x+1))."""
    s = s.replace("^", "**").replace("√", "sqrt").strip()
    # ')' suivi d'une lettre/chiffre/'(' -> multiplication.
    s = re.sub(r"\)\s*(?=[A-Za-z0-9(])", ")*", s)
    # chiffre suivi d'une lettre ou d'une parenthèse -> multiplication.
    s = re.sub(r"(?<=\d)\s*(?=[A-Za-z(])", "*", s)
    # variable simple (x, y, t, z) directement suivie de '(' -> multiplication,
    # sauf si elle fait partie d'un nom de fonction (sin(, ln(, exp(...).
    s = re.sub(r"(^|[^\w])([xytz])\s*\(", r"\1\2*(", s)
    return s


def _by_parts_steps(f, sym, sympy):
    """Dérivation par parties VÉRIFIÉE pour f = ln(a*x + b).

    Chaque étape est recalculée par SymPy : la dérivation est donc exacte.
    Renvoie '' si la fonction n'est pas de la forme ln(linéaire).
    """
    if not isinstance(f, sympy.log):
        return ""
    g = f.args[0]
    if sympy.degree(g, sym) != 1:
        return ""
    p = sympy.Poly(g, sym)
    a, b = p.nth(1), p.nth(0)
    du = sympy.simplify(a / g)
    v_int = sympy.simplify(sympy.integrate(sym * a / g, sym))
    final = sympy.simplify(sym * f - v_int)
    g_s = str(g).replace("log(", "ln(")
    du_s = str(du).replace("log(", "ln(")
    v_s = str(v_int).replace("log(", "ln(")
    f_s = str(final).replace("log(", "ln(")
    return (f"\n\nMÉTHODE PAR PARTIES (chaque étape vérifiée par SymPy) :\n"
            f"u = ln({g_s}),  dv = d{sym}\n"
            f"du = {du_s} d{sym},  v = {sym}\n"
            f"∫ u·dv = u·v − ∫ v·du = {sym}·ln({g_s}) − ∫ {sym}·{a}/({g_s}) d{sym}\n"
            f"∫ {sym}·{a}/({g_s}) d{sym} = {v_s}\n"
            f"Résultat : {sym}·ln({g_s}) − ({v_s}) = {f_s} + C")


def calcul_symbolique(expression: str, operation: str = "integrale",
                      variable: str = "x", point: str = "oo") -> str:
    """Calcule et VÉRIFIE une expression mathématique avec SymPy.

    `expression` est fournie en texte brut (ex: 'ln(x+1)'), copiée telle
    quelle de la demande de l'étudiant. SymPy l'interprète, calcule, puis
    vérifie le résultat (la dérivée du résultat doit redonner l'expression).
    """
    try:
        import sympy
    except ImportError:
        return ("ERREUR: SymPy n'est pas installé. "
                "Installez-le avec: python -m pip install sympy.")
    op = _norm_op(operation)
    expr = (expression or "").strip()
    if not expr:
        return ("ERREUR: expression vide. Passez SEULEMENT la fonction, "
                "ex: expression='ln(x+1)'.")
    sym = sympy.symbols(variable)
    locals_map = {variable: sym, "ln": sympy.log, "log": sympy.log,
                  "e": sympy.E, "pi": sympy.pi, "oo": sympy.oo}
    try:
        if "=" in expr:
            lhs_s, _, rhs_s = expr.partition("=")
            f = sympy.sympify(_prepare_expr(lhs_s), locals=locals_map) - \
                sympy.sympify(_prepare_expr(rhs_s), locals=locals_map)
        else:
            f = sympy.sympify(_prepare_expr(expr), locals=locals_map)
    except Exception as err:
        return (f"ERREUR: expression '{expression}' non comprise ({err}). "
                f"Passez SEULEMENT la fonction en texte brut, ex: 'ln(x+1)', "
                f"'x**2*exp(x)' ou l'équation 'x^2 - 5*x + 6 = 0'.")
    f = sympy.simplify(f)

    if op == "derivee":
        r = sympy.simplify(sympy.diff(f, sym))
        check = sympy.simplify(sympy.integrate(r, sym) - f)
        verif = "CORRECT" if check == 0 else f"à vérifier: reste {check}"
        return (f"Expression interprétée : {f}\n"
                f"f'({variable}) = {r}\n"
                f"VÉRIFICATION : {verif}")

    if op == "equation":
        try:
            sols = sympy.solve(f, sym)
        except Exception as err:
            return f"ERREUR: résolution impossible: {err}"
        # Vérifie chaque solution en la substituant dans l'équation.
        try:
            checks = [sympy.simplify(f.subs(sym, s)) for s in sols]
            verif = "CORRECT" if all(c == 0 for c in checks) else \
                f"DOUTEUX: restes {[c for c in checks if c != 0]}"
        except Exception:
            verif = "calculée (vérification par substitution impossible)"
        return (f"Équation : {expr}\nSolution(s) {variable} : {sols}\n"
                f"VÉRIFICATION : {verif}")

    if op == "limite":
        try:
            p = sympy.sympify(_prepare_expr(point), locals=locals_map)
            r = sympy.limit(f, sym, p)
        except Exception as err:
            return f"ERREUR: limite impossible: {err}"
        return f"Expression interprétée : {f}\nlim {variable}→{point} : {r}"

    if op == "simplifier":
        return f"Expression interprétée : {expr}\nSimplifiée : {sympy.simplify(f)}"

    if op == "factoriser":
        try:
            return f"Expression interprétée : {expr}\nFactorisée : {sympy.factor(f)}"
        except Exception as err:
            return f"ERREUR: factorisation impossible: {err}"

    # Intégrale (cas par défaut aussi).
    r = sympy.integrate(f, sym)
    check = sympy.simplify(sympy.diff(r, sym) - f)
    verif = "CORRECT (la dérivée du résultat redonne exactement f(x))" \
        if check == 0 else f"DOUTEUX: il reste {check}"
    form = ""
    try:
        fr = sympy.collect(r, sympy.log(sym + 1))
        if fr != r:
            form = f"\nForme regroupée : {fr} + C"
    except Exception:
        pass
    try:
        by_parts = _by_parts_steps(f, sym, sympy)
    except Exception:
        by_parts = ""
    return (f"Expression interprétée : {f}\n"
            f"∫ f({variable}) d{variable} = {r} + C{form}"
            f"{by_parts}\n"
            f"VÉRIFICATION : {verif}")


# --------------------------------------------------------------------------
# Recherche d'un terme dans un dossier (type "grep").
# --------------------------------------------------------------------------

# Dossiers à ignorer lors d'une recherche récursive.
IGNORED_DIRS = {"node_modules", ".git", "dist", ".next", "coverage", "__pycache__"}


def count_occurrences(path: str, term: str) -> str:
    """Compte EXACTEMENT les occurrences d'un mot (mots entiers, insensible
    à la casse). Décompte par le code : résultat fiable à 100 %."""
    if not os.path.isfile(path):
        return f"ERREUR: fichier introuvable: {path}"
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as err:
        return f"ERREUR: {err}"
    if len(text) > 5 * 1024 * 1024:
        return f"ERREUR: fichier trop volumineux ({len(text)} octets)."
    if " " in term.strip():
        count = text.lower().count(term.lower())
    else:
        count = len(re.findall(rf"\b{re.escape(term)}\b", text,
                               flags=re.IGNORECASE))
    return (f"Le terme '{term}' apparaît {count} fois dans {path} "
            f"({len(text.split())} mots dans le fichier).")


def search_in_files(term: str, folder: str = ".") -> str:
    """Recherche un mot/expression (insensible à la casse) dans un dossier.

    Retourne `fichier:n°ligne: contenu`, comme le font les bons outils.
    Limite à 100 résultats pour ne pas saturer le contexte du modèle.
    """
    needle = term.lower()
    hits: list[str] = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]   # on évite les dossiers lourds
        for name in files:
            full = os.path.join(root, name)
            try:
                with open(full, "rb") as fh:
                    data = fh.read()
            except OSError:
                continue                                      # fichier illisible : on ignore
            if b"\0" in data[:8192]:                          # binaire : on saute
                continue
            for i, line in enumerate(data.decode("utf-8", errors="replace").split("\n"),
                                     start=1):
                if needle in line.lower():
                    hits.append(f"{full}:{i}: {line.strip()[:200]}")
                    if len(hits) >= 100:
                        break
            if len(hits) >= 100:
                break
        if len(hits) >= 100:
            break
    if not hits:
        return f"Aucune occurrence de '{term}' dans {folder}."
    return f"{len(hits)} occurrence(s) de '{term}' :\n" + "\n".join(hits)


# --------------------------------------------------------------------------
# Lecture de documents : un .docx/.xlsx/.pptx est un ZIP (zipfile, natif),
# un .pdf contient des flux texte compressés (zlib, natif). Zéro dépendance.
# Limite connue : un PDF numérisé (image) n'a pas de texte à extraire.
# --------------------------------------------------------------------------

# Taille max du texte renvoyé au modèle (on protège son contexte).
DOC_TEXT_LIMIT = 8000

# Ponctuation française des PDF encodés en CP1252 (les apostrophes, tirets…).
_CP1252 = {
    0x80: "€", 0x82: "‚", 0x83: "ƒ", 0x84: "„", 0x85: "…", 0x86: "†", 0x87: "‡",
    0x88: "ˆ", 0x89: "‰", 0x8A: "Š", 0x8B: "‹", 0x8C: "Œ", 0x8E: "Ž",
    0x91: "‘", 0x92: "’", 0x93: "“", 0x94: "”", 0x95: "•", 0x96: "–", 0x97: "—",
    0x98: "˜", 0x99: "™", 0x9A: "š", 0x9B: "›", 0x9C: "œ", 0x9E: "ž", 0x9F: "Ÿ",
}


def _decode_xml(s: str) -> str:
    """Décode les entités XML (&amp;, &lt;…) en caractères réels."""
    return (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            .replace("&quot;", '"').replace("&apos;", "'"))


def _xml_to_text(xml: str) -> str:
    """Transforme du XML Word/PowerPoint en texte lisible (balises retirées)."""
    text = re.sub(r"</w:p>|</a:p>", "\n", xml)      # fin de paragraphe -> ligne
    text = re.sub(r"<w:tab[^>]*/>|<a:br[^>]*/>", "\t", text)
    text = re.sub(r"<[^>]+>", "", text)             # toutes les autres balises
    text = _decode_xml(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _docx_to_text(path: str) -> str:
    """Word : le texte vit dans word/document.xml (un XML aux balises <w:…>)."""
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    return _xml_to_text(xml)


def _pptx_to_text(path: str) -> str:
    """PowerPoint : chaque diapositive est un XML dans ppt/slides/slideN.xml."""
    with zipfile.ZipFile(path) as zf:
        slides = sorted(
            (n for n in zf.namelist() if re.match(r"^ppt/slides/slide\d+\.xml$", n)),
            key=lambda n: int(re.search(r"\d+", n).group()),
        )
        if not slides:
            return "(aucune diapositive trouvée)"
        parts = []
        for name in slides:
            num = int(re.search(r"\d+", name).group())
            xml = zf.read(name).decode("utf-8")
            parts.append(f"Diapositive {num}:\n{_xml_to_text(xml)}")
    return "\n\n".join(parts)


def _xlsx_shared_strings(xml: str) -> list[str]:
    """Excel : les textes partagés sont dans xl/sharedStrings.xml."""
    strings: list[str] = []
    for si in re.findall(r"<si\b[\s\S]*?</si>", xml):
        text = "".join(re.findall(r"<t[^>]*>([\s\S]*?)</t>", si))
        strings.append(_decode_xml(text))
    return strings


def _xlsx_sheet(xml: str, shared: list[str]) -> str:
    """Une feuille : chaque cellule <c> devient `référence: valeur`."""
    lines: list[str] = []
    for cell in re.findall(r"<c\b[^>]*>[\s\S]*?</c>", xml):
        ref = re.search(r'r="([A-Z]+\d+)"', cell)
        if not ref:
            continue
        ref = ref.group(1)
        typ = re.search(r't="([^"]*)"', cell)
        typ = typ.group(1) if typ else ""
        v = re.search(r"<v>([\s\S]*?)</v>", cell)
        v = v.group(1) if v else None
        inline = re.search(r"<t[^>]*>([\s\S]*?)</t>", cell)
        inline = inline.group(1) if inline else None
        if typ == "s" and v is not None:
            value = shared[int(v)] if int(v) < len(shared) else ""
        elif inline is not None:
            value = inline
        elif v is not None:
            value = v
        else:
            value = ""
        if value.strip():
            lines.append(f"{ref}: {_decode_xml(value)}")
    return "\n".join(lines)


def _xlsx_to_text(path: str) -> str:
    """Excel : feuilles dans l'ordre, cellules avec leurs références (A1, B2…)."""
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if "xl/sharedStrings.xml" in names:
            shared = _xlsx_shared_strings(zf.read("xl/sharedStrings.xml").decode("utf-8"))
        else:
            shared = []
        sheets = sorted(
            (n for n in names if re.match(r"^xl/worksheets/sheet\d+\.xml$", n)),
            key=lambda n: int(re.search(r"\d+", n).group()),
        )
        if not sheets:
            return "(aucune feuille trouvée)"
        parts = []
        for i, name in enumerate(sheets, start=1):
            xml = zf.read(name).decode("utf-8")
            parts.append(f"Feuille {i}:\n{_xlsx_sheet(xml, shared)}")
    return "\n\n".join(parts)


def _pdf_streams(data: bytes) -> list[bytes]:
    """Décompresse les flux texte (FlateDecode) d'un PDF, avec ou sans en-tête zlib."""
    streams: list[bytes] = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.DOTALL):
        raw = m.group(1)
        for wbits in (15, -15):                     # -15 = deflate brut, 15 = zlib complet
            try:
                streams.append(zlib.decompress(raw, wbits))
                break
            except zlib.error:
                continue
    return streams


def _decode_pdf_string(s: str) -> str:
    """Décode une chaîne PDF : échappements + encodage CP1252."""
    s = s.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
    s = s.replace(r"\n", "\n").replace(r"\r", "")
    s = re.sub(r"\\([0-7]{1,3})", lambda m: chr(int(m.group(1), 8)), s)
    return "".join(_CP1252.get(ord(ch), ch) if "\x80" <= ch <= "\x9f" else ch
                   for ch in s)


def _pdf_op_text(op: str) -> str:
    """Texte d'un opérateur Tj ou TJ (les parenthèses délimitantes sont retirées)."""
    if op.startswith("("):
        return _decode_pdf_string(op[1:op.rfind(")")])
    arr = op[1:op.rfind("]")]                       # le tableau de chaînes de TJ
    return "".join(_decode_pdf_string(p)
                   for p in re.findall(r"\(((?:[^()\\]|\\.)*)\)", arr))


def _extract_pdf_text(data: bytes) -> str:
    """Recolle les morceaux de texte d'un PDF (les mots sont souvent découpés)."""
    lines: list[str] = []
    for stream in _pdf_streams(data):
        chunk = stream.decode("latin1")
        for segment in re.split(r"T\*|Td|TD", chunk):
            ops = re.findall(
                r"\((?:[^()\\]|\\.)*\)\s*Tj|\[(?:[^\[\]\\]|\\.)*\]\s*TJ",
                segment)
            if not ops:
                continue
            line = "".join(_pdf_op_text(op) for op in ops)
            line = re.sub(r"\s{2,}", " ", line).strip()
            if line:
                lines.append(line)
    return "\n".join(lines).strip()


def read_document(path: str) -> str:
    """Extrait le texte lisible d'un document : Word, PowerPoint, Excel, PDF, texte."""
    path = _existing_path(path)
    if not os.path.isfile(path):
        parent = os.path.dirname(os.path.abspath(path))
        try:
            listing = "\n".join(
                f"  - {name}" for name in sorted(os.listdir(parent))[:40])
        except OSError:
            listing = ""
        hint = (f"\nListe du dossier {parent}:\n{listing}" if listing else "")
        return (f"ERREUR: fichier introuvable: {path}"
                f"\nVérifiez le chemin ou cherchez le fichier.{hint}")
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    try:
        if ext == "docx":
            text = _docx_to_text(path)
        elif ext == "pptx":
            text = _pptx_to_text(path)
        elif ext == "xlsx":
            text = _xlsx_to_text(path)
        elif ext == "pdf":
            with open(path, "rb") as fh:
                text = _extract_pdf_text(fh.read())
        else:                                       # fichier texte ordinaire
            with open(path, "rb") as fh:
                data = fh.read()
            if b"\0" in data[:8192]:
                return (f"ERREUR: type de fichier '{ext}' non supporté par "
                        f"read_document, et le fichier semble binaire.")
            text = data.decode("utf-8", errors="replace")
    except (OSError, zipfile.BadZipFile) as err:
        return f"ERREUR: impossible d'extraire le texte: {err}"
    text = (text or "").strip()
    if not text:
        return "(document vide ou sans texte lisible)"
    if len(text) > DOC_TEXT_LIMIT:
        return text[:DOC_TEXT_LIMIT] + "\n...[tronqué]"
    return text


# Correspondance nom d'outil -> fonction Python.
EXECUTORS = {
    "list_dir": list_dir,
    "read_file": read_file,
    "read_document": read_document,
    "search_in_files": search_in_files,
    "count_occurrences": count_occurrences,
    "write_file": write_file,
    "edit_file": edit_file,
    "glob": glob,
    "bash": bash,
    "calcul_symbolique": calcul_symbolique,
}


def execute_tool(name: str, arguments: dict) -> str:
    """Point d'entrée unique : exécute un outil par son nom, en sécurité."""
    if name not in EXECUTORS:
        return f"ERREUR: outil inconnu '{name}'."
    try:
        return EXECUTORS[name](**arguments)
    except TypeError as err:
        return f"ERREUR: mauvais arguments pour {name}: {err}"
    except Exception as err:                     # pragma: no cover - filet de sécurité
        return f"ERREUR inattendue dans {name}: {err}"
