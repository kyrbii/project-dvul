"""
Visueller Judge-Eval — orientiert an MatPlotAgent / MatPlotBench
(Yang et al. 2024, arXiv:2402.11453).

Kernidee aus dem Paper, hier 1:1 übernommen:
  - Pro Testfall existiert eine Ground-Truth-Figur (von Menschen verifiziert).
  - Ein multimodales LLM ("Judge") sieht die vom Modell erzeugte Figur UND die
    Referenz-Figur und vergibt einen Score 0–100, wie gut die generierte Figur
    die Frage korrekt beantwortet bzw. der Referenz entspricht.
  - Die Verlässlichkeit des Judges wird gegen menschliche Bewertungen validiert
    (Korrelation) — ohne diesen Schritt ist ein LLM-Judge nicht belastbar.

Unterschied zum alten eval_judge.py:
  - Judge sieht das gerenderte BILD, nicht nur Code + Titel + Bot-Text.
  - Es gibt eine Ground-Truth-Referenzfigur pro Fall.
  - Judge-/Render-Fehler werden AUSGESCHLOSSEN, nicht auf einen Mittelwert
    gesetzt (das alte `return 3` maskierte Totalausfälle).
  - Score wird strikt aus dem Format "[[N]]" geparst (robuster als "erste Zahl").
  - Optionaler Modus zur Validierung gegen menschliche Scores.

Echte API-Calls + multimodales Modell -> NICHT in die CI, nur manuell:
    uv run python tests/eval/eval_judge_visual.py
    uv run python tests/eval/eval_judge_visual.py --save-images runs/
    uv run python tests/eval/eval_judge_visual.py --correlate runs/human_scores.csv
"""

import argparse
import base64
import csv
import io
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib

