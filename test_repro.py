import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from agent import run_agent

rep, hist = run_agent("calculer l'intégrale ∫ln(x+1)dx")
print("REPONSE:\n", rep[:1200])
print("\nOUTILS:")
for h in hist:
    if h.get("role") == "tool":
        print("  *", (h.get("content") or "")[:400].replace("\n", " ⏎ "))
for h in hist:
    if h.get("role") == "assistant" and h.get("tool_calls"):
        for c in h["tool_calls"]:
            print("  APPEL:", c["function"]["name"], c["function"]["arguments"])
