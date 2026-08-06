"""Tests des helpers de pièces jointes de l'interface web.

Ne nécessite PAS Ollama ni un navigateur : on teste seulement la
sauvegarde / le nettoyage des fichiers téléversés.
Lancement:  python -m unittest discover -s tests -v
"""

import base64
import os
import shutil
import tempfile
import unittest

import web


class SafeFilenameTests(unittest.TestCase):
    def test_chemin_absolu_nefaste(self):
        self.assertEqual(web._safe_filename(r"C:\Users\toto\mal.py"), "mal.py")
        self.assertEqual(web._safe_filename("/etc/passwd"), "passwd")

    def test_caracteres_interdits_retires(self):
        self.assertEqual(web._safe_filename('a<b>c:d"e|h?i*j'), "abcdehij")
        self.assertEqual(web._safe_filename('a/b\\c.txt'), "c.txt")
        self.assertEqual(web._safe_filename(".."), "")

    def test_accents_conserves(self):
        self.assertEqual(web._safe_filename("exercice_départ.PNG"), "exercice_départ.PNG")


class SaveAttachmentsTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="agent_up_")
        self._old_ws = web.config.WORKSPACE
        web.config.WORKSPACE = self.dir

    def tearDown(self):
        web.config.WORKSPACE = self._old_ws
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_sauvegarde_et_chemin_absolu(self):
        payload = base64.b64encode(b"contenu du fichier").decode("ascii")
        paths = web._save_attachments("sess1", [{"name": "note.txt", "data": payload}])
        self.assertEqual(len(paths), 1)
        self.assertTrue(os.path.isabs(paths[0]))
        self.assertEqual(os.path.basename(paths[0]), "note.txt")
        with open(paths[0], "rb") as fh:
            self.assertEqual(fh.read(), b"contenu du fichier")

    def test_trop_de_fichiers(self):
        files = [{"name": f"f{i}.txt", "data": base64.b64encode(b"x").decode("ascii")}
                 for i in range(web.MAX_FILES + 1)]
        with self.assertRaises(ValueError):
            web._save_attachments("s1", files)

    def test_fichier_trop_gros(self):
        blob = base64.b64encode(b"x" * (web.MAX_FILE_SIZE + 1)).decode("ascii")
        with self.assertRaises(ValueError):
            web._save_attachments("s1", [{"name": "gros.bin", "data": blob}])

    def test_base64_invalide_ignore(self):
        paths = web._save_attachments("s1", [{"name": "moche.bin", "data": "@@@"}])
        self.assertEqual(paths, [])

    def test_pas_de_fichiers(self):
        self.assertEqual(web._save_attachments("s1", []), [])


if __name__ == "__main__":
    unittest.main()
