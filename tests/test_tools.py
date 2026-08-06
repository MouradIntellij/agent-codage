"""Tests unitaires des outils et de la normalisation des messages.

Ne nécessite PAS Ollama : on teste le code qui entoure le modèle.
Lancement:  python -m unittest discover -s tests -v
"""

import os
import shutil
import tempfile
import unittest
import zipfile
import zlib

import llm
import tools


def make_zip(entries: list[tuple[str, str]]) -> bytes:
    """Construit un ZIP minimal en mémoire (déflaté), sans dépendance."""
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries:
            zf.writestr(name, content)
    return buf.getvalue()


def make_pdf(stream: str) -> bytes:
    """Construit un 'PDF' minimal : un flux déflaté contenant une opération Tj."""
    compressor = zlib.compressobj(wbits=-15)          # deflate brut, comme les PDF
    payload = compressor.compress(stream.encode("latin1")) + compressor.flush()
    return (b"%PDF-1.4\n"
            b"10 0 obj\n<< /Length " + str(len(payload)).encode() +
            b" /Filter /FlateDecode >>\nstream\n" + payload +
            b"\nendstream\nendobj\n%%EOF")


class ToolsTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="agent_test_")
        self.file = os.path.join(self.dir, "demo.py")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_write_and_read(self):
        tools.write_file(self.file, "ligne 1\nligne 2\n")
        content = tools.read_file(self.file)
        self.assertIn("1: ligne 1", content)
        self.assertIn("2: ligne 2", content)

    def test_read_missing_file(self):
        self.assertIn("ERREUR", tools.read_file(os.path.join(self.dir, "x.txt")))

    def test_edit_file_ok(self):
        tools.write_file(self.file, "def hello():\n    print('hi')\n")
        result = tools.edit_file(self.file, "print('hi')", "print('bonjour')")
        self.assertIn("modifié", result)
        with open(self.file, encoding="utf-8") as fh:
            self.assertIn("bonjour", fh.read())

    def test_edit_file_not_found(self):
        tools.write_file(self.file, "abc")
        result = tools.edit_file(self.file, "zzz", "yyy")
        self.assertIn("INTROUVABLE", result)

    def test_edit_file_ambiguous(self):
        tools.write_file(self.file, "abc\nabc\n")
        result = tools.edit_file(self.file, "abc", "xyz")
        self.assertIn("fois", result)

    def test_list_dir(self):
        tools.write_file(self.file, "x")
        listing = tools.list_dir(self.dir)
        self.assertIn("demo.py", listing)

    def test_glob(self):
        tools.write_file(self.file, "x")
        self.assertIn("demo.py", tools.glob(os.path.join(self.dir, "*.py")))

    def test_bash(self):
        result = tools.bash("python --version")
        self.assertIn("Python", result)

    def test_unknown_tool(self):
        self.assertIn("inconnu", tools.execute_tool("no_such_tool", {}))

    def test_read_file_refuses_binary_docx(self):
        file = os.path.join(self.dir, "binaire.docx")
        with open(file, "wb") as fh:
            fh.write(make_zip([("word/document.xml", "<x/>")]))
        self.assertIn("BINAIRE", tools.read_file(file))

    def test_search_in_files_finds_lines(self):
        tools.write_file(os.path.join(self.dir, "a.js"),
                         "const x = 1;\n// hello\nconsole.log(x);\n")
        tools.write_file(os.path.join(self.dir, "b.js"), "console.log('autre');\n")
        result = tools.search_in_files("hello", self.dir)
        self.assertIn("a.js:2:", result)
        self.assertIn("hello", result)
        self.assertNotIn("b.js", result)

    def test_search_in_files_case_insensitive_and_recursive(self):
        sub = os.path.join(self.dir, "sous")
        tools.write_file(os.path.join(self.dir, "root.txt"), "rien ici\n")
        tools.write_file(os.path.join(sub, "deep.txt"), "RECHERCHE trouvée\n")
        result = tools.search_in_files("recherche", self.dir)
        self.assertIn("deep.txt:1:", result)

    def test_search_in_files_no_result(self):
        tools.write_file(os.path.join(self.dir, "a.txt"), "rien\n")
        result = tools.search_in_files("zizou", self.dir)
        self.assertIn("Aucune occurrence", result)

    def test_count_occurrences_word_exact(self):
        tools.write_file(os.path.join(self.dir, "notes.txt"),
                         "Le logarithme naturel. Les logarithmes des nombres. "
                         "logarithme, encore logarithme !\n")
        result = tools.count_occurrences(os.path.join(self.dir, "notes.txt"),
                                         "logarithme")
        self.assertIn("apparaît 3 fois", result)

    def test_count_occurrences_missing_file(self):
        result = tools.count_occurrences(os.path.join(self.dir, "nope.txt"), "x")
        self.assertIn("fichier introuvable", result)

    def test_count_occurrences_phrase(self):
        tools.write_file(os.path.join(self.dir, "text.txt"),
                         "bonjour le monde\nmonde entier\nbonjour le monde\n")
        result = tools.count_occurrences(os.path.join(self.dir, "text.txt"),
                                         "bonjour le monde")
        self.assertIn("apparaît 2 fois", result)

    def test_read_document_docx(self):
        file = os.path.join(self.dir, "doc.docx")
        xml = ("<w:document><w:body>"
               "<w:p><w:t>Bonjour les étudiants</w:t></w:p>"
               "<w:p><w:t>Deuxième paragraphe.</w:t></w:p>"
               "</w:body></w:document>")
        with open(file, "wb") as fh:
            fh.write(make_zip([("word/document.xml", xml)]))
        result = tools.read_document(file)
        self.assertIn("Bonjour les étudiants", result)
        self.assertIn("Deuxième paragraphe", result)

    def test_read_document_pptx(self):
        file = os.path.join(self.dir, "pres.pptx")
        slide = ("<a:sld><a:cSld><a:spTree>"
                 "<a:sp><a:txBody><a:p><a:r><a:t>Titre de la diapo</a:t></a:r>"
                 "</a:p></a:txBody></a:sp>"
                 "</a:spTree></a:cSld></a:sld>")
        with open(file, "wb") as fh:
            fh.write(make_zip([("ppt/slides/slide1.xml", slide)]))
        result = tools.read_document(file)
        self.assertIn("Diapositive 1", result)
        self.assertIn("Titre de la diapo", result)

    def test_read_document_xlsx(self):
        file = os.path.join(self.dir, "notes.xlsx")
        shared = "<sst><si><t>Pierre</t></si><si><t>Note</t></si></sst>"
        sheet = ("<worksheet><sheetData>"
                 '<row r="1"><c r="A1" t="s"><v>0</v></c>'
                 '<c r="B1" t="s"><v>1</v></c></row>'
                 '<row r="2"><c r="A2" t="s"><v>0</v></c><c r="B2"><v>92</v></c></row>'
                 "</sheetData></worksheet>")
        with open(file, "wb") as fh:
            fh.write(make_zip([
                ("xl/sharedStrings.xml", shared),
                ("xl/worksheets/sheet1.xml", sheet),
            ]))
        result = tools.read_document(file)
        self.assertIn("Feuille 1", result)
        self.assertIn("A1: Pierre", result)
        self.assertIn("B2: 92", result)

    def test_read_document_pdf(self):
        file = os.path.join(self.dir, "cours.pdf")
        with open(file, "wb") as fh:
            fh.write(make_pdf("BT /F1 12 Tf (Bonjour PDF) Tj ET"))
        result = tools.read_document(file)
        self.assertIn("Bonjour PDF", result)

    def test_read_document_missing_file(self):
        self.assertIn("ERREUR", tools.read_document(os.path.join(self.dir, "x.pdf")))


