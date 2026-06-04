import io
import logging
import matplotlib
matplotlib.use('agg')

import matplotlib.pyplot as plt
import pandas as pd

logger = logging.getLogger(__name__)

def execute_plot_code(code: str, df: pd.DataFrame) -> str:
    """
    Executes matplotlib code in a hardened in-memory environment.
    Returns the SVG string of the generated plot.
    """
    # We'll run the code in a separate, hardened process (sandbox_runner.py)
    import subprocess
    import tempfile
    import textwrap
    import sys
    import ast
    import os
    import seaborn as sns
    import numpy as np

    # Clean code (remove markdown fences if present)
    code = code.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        if len(lines) > 2:
            code = "\n".join(lines[1:-1])
        else:
            code = code.replace("```python", "").replace("```", "").strip()

    # Quick AST check here before launching subprocess
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return "Sandbox Error: import statements are not allowed."
            if isinstance(node, ast.Attribute) and getattr(node, 'attr', '').startswith('__'):
                return "Sandbox Error: access to dunder attributes is disallowed."
    except Exception as e:
        return f"Sandbox Error: invalid code ({e})"

    runner_path = os.path.join(os.path.dirname(__file__), 'sandbox_runner.py')

    # Write code and dataframe to temp files and invoke runner
    with tempfile.TemporaryDirectory() as td:
        code_file = os.path.join(td, 'code.py')
        csv_file = os.path.join(td, 'data.csv')
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        # Write dataframe as CSV to avoid pickling untrusted data
        df.to_csv(csv_file, index=False)

        try:
            proc = subprocess.run([
                sys.executable, runner_path, code_file, csv_file
            ], capture_output=True, text=True, timeout=8)

            if proc.returncode == 0:
                # stdout contains SVG
                return proc.stdout
            else:
                stderr = proc.stderr.strip()
                return f"Sandbox Error: runner failed (code {proc.returncode}): {stderr}"

        except subprocess.TimeoutExpired:
            return "Sandbox Error: execution timed out"
        except Exception as e:
            logger.exception("Failed to run sandbox runner")
            return f"Sandbox Error: {e}"
