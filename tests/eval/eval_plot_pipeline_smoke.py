"""
Pipeline-Smoke-Eval (Test 1 von 3).

Prüft: Funktioniert die Mechanik?
  - Plot-Fragen erzeugen einen Plot (kein Absturz, kein stilles Schweigen).
  - Das vom /plots-Endpoint ausgelieferte SVG ist wohlgeformt (XML-parsebar).
  - Text-Fragen erzeugen KEINEN Plot (Negativfall).
  - LLM liefert eine textuelle Erklärung.

Was diese Eval NICHT prüft:
  - Inhaltliche Korrektheit der Zahlenwerte (→ eval_plot_values.py)
  - Ob der Diagrammtyp zur Frage passt (→ eval_judge_visual.py)

Echte API-Calls → nur manuell starten:
    uv run python tests/eval/eval_plot_pipeline_smoke.py
"""

import statistics
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

DATASET = "test_data/sales_sample.csv"
RUNS_PER_QUESTION = 1


# ── Testfälle ─────────────────────────────────────────────────────────────────

PLOT_QUESTIONS = [
    "Erstelle ein Balkendiagramm mit dem Umsatz pro Kategorie",
    "Zeige mir den Profit pro Region als Diagramm",
    "Visualisiere die Verteilung der Umsätze",
]

# Bei diesen Fragen erwarten wir ausdrücklich KEINEN Plot.
TEXT_QUESTIONS = [
    "Welche Kategorie hat den höchsten Umsatz?",
    "Fasse die wichtigsten Erkenntnisse zusammen",
]


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────


def upload() -> str:
    with open(DATASET, "rb") as f:
        resp = client.post(
            "/upload-csv",
            files={"file": ("sales_sample.csv", f, "text/csv")},
        )
    resp.raise_for_status()
    return resp.json()["chat_id"]


def ask(chat_id: str, message: str) -> dict:
    resp = client.post("/chat", json={"chat_id": chat_id, "message": message})
    resp.raise_for_status()
    return resp.json()


def get_plot_svg(chat_id: str, plot_index: int) -> str:
    resp = client.get(f"/plots/{chat_id}/{plot_index}")
    return resp.text if resp.status_code == 200 else ""


def is_valid_svg(svg: str) -> bool:
    """Echter XML-Parse statt String-Suche."""
    try:
        ET.fromstring(svg)
        return True
    except ET.ParseError:
        return False


def _report(label: str, scores: list[float]) -> None:
    if not scores:
        return
    m = statistics.mean(scores) * 100
    sd = (statistics.stdev(scores) * 100) if len(scores) > 1 else 0.0
    print(f"  {label:<32} {m:5.1f}%  (σ={sd:.1f}pp)")


# ── Scoring ───────────────────────────────────────────────────────────────────


def score_plot_created(response: dict) -> float:
    return 1.0 if response["response"]["plot_reference"] else 0.0


def score_no_plot(response: dict) -> float:
    return 1.0 if not response["response"]["plot_reference"] else 0.0


def score_svg_valid(chat_id: str, response: dict) -> float:
    refs = response["response"]["plot_reference"]
    if not refs:
        return 0.0
    valid = sum(1 for idx in refs if is_valid_svg(get_plot_svg(chat_id, idx)))
    return valid / len(refs)


def score_explanation(response: dict) -> float:
    msg = response["response"].get("bot_message", "")
    return 1.0 if msg and len(msg) > 50 else 0.0


# ── Eval-Durchlauf ────────────────────────────────────────────────────────────


def run_eval() -> None:
    all_plot_created: list[float] = []
    all_svg_valid: list[float] = []
    all_explanation_plot: list[float] = []
    all_no_plot_on_text: list[float] = []
    all_explanation_text: list[float] = []

    print(f"\n{'=' * 60}")
    print(f"Pipeline-Smoke-Eval  ({RUNS_PER_QUESTION} Läufe pro Frage)")
    print(f"{'=' * 60}\n")

    print("--- Plot-Fragen ---")
    for question in PLOT_QUESTIONS:
        q_c: list[float] = []
        q_s: list[float] = []
        for run in range(RUNS_PER_QUESTION):
            chat_id = upload()
            response = ask(chat_id, question)

            c = score_plot_created(response)
            s = score_svg_valid(chat_id, response)
            e = score_explanation(response)

            q_c.append(c)
            q_s.append(s)
            all_plot_created.append(c)
            all_svg_valid.append(s)
            all_explanation_plot.append(e)

            print(
                f"  [{run + 1}] {question[:42]:<42}  "
                f"Plot:{c:.0f}  SVG:{s:.2f}  Text:{e:.0f}"
            )
        cm = statistics.mean(q_c) * 100
        sm = statistics.mean(q_s) * 100
        print(f"       Ø  Plot:{cm:.0f}%  SVG:{sm:.0f}%\n")

    print("--- Text-Fragen (kein Plot erwartet) ---")
    for question in TEXT_QUESTIONS:
        q_np: list[float] = []
        for run in range(RUNS_PER_QUESTION):
            chat_id = upload()
            response = ask(chat_id, question)

            np_score = score_no_plot(response)
            e = score_explanation(response)

            q_np.append(np_score)
            all_no_plot_on_text.append(np_score)
            all_explanation_text.append(e)

            print(
                f"  [{run + 1}] {question[:42]:<42}  "
                f"KeinPlot:{np_score:.0f}  Text:{e:.0f}"
            )
        npm = statistics.mean(q_np) * 100
        print(f"       Ø  KeinPlot:{npm:.0f}%\n")

    print(f"{'=' * 60}")
    print("ERGEBNIS")
    _report("Plot-Erstellung (Plot-Fragen):", all_plot_created)
    _report("SVG-Gültigkeit (XML-Parse):", all_svg_valid)
    _report("Texterklärung (Plot-Fragen):", all_explanation_plot)
    _report("Kein Plot bei Text-Fragen:", all_no_plot_on_text)
    _report("Texterklärung (Text-Fragen):", all_explanation_text)
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    run_eval()