matplotlib.use("agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    import seaborn as sns
except ImportError:  # seaborn ist optional
    sns = None

from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from backend.llm.llm_instance import get_llm_instance
from backend.main import app, chat_store

client = TestClient(app)

# ── An EUREN Datensatz anpassen ───────────────────────────────────────────────
# Standard-Superstore-Spalten. Wenn euer CSV andere Namen nutzt, hier ändern —
# davon hängen NUR die Referenz-Figuren ab (der Modell-Code wird unverändert
# gegen das echte df ausgeführt).
DATASET = "test_data/Sample - Superstore.csv"
CATEGORY_COL = "Category"
SALES_COL = "Sales"
REGION_COL = "Region"
PROFIT_COL = "Profit"
DATE_COL = "Order Date"

RUNS_PER_QUESTION = 1


# ── Judge-Prompt (Paper-Stil: Bild vs. Referenz, 0–100) ───────────────────────
# Bewusst auf "beantwortet die Frage / gleiche Daten & Diagrammtyp" formuliert
# statt auf pixelgenaue Übereinstimmung — Farbe, Sortierung, Bar vs. Barh sind
# legitime Freiheitsgrade und sollen nicht bestraft werden.
JUDGE_PROMPT = """\
Du bist ein objektiver Bewerter für Datenvisualisierungen.

Du erhältst zwei Bilder:
  1. die REFERENZ-Figur (Ground Truth, von Experten verifiziert),
  2. die vom Modell ERZEUGTE Figur.

Frage des Nutzers:
{question}

Bewerte, wie gut die erzeugte Figur die Frage des Nutzers beantwortet und mit
der Referenz übereinstimmt. Berücksichtige: richtiger Diagrammtyp, korrekte
Daten/Aggregation, sinnvolle Achsen und Beschriftung, Lesbarkeit. Stilistische
Unterschiede (Farben, Reihenfolge, horizontal vs. vertikal) sind KEIN Mangel,
solange dieselbe Information korrekt dargestellt wird.

Gib zuerst eine kurze Begründung (1–2 Sätze). Beende deine Antwort dann strikt
mit einer Zahl von 0 bis 100 im Format "[[Zahl]]", z. B. "[[85]]"."""


# ── Testfälle mit Ground-Truth-Referenzcode ───────────────────────────────────
# Referenz-Figuren werden aus den BEKANNTEN korrekten Aggregaten gerendert.
# Bekannte Superstore-Fakten: Technology = höchster Umsatz, West = höchster
# Profit, Furniture = niedrigste Profit-Margin.
TEST_CASES = [
    {
        "name": "umsatz_pro_kategorie",
        "question": "Zeige mir den Umsatz pro Kategorie als Balkendiagramm",
        "reference_code": f"""
agg = df.groupby({CATEGORY_COL!r})[{SALES_COL!r}].sum().sort_values(ascending=False)
plt.figure(figsize=(7, 4))
plt.bar(agg.index.astype(str), agg.values, color="#4c72b0")
plt.title("Umsatz pro Kategorie (Referenz)")
plt.ylabel("Umsatz")
plt.xlabel("Kategorie")
plt.tight_layout()
""",
    },
    {
        "name": "profit_pro_region",
        "question": "Zeige mir den Profit pro Region als Diagramm",
        "reference_code": f"""
agg = df.groupby({REGION_COL!r})[{PROFIT_COL!r}].sum().sort_values(ascending=False)
plt.figure(figsize=(7, 4))
plt.bar(agg.index.astype(str), agg.values, color="#55a868")
plt.title("Profit pro Region (Referenz)")
plt.ylabel("Profit")
plt.xlabel("Region")
plt.tight_layout()
""",
    },
    {
        "name": "umsatztrend",
        "question": "Zeige mir den Umsatztrend über die Zeit als Liniendiagramm",
        "reference_code": f"""
d = df.copy()
d[{DATE_COL!r}] = pd.to_datetime(d[{DATE_COL!r}])
ts = d.groupby(d[{DATE_COL!r}].dt.to_period("M"))[{SALES_COL!r}].sum()
ts.index = ts.index.to_timestamp()
plt.figure(figsize=(8, 4))
plt.plot(ts.index, ts.values, color="#c44e52")
plt.title("Umsatztrend pro Monat (Referenz)")
plt.ylabel("Umsatz")
plt.xlabel("Zeit")
plt.tight_layout()
""",
    },
    {
        "name": "marge_pro_kategorie",
        "question": "Zeige mir die Profit-Margin pro Kategorie als Diagramm",
        "reference_code": f"""
g = df.groupby({CATEGORY_COL!r})
margin = (g[{PROFIT_COL!r}].sum() / g[{SALES_COL!r}].sum() * 100).sort_values()
plt.figure(figsize=(7, 4))
plt.bar(margin.index.astype(str), margin.values, color="#8172b3")
plt.title("Profit-Margin (%) pro Kategorie (Referenz)")
plt.ylabel("Marge in %")
plt.xlabel("Kategorie")
plt.tight_layout()
""",
    },
]


# ── Rendering ─────────────────────────────────────────────────────────────────


def render_png(code: str, df: pd.DataFrame) -> bytes | None:
    """Führt Plot-Code aus und gibt das Bild als PNG-Bytes zurück (oder None).

    Bewusst MIT normalen Builtins: das ist eine vertrauenswürdige manuelle Eval,
    kein Produktivpfad. (Die Sicherheits-Sandbox wird separat in den
    sandbox-Tests geprüft.) Echter Plot-Code braucht Builtins wie len/zip/range.
    """
    plt.close("all")
    ns: dict = {"plt": plt, "pd": pd, "np": np, "df": df.copy()}
    if sns is not None:
        ns["sns"] = sns
    try:
        exec(code, ns)  # noqa: S102 — manuelle Eval, kein User-Input
    except Exception as exc:
        print(f"      [render-Fehler] {type(exc).__name__}: {exc}")
        return None
    if not plt.get_fignums():
        return None
    buf = io.BytesIO()
    plt.gcf().savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close("all")
    return buf.getvalue()


def to_data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode()


# ── Pipeline-Aufrufe ──────────────────────────────────────────────────────────


def upload() -> str:
    with open(DATASET, "rb") as f:
        resp = client.post(
            "/upload-csv",
            files={"file": (Path(DATASET).name, f, "text/csv")},
        )
    resp.raise_for_status()
    return resp.json()["chat_id"]


def ask(chat_id: str, message: str) -> dict:
    resp = client.post("/chat", json={"chat_id": chat_id, "message": message})
    resp.raise_for_status()
    return resp.json()


def get_model_plot_code(chat_id: str, response: dict) -> str | None:
    """Plot-Code der letzten erzeugten Figur, oder None wenn kein Plot kam."""
    if not response["response"].get("plot_reference"):
        return None
    plots = chat_store.get(chat_id, {}).get("plots", [])
    if not plots:
        return None
    return plots[-1].get("code") or None


# ── Judge ─────────────────────────────────────────────────────────────────────


def get_vision_llm():
    """Muss ein MULTIMODALES Modell liefern (Bilder im Input).

    Das Standard-Modell (nvidia/nemotron-...) unterstützt kein Vision.
    Setze OPENROUTER_VISION_MODEL in .env auf ein vision-fähiges Modell,
    z. B. "openai/gpt-4o" oder "anthropic/claude-3.5-sonnet".
    """
    import os

    vision_model = os.getenv("OPENROUTER_VISION_MODEL")
    if vision_model:
        return get_llm_instance(model_name=vision_model)
    print(
        "  [WARNUNG] OPENROUTER_VISION_MODEL nicht gesetzt.\n"
        "  Setze z. B. OPENROUTER_VISION_MODEL=openai/gpt-4o in .env.\n"
        "  Das Standardmodell unterstützt wahrscheinlich kein Vision — "
        "Judge-Aufrufe werden fehlschlagen."
    )
    return get_llm_instance()


def parse_score(text: str) -> int | None:
    """Score 0–100 strikt aus '[[N]]' parsen, sonst letzte Zahl als Fallback."""
    m = re.search(r"\[\[\s*(\d{1,3})\s*\]\]", text)
    if m:
        return max(0, min(100, int(m.group(1))))
    nums = re.findall(r"\b\d{1,3}\b", text)
    return max(0, min(100, int(nums[-1]))) if nums else None


def judge_score(question: str, model_png: bytes, ref_png: bytes) -> int | None:
    """Ruft den Vision-Judge auf. Gibt 0–100 zurück oder None bei API-Fehler."""
    llm = get_vision_llm()
    content = [
        {"type": "text", "text": JUDGE_PROMPT.format(question=question)},
        {"type": "text", "text": "REFERENZ-Figur (Ground Truth):"},
        {"type": "image_url", "image_url": {"url": to_data_url(ref_png)}},
        {"type": "text", "text": "Vom Modell ERZEUGTE Figur:"},
        {"type": "image_url", "image_url": {"url": to_data_url(model_png)}},
    ]
    try:
        resp = llm.invoke([HumanMessage(content=content)])
        return parse_score(resp.content.strip())
    except Exception as exc:
        print(f"      [Judge-Fehler] {type(exc).__name__}: {exc}")
        return None


# ── Eval-Durchlauf ────────────────────────────────────────────────────────────


def run_eval(save_dir: Path | None = None) -> None:
    df = pd.read_csv(DATASET)

    # Referenz-Figuren einmal rendern (ändern sich über Läufe nicht).
    references: dict[str, bytes] = {}
    for case in TEST_CASES:
        ref = render_png(case["reference_code"], df)
        if ref is None:
            print(
                f"!! Referenz für '{case['name']}' konnte nicht gerendert werden "
                f"— Spaltennamen im CONFIG-Block prüfen."
            )
        references[case["name"]] = ref
        if save_dir is not None and ref is not None:
            (save_dir / f"{case['name']}_reference.png").write_bytes(ref)

    rows: list[dict] = []  # für --save-images / Human-Korrelation
    all_scores: list[int] = []
    judge_failures = 0

    print(f"\n{'=' * 64}")
    print(f"Visueller Judge-Eval (Bild vs. Referenz)  —  {RUNS_PER_QUESTION} Läufe/Frage")
    print(f"Datensatz: {DATASET}")
    print(f"{'=' * 64}\n")

    for case in TEST_CASES:
        ref_png = references[case["name"]]
        if ref_png is None:
            print(f"  Frage übersprungen (keine Referenz): {case['question']}\n")
            continue

        case_scores: list[int] = []
        print(f"  Frage: {case['question']}")

        for run in range(RUNS_PER_QUESTION):
            chat_id = upload()
            response = ask(chat_id, case["question"])
            code = get_model_plot_code(chat_id, response)

            if code is None:
                # Plot-Anfrage, aber kein Plot erzeugt -> echter Fehlschlag.
                score = 0
                model_png = None
                print(f"    [{run + 1}] kein Plot erzeugt            -> 0")
            else:
                model_png = render_png(code, df)
                if model_png is None:
                    score = 0  # Code lieferte keine Figur -> Fehlschlag
                    print(f"    [{run + 1}] Code rendert nicht          -> 0")
                else:
                    judged = judge_score(case["question"], model_png, ref_png)
                    if judged is None:
                        judge_failures += 1
                        print(f"    [{run + 1}] Judge nicht verfügbar (ausgeschlossen)")
                        continue  # NICHT in den Schnitt aufnehmen
                    score = judged
                    print(f"    [{run + 1}] Score: {score}/100")

            case_scores.append(score)
            all_scores.append(score)

            if save_dir is not None:
                img_path = ""
                if model_png is not None:
                    img_path = str(save_dir / f"{case['name']}_run{run + 1}.png")
                    Path(img_path).write_bytes(model_png)
                rows.append(
                    {
                        "case": case["name"],
                        "run": run + 1,
                        "judge_score": score,
                        "model_image": img_path,
                        "human_score": "",  # vom Menschen auszufüllen
                    }
                )

        if case_scores:
            mean = statistics.mean(case_scores)
            sd = statistics.stdev(case_scores) if len(case_scores) > 1 else 0.0
            print(f"    Ø {mean:.1f}/100  (σ={sd:.1f})\n")

    # ── Ergebnis ──
    print(f"{'=' * 64}")
    print("ERGEBNIS")
    if all_scores:
        mean = statistics.mean(all_scores)
        sd = statistics.stdev(all_scores) if len(all_scores) > 1 else 0.0
        print(f"  GESAMT: {mean:.1f}/100  (σ={sd:.1f}, n={len(all_scores)})")
    else:
        print("  Keine bewertbaren Läufe.")
    if judge_failures:
        print(f"  Judge-Ausfälle (ausgeschlossen): {judge_failures}")
    print(f"{'=' * 64}\n")

    if save_dir is not None:
        csv_path = save_dir / "human_scores.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["case", "run", "judge_score", "model_image", "human_score"]
            )
            writer.writeheader()
            writer.writerows(rows)
        print(f"  Bilder + Vorlage gespeichert: {csv_path}")
        print("  -> 'human_score' (0–100) von Hand ausfüllen, dann:")
        print(f"     uv run python {Path(__file__).name} --correlate {csv_path}\n")


