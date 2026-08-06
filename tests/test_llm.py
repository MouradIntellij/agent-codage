"""Tests de llm.parse_tool_calls et du filet « appel d'outil en JSON texte »."""

import unittest

import llm


class TestParseToolCalls(unittest.TestCase):

    def test_tool_call_structure_normalisee(self):
        msg = {
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "count_occurrences",
                             "arguments": '{"path": "a.txt", "term": "log"}'},
            }],
        }
        calls = llm.parse_tool_calls(msg)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "count_occurrences")
        self.assertEqual(calls[0]["arguments"], {"path": "a.txt", "term": "log"})

    def test_appel_ecrit_en_json_dans_le_texte(self):
        msg = {"role": "assistant",
               "content": ('Voici le calcul :\n{"name": "bash", "parameters": '
                           '{"command": "python -c \\"print(1)\\"", '
                           '"timeout": 10}}\nFin.')}
        calls = llm.parse_tool_calls(msg)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "bash")
        self.assertEqual(calls[0]["arguments"]["command"],
                         'python -c "print(1)"')
        self.assertEqual(calls[0]["id"], "textcall")

    def test_texte_normal_retourne_vide(self):
        msg = {"role": "assistant",
               "content": "L'intégrale de ln(x) est x*log(x) - x."}
        self.assertEqual(llm.parse_tool_calls(msg), [])

    def test_argument_json_invalide_devient_dict(self):
        msg = {"role": "assistant", "content": None,
               "tool_calls": [{
                   "id": "x", "type": "function",
                   "function": {"name": "bash", "arguments": "pas du json"},
               }]}
        calls = llm.parse_tool_calls(msg)
        self.assertEqual(calls[0]["name"], "bash")
        self.assertEqual(calls[0]["arguments"], {"_raw": "pas du json"})


if __name__ == "__main__":
    unittest.main()
