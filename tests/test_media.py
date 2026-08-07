"""Tests des outils de génération d'images (generer_image) et de
création de présentations PowerPoint (creer_powerpoint).

Aucun Ollama ni service externe requis : les moteurs SD sont simulés/absents
et le rendu des illustrations est 100 % local (Pillow embarqué).
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import config
import tools


class TestGenererImage(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_graphique_barres_genere_png_et_svg(self):
        out = os.path.join(self.tmp, "g.png")
        msg = tools.generer_image(
            "graphique en barres : 2020=80 ; 2021=90 ; 2022=95", out)
        self.assertIn("illustration générée", msg)
        self.assertTrue(os.path.exists(out))
        with open(out, "rb") as fh:
            self.assertEqual(fh.read(8), b"\x89PNG\r\n\x1a\n")
        self.assertTrue(os.path.exists(os.path.splitext(out)[0] + ".svg"))

    def test_pas_de_donnees_aucune_fabrication(self):
        out = os.path.join(self.tmp, "g.png")
        msg = tools.generer_image("graphique en barres sans aucune donnee", out)
        self.assertIn("ERREUR", msg)
        self.assertFalse(os.path.exists(out))

    def test_tous_les_genres_illustration(self):
        cases = [
            "répartition : Maths=40 ; Français=30 ; Physique=30",
            "processus : collecte ; traitement ; analyse ; présentation",
            "carte mentale : le système solaire ; Mercure ; Vénus ; Terre",
            "pour: rapide ; précis  contre: lent ; lourd",
            "equation : E = m*c^2",
            "une scène de forêt avec un soleil et des arbres",
        ]
        for i, prompt in enumerate(cases):
            out = os.path.join(self.tmp, f"k{i}.png")
            msg = tools.generer_image(prompt, out)
            self.assertIn("illustration générée", msg, msg)
            self.assertTrue(os.path.exists(out), msg)

    def test_description_vide(self):
        self.assertIn("ERREUR", tools.generer_image("", "x.png"))
        self.assertIn("ERREUR", tools.generer_image("   ", "x.png"))

    @patch.object(config, "SDCPP", "sd.exe")
    @patch.object(config, "SD_MODEL", "modele.gguf")
    def test_sd_cpp_absent_bascule_illustration(self):
        # exe/modèle inexistants -> pas de moteur SD -> illustration locale
        out = os.path.join(self.tmp, "g.png")
        msg = tools.generer_image(
            "graphique : A=50 ; B=30 ; C=20", out)
        self.assertIn("illustration générée", msg)
        self.assertTrue(os.path.exists(out))

    @patch.object(config, "SD_URL", "http://127.0.0.1:9")   # injoignable
    def test_sd_api_injoignable_bascule_illustration(self):
        out = os.path.join(self.tmp, "g.png")
        msg = tools.generer_image(
            "graphique : A=50 ; B=30 ; C=20", out)
        self.assertIn("illustration générée", msg)


class TestCreerPowerpoint(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_presentation_minimale_creée(self):
        plan = json.dumps({
            "titre": "Cours de maths",
            "auteur": "M. Dupont",
            "slides": [{"titre": "Objectifs",
                        "texte": ["Comprendre", "Savoir faire"]}],
        })
        out = os.path.join(self.tmp, "cours.pptx")
        msg = tools.creer_powerpoint(plan, out)
        self.assertIn("OK: présentation créée", msg)
        self.assertTrue(os.path.exists(out))
        texte = tools.read_document(out)
        self.assertIn("Objectifs", texte)
        self.assertIn("Comprendre", texte)

    def test_video_et_image_manquante(self):
        plan = json.dumps({
            "titre": "Cours",
            "slides": [{
                "titre": "Exemple",
                "texte": ["A"],
                "image": os.path.join(self.tmp, "introuvable.png"),
                "video": {"url": "https://youtube.com/watch?v=abc",
                          "texte": "Voir la video"},
            }],
        })
        out = os.path.join(self.tmp, "c2.pptx")
        msg = tools.creer_powerpoint(plan, out)
        self.assertIn("1 lien(s) vidéo", msg)
        self.assertIn("NON intégrée", msg)     # honnête : image absente
        self.assertTrue(os.path.exists(out))

    def test_image_existante_integree(self):
        img = os.path.join(self.tmp, "img.png")
        tools.generer_image("graphique : A=50 ; B=30", img)
        plan = json.dumps({
            "titre": "Cours",
            "slides": [{"titre": "Données", "texte": ["Résultats"],
                        "image": img}],
        })
        out = os.path.join(self.tmp, "c3.pptx")
        msg = tools.creer_powerpoint(plan, out)
        self.assertIn("1 image(s) intégrée(s)", msg)
        self.assertNotIn("NON intégrée", msg)

    def test_plan_json_invalide(self):
        self.assertIn("ERREUR", tools.creer_powerpoint("{pas du json", "x.pptx"))
        self.assertIn("ERREUR", tools.creer_powerpoint("[]", "x.pptx"))
        self.assertIn("ERREUR", tools.creer_powerpoint(
            json.dumps({"titre": "x", "slides": []}), "x.pptx"))


class TestDessinHonnete(unittest.TestCase):

    def test_detect_genres(self):
        import dessin
        self.assertEqual(dessin._detect("graphique en barres de ventes"), "bar")
        self.assertEqual(dessin._detect("répartition des notes"), "pie")
        self.assertEqual(dessin._detect("étapes du projet : a ; b"), "flow")
        self.assertEqual(dessin._detect("carte mentale : sujet"), "mindmap")
        self.assertEqual(dessin._detect("avantages et inconvénients"), "compare")
        self.assertEqual(dessin._detect("formule de la physique"), "equation")
        self.assertEqual(dessin._detect("une maison au bord de la mer"), "generic")

    def test_detect_donnees_brutes_sans_genre_devient_barres(self):
        import dessin
        self.assertEqual(dessin._detect(
            "label=valeur;2023=120;2024=150;2025=180"), "bar")
        self.assertEqual(dessin._detect("2023=120;2024=150"), "bar")

    def test_detect_equation_pas_confondue_avec_donnees(self):
        import dessin
        self.assertEqual(dessin._detect("x^2+3x+5=0"), "equation")
        self.assertEqual(dessin._detect("a^2 + b^2 = c^2"), "equation")
        self.assertEqual(dessin._detect("x=5"), "equation")

    def test_titre_donnees_brutes_neutre(self):
        import dessin
        self.assertEqual(
            dessin._first_sentence("label=valeur;2023=120;2024=150"), "Données")
        self.assertEqual(
            dessin._first_sentence("Ventes du magasin 2023=120;2024=150"),
            "Ventes du magasin")

    def test_donnees_brutes_generent_un_graphique(self):
        import dessin
        import tempfile
        tmp = tempfile.mkdtemp()
        try:
            out = os.path.join(tmp, "d.png")
            msg = dessin.generer("label=valeur;2023=120;2024=150;2025=180", out)
            self.assertIn("Genre: bar", msg)
            self.assertTrue(os.path.exists(out))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestResolveSortie(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_sans_sortie_utilise_espace_de_travail(self):
        out = tools._resolve_sortie(None, "images", ".png")
        self.assertTrue(out.startswith(os.path.join(config.WORKSPACE, "images")))

    def test_dossier_trailing_slash_recoit_nom_defaut(self):
        d = os.path.join(self.tmp, "images")
        out = tools._resolve_sortie(d + "/", "images", ".png")
        self.assertTrue(out.startswith(os.path.join(d, "agent-")))
        self.assertTrue(out.endswith(".png"))

    def test_nom_sans_extension_la_recoit(self):
        out = tools._resolve_sortie("ventes", "images", ".png")
        self.assertTrue(out.endswith(".png"))

    def test_extension_conservee(self):
        out = tools._resolve_sortie("ventes.png", "images", ".png")
        self.assertTrue(out.endswith("ventes.png"))


if __name__ == "__main__":
    unittest.main()
