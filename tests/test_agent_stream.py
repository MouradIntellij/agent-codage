"""Tests de la boucle avec streaming (run_agent_stream).

On ne contacte PAS Ollama : llm.chat_stream est remplacé par un faux qui
diffuse des morceaux scriptés, pour vérifier la logique de la boucle
(porte de décision, outils, historique).
"""

import os
import tempfile
import unittest
from unittest.mock import patch

import agent


class FakeChatStream:
    """Renvoie des messages scriptés et capture les deltas diffusés."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.deltas = []
        self.calls = []

    def __call__(self, messages, tools=None, on_delta=None):
        self.calls.append({"messages": list(messages), "tools": tools})
        reply = self.replies.pop(0)
        for mot in (reply.get("content") or "").split(" "):
            if mot and on_delta:
                on_delta(mot + " ")
        return reply


class TestRunAgentStream(unittest.TestCase):

    def test_demande_de_code_repond_sans_outils(self):
        fake = FakeChatStream([
            {"role": "assistant", "content": "Voici le code :\nprint(1)"},
        ])
        deltas = []
        with patch.object(agent.llm, "chat_stream", fake):
            response, history = agent.run_agent_stream(
                "donne-moi le code en python pour lire un pdf",
                on_delta=deltas.append)
        self.assertIn("Voici le code", response)
        self.assertEqual(len(fake.calls), 1)
        # Aucun outil annoncé : le modèle ne peut pas chercher de fichier.
        self.assertIsNone(fake.calls[0]["tools"])
        # Le texte a bien été diffusé morceau par morceau.
        self.assertIn("Voici le code", "".join(deltas))
        self.assertEqual(history[-1]["content"], "Voici le code :\nprint(1)")

    def test_demande_d_explication_repond_sans_outils(self):
        fake = FakeChatStream([
            {"role": "assistant",
             "content": "Cette fonction convertit les appels d'outils en liste."},
        ])
        deltas = []
        with patch.object(agent.llm, "chat_stream", fake):
            response, history = agent.run_agent_stream(
                "expliquez moi ce code\nexport function parseToolCalls() {}",
                on_delta=deltas.append)
        self.assertIn("liste", response)
        self.assertEqual(len(fake.calls), 1)
        self.assertIsNone(fake.calls[0]["tools"])
        self.assertEqual(history[-1]["content"],
                         "Cette fonction convertit les appels d'outils en liste.")
        # La directive d'explication est bien injectée.
        self.assertIn("pédagogique", fake.calls[0]["messages"][-1]["content"])

    def test_suite_d_explication_repond_sans_outils(self):
        fake = FakeChatStream([
            {"role": "assistant", "content": "C'est la boucle ReAct de l'agent."},
        ])
        deltas = []
        with patch.object(agent.llm, "chat_stream", fake):
            response, _ = agent.run_agent_stream(
                "et ce code\nfor (let step = 0; step < config.maxIterations; step++) {}",
                on_delta=deltas.append)
        self.assertEqual(len(fake.calls), 1)
        self.assertIsNone(fake.calls[0]["tools"])
        self.assertIn("ReAct", response)

    def test_ce_code_avec_verbe_d_action_garde_les_outils(self):
        target = os.path.join(tempfile.gettempdir(), "cecode_test.py")
        if os.path.exists(target):
            os.remove(target)
        appel = {
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "write_file",
                             "arguments": {"path": target, "content": "x = 1"}},
            }],
        }
        final = {"role": "assistant", "content": "Fait."}
        fake = FakeChatStream([appel, final])
        with patch.object(agent.llm, "chat_stream", fake):
            response, _ = agent.run_agent_stream("corrige ce code puis crée le fichier")
        self.assertIsNotNone(fake.calls[0]["tools"])
        self.assertEqual(response, "Fait.")
        self.assertTrue(os.path.exists(target))
        os.remove(target)

    def test_direct_mode_relance_si_reponse_en_json(self):
        mauvais = {"role": "assistant",
                   "content": '{"name":"listZipEntries","parameters":{}}'}
        bon = {"role": "assistant",
               "content": "Voici l'explication pédagogique de la fonction."}
        fake = FakeChatStream([mauvais, bon])
        with patch.object(agent.llm, "chat", fake):
            response, _ = agent.run_agent_stream(
                "et ce code\nfunction listZipEntries(buffer: Buffer) {}")
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(response, "Voici l'explication pédagogique de la fonction.")
        self.assertIsNone(fake.calls[0]["tools"])
        self.assertIsNone(fake.calls[1]["tools"])
        # Le message de relance demande une réponse en texte normal.
        self.assertIn("texte français normal", fake.calls[1]["messages"][-1]["content"])

    def test_action_utilise_outils_puis_repond(self):
        target = os.path.join(tempfile.gettempdir(), "stream_test_bonjour.py")
        if os.path.exists(target):
            os.remove(target)
        appel = {
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "write_file",
                             "arguments": {"path": target,
                                           "content": "print('bonjour')"}},
            }],
        }
        final = {"role": "assistant", "content": "Fait."}
        fake = FakeChatStream([appel, final])
        deltas = []
        seen_tools = []
        with patch.object(agent.llm, "chat_stream", fake):
            response, history = agent.run_agent_stream(
                "cree le fichier de test",
                on_delta=deltas.append,
                on_tool=lambda call, result: seen_tools.append(call["name"]))
        self.assertEqual(response, "Fait.")
        self.assertTrue(os.path.exists(target))
        self.assertEqual(seen_tools, ["write_file"])
        self.assertEqual(len(fake.calls), 2)
        # Les outils sont annoncés dans la boucle (contrairement au mode code).
        self.assertIsNotNone(fake.calls[0]["tools"])
        self.assertEqual("".join(deltas).strip(), "Fait.")
        os.remove(target)

    def test_plan_sans_action_declenche_linjonction(self):
        # Le modèle promet de calculer sans exécuter d'outil : la boucle doit
        # lui renvoyer une injonction (PENDING_NUDGE) au lieu de s'arrêter.
        plan = {"role": "assistant",
                "content": "Je vais calculer l'intégrale avec SymPy."}
        final = {"role": "assistant", "content": "Résultat vérifié : x*log(x) - x."}
        fake = FakeChatStream([plan, final])
        with patch.object(agent.llm, "chat_stream", fake):
            response, history = agent.run_agent_stream("calcule l'intégrale de ln(x)")
        self.assertEqual(response, "Résultat vérifié : x*log(x) - x.")
        self.assertEqual(len(fake.calls), 2)
        self.assertIn(agent.PENDING_NUDGE,
                      fake.calls[1]["messages"][-1]["content"])

    def test_pas_de_nudge_apres_un_outil(self):
        # Après un vrai appel d'outil, une mention rhétorique (« nous pouvons
        # utiliser les règles de l'intégrale ») ne doit PAS relancer la boucle.
        appel = {
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "bash",
                             "arguments": {"command": "python -c \"print(1)\""}},
            }],
        }
        final = {"role": "assistant",
                 "content": "Le résultat est x*log(x) - x : nous pouvons "
                            "utiliser les règles de l'intégrale."}
        fake = FakeChatStream([appel, final])
        with patch.object(agent.llm, "chat_stream", fake):
            response, _ = agent.run_agent_stream("calcule l'intégrale de ln(x)")
        self.assertEqual(response, "Le résultat est x*log(x) - x : nous pouvons "
                                   "utiliser les règles de l'intégrale.")
        self.assertEqual(len(fake.calls), 2)


if __name__ == "__main__":
    unittest.main()
