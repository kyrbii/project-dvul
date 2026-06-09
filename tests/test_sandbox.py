import pandas as pd

from backend.llm.sandbox import execute_plot_code


def test_execute_plot_code_returns_svg():
    df = pd.DataFrame({"x": [1, 2, 3], "y": [2, 4, 8]})

    svg = execute_plot_code(
        """
import matplotlib.pyplot as plt
plt.plot(df["x"], df["y"])
plt.title("Growth")
plt.xlabel("x")
plt.ylabel("y")
""",
        df,
    )

    assert svg.lstrip().startswith("<?xml")
    assert "<svg" in svg


def test_execute_plot_code_rejects_filesystem_imports():
    df = pd.DataFrame({"x": [1]})

    result = execute_plot_code(
        """
import os
plt.plot(df["x"])
""",
        df,
    )

    assert result.startswith("Sandbox Error:")
    assert "Import of 'os' is not allowed" in result


def test_execute_plot_code_rejects_library_file_io():
    df = pd.DataFrame({"x": [1]})

    result = execute_plot_code(
        """
pd.read_csv("/etc/passwd")
plt.plot(df["x"])
""",
        df,
    )

    assert result.startswith("Sandbox Error:")
    assert "Use of 'read_csv' is not allowed" in result


def test_execute_plot_code_times_out():
    df = pd.DataFrame({"x": [1]})

    result = execute_plot_code(
        """
while True:
    pass
""",
        df,
    )

    assert result.startswith("Sandbox Error:")
