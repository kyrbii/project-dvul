"""
Werte-Eval (Test 2 von 3).

Prüft: Stimmen die geplotteten Zahlen?
Nimmt den gespeicherten Plot-Code des Modells, führt ihn neu in matplotlib aus,
liest Balkenwerte aus und vergleicht mit pandas-Referenzwerten (5 % Toleranz).
Erkennt automatisch vertikale (bar) und horizontale (barh) Balken.

Echte API-Calls → nur manuell starten:
    uv run python tests/eval/eval_plot_values.py
"""

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib

matplotlib.use("agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from fastapi.testclient import TestClient

from backend.main import app, chat_store

client = TestClient(app)

DATASET = "test_data/sales_sample.csv"
RUNS = 1
TOLERANCE = 0.05

# ── Referenzwerte (pandas aus sales_sample.csv, seed=42) ──────────────────────
REF_SALES_BY_CATEGORY = {
    "Technology": 133135,
    "Furniture": 96209,
    "Office Supplies": 47847,
}
REF_PROFIT_BY_REGION = {
    "South": 12125,
    "East": 11594,
    "West": 11579,
    "Central": 10643,
}

TEST_CASES = [
    {
        "question": "Erstelle ein Balkendiagramm mit dem Umsatz pro Kategorie",
        "ref": REF_SALES_BY_CATEGORY,
        "top_key": "Technology",
    },
    {
        "question": "Zeige mir den Profit pro Region als Balkendiagramm",
        "ref": REF_PROFIT_BY_REGION,
        "top_key": "South",
    },
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


def extract_bar_data(plot_code: str, df: pd.DataFrame) -> tuple[list[float], list[str]]:
    """Führt Plot-Code aus und gibt (Werte, Labels) zurück.

    Erkennt automatisch vertikale (bar) und horizontale (barh) Balken.
    Builtins bleiben verfügbar — das ist eine vertrauenswürdige manuelle Eval.
    """
    plt.close("all")
    ns: dict = {"plt": plt, "pd": pd, "df": df.copy(), "np": np, "sns": sns}
    try:
        exec(compile(plot_code, "<eval>", "exec"), ns)  # noqa: S102
    except Exception as exc:
        print(f"      [render-Fehler] {type(exc).__name__}: {exc}")
        return [], []

    if not plt.get_fignums():
        return [], []

    axes = plt.gcf().get_axes()
    if not axes:
        plt.close("all")
        return [], []
    ax = axes[0]

    # Vertikale Balken (bar / barplot)
    v_bars = [p for p in ax.patches if hasattr(p, "get_height") and p.get_height() > 1]
    if v_bars:
        values = [b.get_height() for b in v_bars]
        labels = [t.get_text().strip() for t in ax.get_xticklabels()]
        plt.close("all")
        return values, labels

    # Horizontale Balken (barh)
    h_bars = [p for p in ax.patches if hasattr(p, "get_width") and p.get_width() > 1]
    if h_bars:
        values = [b.get_width() for b in h_bars]
        labels = [t.get_text().strip() for t in ax.get_yticklabels()]
        plt.close("all")
        return values, labels

    plt.close("all")
    return [], []


def score_top_key(values: list[float], labels: list[str], expected_top: str) -> float:
    """1.0 wenn der größte Balken dem erwarteten Key entspricht."""
    if not values:
        return 0.0
    max_idx = values.index(max(values))
    if labels and max_idx < len(labels):
        top = labels[max_idx]
        return 1.0 if expected_top.lower() in top.lower() else 0.0
    # Kein Label: fallback auf Verhältnis-Check
    sv = sorted(values, reverse=True)
    return 0.5 if len(sv) >= 2 and sv[0] / sv[1] > 1.2 else 0.0


def score_value_accuracy(
    values: list[float], labels: list[str], ref: dict[str, int]
) -> float:
    """Anteil der Balken, deren Wert innerhalb TOLERANCE vom Referenzwert liegt."""
    if not values:
        return 0.0

    if not labels:
        # Kein Label-Match möglich; prüfe ob sortierte Werte zur Referenz passen
        ref_vals = sorted(ref.values(), reverse=True)
        got_vals = sorted(values, reverse=True)[: len(ref_vals)]
        matched = sum(
            1
            for g, r in zip(got_vals, ref_vals)
            if abs(g - r) / r <= TOLERANCE
        )
        return matched / len(ref_vals)

    matched, total = 0, 0
    for label, val in zip(labels, values):
        for key, expected in ref.items():
            if key.lower() in label.lower() or label.lower() in key.lower():
                total += 1
                if abs(val - expected) / expected <= TOLERANCE:
                    matched += 1
                break

    return matched / total if total > 0 else 0.0


def _report(label: str, scores: list[float]) -> None:
    if not scores:
        return
    m = statistics.mean(scores) * 100
    sd = (statistics.stdev(scores) * 100) if len(scores) > 1 else 0.0
    print(f"  {label:<28} {m:5.1f}%  (σ={sd:.1f}pp)")


# ── Eval-Durchlauf ────────────────────────────────────────────────────────────


def run_eval() -> None:
    df = pd.read_csv(DATASET)

    print(f"\n{'=' * 60}")
    print(f"Werte-Eval  ({RUNS} Läufe pro Frage)")
    print(f"{'=' * 60}\n")

    all_creation: list[float] = []
    all_top: list[float] = []
    all_acc: list[float] = []

    for case in TEST_CASES:
        q = case["question"]
        ref = case["ref"]
        top_key = case["top_key"]
        creation: list[float] = []
        top_scores: list[float] = []
        acc_scores: list[float] = []

        print(f"  Frage: {q}")
        print(f"  Referenz: {', '.join(f'{k}={v:,}' for k, v in ref.items())}")

        for run in range(RUNS):
            chat_id = upload()
            response = ask(chat_id, q)
            plots = chat_store.get(chat_id, {}).get("plots", [])

            has_plot = bool(response["response"]["plot_reference"])
            creation.append(1.0 if has_plot else 0.0)

            if has_plot and plots:
                code = plots[-1].get("code", "")
                values, labels = extract_bar_data(code, df)
                tc = score_top_key(values, labels, top_key)
                va = score_value_accuracy(values, labels, ref)
            else:
                tc = va = 0.0

            top_scores.append(tc)
            acc_scores.append(va)
            print(
                f"    [{run + 1}] Plot:{str(has_plot):5}  "
                f"TopKey:{tc:.2f}  ValueAcc:{va:.2f}"
            )

        all_creation.extend(creation)
        all_top.extend(top_scores)
        all_acc.extend(acc_scores)

        cm = statistics.mean(creation) * 100
        tm = statistics.mean(top_scores) * 100
        am = statistics.mean(acc_scores) * 100
        ts = (statistics.stdev(top_scores) * 100) if len(top_scores) > 1 else 0.0
        as_ = (statistics.stdev(acc_scores) * 100) if len(acc_scores) > 1 else 0.0
        print(
            f"    Ø  Plot:{cm:.0f}%  "
            f"TopKey:{tm:.0f}% (σ={ts:.0f})  "
            f"Acc:{am:.0f}% (σ={as_:.0f})\n"
        )

    print(f"{'=' * 60}")
    print("GESAMT")
    _report("Plot-Erstellung:", all_creation)
    _report("Top-Wert korrekt:", all_top)
    _report("Werte-Genauigkeit:", all_acc)
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    run_eval()