class LlmTests(unittest.TestCase):
    def test_parse_string_arguments(self):
        message = {"role": "assistant", "content": None,
                   "tool_calls": [{"id": "c1", "function": {
                       "name": "bash", "arguments": '{"command": "ls"}'}}]}
        calls = llm.parse_tool_calls(message)
        self.assertEqual(calls[0]["name"], "bash")
        self.assertEqual(calls[0]["arguments"]["command"], "ls")

    def test_parse_dict_arguments(self):
        message = {"role": "assistant", "content": None,
                   "tool_calls": [{"id": "c1", "function": {
                       "name": "read_file", "arguments": {"path": "a.py"}}}]}
        calls = llm.parse_tool_calls(message)
        self.assertEqual(calls[0]["arguments"]["path"], "a.py")

    def test_parse_no_calls(self):
        self.assertEqual(llm.parse_tool_calls({"content": "bonjour"}), [])

    def test_clean_message_roundtrip(self):
        raw = {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": "bash", "arguments": {"command": "ls"}}}]}
        cleaned = llm._clean_message(raw)
        self.assertIn("arguments", cleaned["tool_calls"][0]["function"])
        self.assertIsInstance(cleaned["tool_calls"][0]["function"]["arguments"], str)

    def test_repair_path_duplicated_root(self):
        self.assertEqual(tools._repair_path(r"C:\LaSalle\C:\LaSalle\f.pdf"),
                         r"C:\LaSalle\f.pdf")
        self.assertEqual(tools._repair_path(r"C:\LaSalle\f.pdf"), r"C:\LaSalle\f.pdf")
        self.assertEqual(tools._repair_path(""), "")
        self.assertEqual(tools._repair_path(r"D:\a\D:\a\x\y.txt"), r"D:\a\x\y.txt")

    def test_norm_op(self):
        self.assertEqual(tools._norm_op("integrale"), "integrale")
        self.assertEqual(tools._norm_op("intégrale"), "integrale")
        self.assertEqual(tools._norm_op("dérivée"), "derivee")
        self.assertEqual(tools._norm_op("équation"), "equation")
        self.assertEqual(tools._norm_op(""), "integrale")
        self.assertEqual(tools._norm_op("limite"), "limite")

    def test_prepare_expr_implicit_multiplication(self):
        self.assertEqual(tools._prepare_expr("x^2 - 5x + 6"), "x**2 - 5*x + 6")
        self.assertEqual(tools._prepare_expr("2x(x+1)"), "2*x*(x+1)")
        self.assertEqual(tools._prepare_expr("ln(x+1)"), "ln(x+1)")      # intact
        self.assertEqual(tools._prepare_expr("(x+1)(x-1)"), "(x+1)*(x-1)")

    def test_strip_integral_notation(self):
        self.assertEqual(tools._strip_integral("∫ln(x+1)dx"), ("ln(x+1)", "x"))
        self.assertEqual(tools._strip_integral("∫ ln(x + 1) dx"), ("ln(x + 1)", "x"))
        self.assertEqual(tools._strip_integral("ln(x+1)"), ("ln(x+1)", None))
        self.assertEqual(tools._strip_integral("∫(x^2 + 1)dx"), ("(x^2 + 1)", "x"))

    def test_calcul_symbolique_integrale_notation_entier(self):
        # L'étudiant écrit '∫ln(x+1)dx' : l'outil nettoie et calcule juste.
        out = tools.calcul_symbolique("∫ln(x+1)dx")
        self.assertIn("x*log(x + 1) - x + log(x + 1)", out)
        self.assertIn("CORRECT", out)
        self.assertNotIn("dx*", out)
        # Une intégrale non résolue doit renvoyer une ERREUR (pas un faux CORRECT).
        out2 = tools.calcul_symbolique("∫dx ln(x+1)")
        self.assertIn("ERREUR", out2)

    def test_calcul_symbolique_integrale_ln_x_plus_1(self):
        out = tools.calcul_symbolique("ln(x+1)", "integrale")
        self.assertIn("log(x + 1)", out)
        self.assertIn("x*log(x + 1) - x + log(x + 1)", out)
        self.assertIn("CORRECT", out)

    def test_calcul_symbolique_equation(self):
        out = tools.calcul_symbolique("x^2 - 5x + 6 = 0", "equation")
        self.assertIn("2", out)
        self.assertIn("3", out)

    def test_calcul_symbolique_derivee(self):
        out = tools.calcul_symbolique("x*exp(x)", "derivee")
        self.assertIn("(x + 1)*exp(x)", out)
        self.assertIn("CORRECT", out)


if __name__ == "__main__":
    unittest.main()