# ── Validierung gegen menschliche Scores (Paper-Schritt) ──────────────────────


def correlate(csv_path: str) -> None:
    """Korrelation Judge vs. Mensch — belegt, ob der Judge verlässlich ist."""
    judge_scores: list[float] = []
    human_scores: list[float] = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("human_score", "").strip() == "":
                continue
            judge_scores.append(float(row["judge_score"]))
            human_scores.append(float(row["human_score"]))

    n = len(judge_scores)
    print(f"\n{'=' * 64}")
    print(f"Judge-Validierung: {n} von Menschen bewertete Läufe")
    print(f"{'=' * 64}")
    if n < 3:
        print("  Zu wenige Bewertungen (mind. 3) für eine Korrelation.\n")
        return

    try:
        from scipy.stats import pearsonr, spearmanr

        r, rp = pearsonr(judge_scores, human_scores)
        rho, sp = spearmanr(judge_scores, human_scores)
        print(f"  Pearson  r = {r:+.3f}  (p={rp:.3g})")
        print(f"  Spearman ρ = {rho:+.3f}  (p={sp:.3g})")
    except ImportError:
        # Fallback ohne scipy: Pearson manuell.
        mj, mh = statistics.mean(judge_scores), statistics.mean(human_scores)
        cov = sum((j - mj) * (h - mh) for j, h in zip(judge_scores, human_scores))
        dj = sum((j - mj) ** 2 for j in judge_scores) ** 0.5
        dh = sum((h - mh) ** 2 for h in human_scores) ** 0.5
        r = cov / (dj * dh) if dj and dh else float("nan")
        print(f"  Pearson r = {r:+.3f}  (scipy für p-Wert/Spearman installieren)")

    print("  (Im Paper gilt r > 0.8 als verlässlicher Judge.)")
    print(f"{'=' * 64}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visueller Judge-Eval")
    parser.add_argument(
        "--save-images",
        metavar="DIR",
        nargs="?",
        const=str(Path(__file__).parent / "runs"),
        help="Bilder + CSV-Vorlage speichern (Standard: tests/eval/runs/)",
    )
    parser.add_argument(
        "--correlate",
        metavar="CSV",
        help="Korrelation Judge vs. Mensch aus ausgefüllter CSV berechnen",
    )
    args = parser.parse_args()

    if args.correlate:
        correlate(args.correlate)
    else:
        out = Path(args.save_images) if args.save_images else None
        if out is not None:
            out.mkdir(parents=True, exist_ok=True)
        run_eval(save_dir=out)