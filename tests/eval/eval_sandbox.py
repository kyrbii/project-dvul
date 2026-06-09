import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
from backend.llm.sandbox import execute_plot_code

# Testdaten
df = pd.DataFrame(
    {"category": ["Tech", "Furniture", "Office"], "sales": [1000, 500, 750]}
)


def test_valid_plot_code_returns_svg():
    code = "plt.bar(df['category'], df['sales'])"
    result = execute_plot_code(code, df)
    assert result.startswith("<?xml") or "<svg" in result


def test_plot_code_without_figure_returns_error():
    code = "x = 1 + 1"  # kein Plot
    result = execute_plot_code(code, df)
    assert "Error" in result


def test_invalid_code_returns_sandbox_error():
    code = "plt.bar(df['nonexistent'], df['sales'])"
    result = execute_plot_code(code, df)
    assert "Sandbox Error" in result


def test_markdown_code_block_is_cleaned():
    code = "```python\nplt.bar(df['category'], df['sales'])\n```"
    result = execute_plot_code(code, df)
    assert "<svg" in result


# ── Sicherheitstests ──────────────────────────────────────


def test_sandbox_blocks_open():
    code = "open('/etc/passwd')"
    result = execute_plot_code(code, df)
    assert "Error" in result


def test_sandbox_blocks_eval():
    code = "eval('1+1')"
    result = execute_plot_code(code, df)
    assert "Error" in result
