import ast
import io
import logging
import multiprocessing as mp
import os
import queue
import tempfile
from collections.abc import Mapping
from types import ModuleType
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)



PLOT_TIMEOUT_SECONDS = 8
MAX_CODE_LENGTH = 20_000
MAX_DATAFRAME_ROWS = 100_000
MAX_DATAFRAME_COLUMNS = 200
MAX_SVG_BYTES = 5_000_000

_ALLOWED_IMPORTS = {
    "math",
    "statistics",
    "matplotlib",
    "matplotlib.pyplot",
    "numpy",
    "pandas",
    "seaborn",
}

_FORBIDDEN_NAMES = {
    "__builtins__",
    "__import__",
    "breakpoint",
    "compile",
    "delattr",
    "dir",
    "eval",
    "exec",
    "getattr",
    "globals",
    "help",
    "input",
    "locals",
    "open",
    "setattr",
    "vars",
}

_FORBIDDEN_MODULES = {
    "builtins",
    "ctypes",
    "importlib",
    "inspect",
    "multiprocessing",
    "os",
    "pathlib",
    "pickle",
    "shutil",
    "signal",
    "socket",
    "subprocess",
    "sys",
    "threading",
}

_FORBIDDEN_ATTRIBUTES = {
    "from_pickle",
    "load",
    "load_dataset",
    "loadtxt",
    "read_clipboard",
    "read_csv",
    "read_excel",
    "read_feather",
    "read_fwf",
    "read_gbq",
    "read_hdf",
    "read_html",
    "read_json",
    "read_orc",
    "read_parquet",
    "read_pickle",
    "read_sas",
    "read_spss",
    "read_sql",
    "read_sql_query",
    "read_sql_table",
    "read_stata",
    "read_table",
    "save",
    "savefig",
    "savetxt",
    "to_clipboard",
    "to_csv",
    "to_excel",
    "to_feather",
    "to_gbq",
    "to_hdf",
    "to_html",
    "to_json",
    "to_latex",
    "to_markdown",
    "to_orc",
    "to_parquet",
    "to_pickle",
    "to_sql",
    "to_stata",
}


class SandboxValidationError(ValueError):
    """Raised when generated plotting code uses disallowed Python features."""


def _copy_builtins() -> dict[str, Any]:
    builtins_obj = __builtins__
    if isinstance(builtins_obj, Mapping):
        source = builtins_obj
    else:
        source = vars(builtins_obj)

    safe_names = {
        "ArithmeticError",
        "AssertionError",
        "Exception",
        "False",
        "FloatingPointError",
        "IndexError",
        "KeyError",
        "NameError",
        "None",
        "RuntimeError",
        "StopIteration",
        "True",
        "TypeError",
        "ValueError",
        "ZeroDivisionError",
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "enumerate",
        "filter",
        "float",
        "int",
        "isinstance",
        "len",
        "list",
        "map",
        "max",
        "min",
        "pow",
        "print",
        "range",
        "reversed",
        "round",
        "set",
        "slice",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
    }
    safe_builtins = {name: source[name] for name in safe_names if name in source}
    safe_builtins["__import__"] = _safe_import
    return safe_builtins


def _safe_import(
    name: str,
    globals_: dict[str, Any] | None = None,
    locals_: dict[str, Any] | None = None,
    fromlist: tuple[str, ...] = (),
    level: int = 0,
) -> ModuleType:
    root_name = name.split(".", 1)[0]
    if level != 0 or root_name in _FORBIDDEN_MODULES or name not in _ALLOWED_IMPORTS:
        raise ImportError(f"Import of '{name}' is not allowed in the plot sandbox.")

    return __import__(name, globals_, locals_, fromlist, level)


def _clean_code(code: str) -> str:
    code = code.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        if len(lines) > 2:
            return "\n".join(lines[1:-1]).strip()
        return code.replace("```python", "").replace("```", "").strip()
    return code


def _validate_code(code: str) -> None:
    if not code:
        raise SandboxValidationError("No plotting code was provided.")
    if len(code) > MAX_CODE_LENGTH:
        raise SandboxValidationError("Plotting code is too large.")

    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise SandboxValidationError(f"Invalid Python syntax: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif node.module:
                imports = [node.module]

            for module_name in imports:
                root_name = module_name.split(".", 1)[0]
                if (
                    root_name in _FORBIDDEN_MODULES
                    or module_name not in _ALLOWED_IMPORTS
                ):
                    raise SandboxValidationError(
                        f"Import of '{module_name}' is not allowed."
                    )

        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise SandboxValidationError(
                f"Use of '{node.id}' is not allowed in the plot sandbox."
            )

        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise SandboxValidationError(
                "Dunder attribute access is not allowed in the plot sandbox."
            )

        if isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_ATTRIBUTES:
            raise SandboxValidationError(
                f"Use of '{node.attr}' is not allowed in the plot sandbox."
            )


def _apply_process_limits() -> None:
    try:
        import resource

        resource.setrlimit(
            resource.RLIMIT_CPU,
            (PLOT_TIMEOUT_SECONDS, PLOT_TIMEOUT_SECONDS + 1),
        )
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    except Exception:
        logger.debug("Process resource limits are not available on this platform.")


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.shape[0] > MAX_DATAFRAME_ROWS or df.shape[1] > MAX_DATAFRAME_COLUMNS:
        return df.iloc[:MAX_DATAFRAME_ROWS, :MAX_DATAFRAME_COLUMNS].copy()
    return df.copy()


def _plot_worker(code: str, df: pd.DataFrame, result_queue: mp.Queue) -> None:
    try:
        _apply_process_limits()

        with tempfile.TemporaryDirectory(prefix="plot-sandbox-") as tmpdir:
            os.environ["HOME"] = tmpdir
            os.environ["MPLCONFIGDIR"] = tmpdir
            os.environ["TMPDIR"] = tmpdir

            import matplotlib

            matplotlib.use("agg")
            import matplotlib.pyplot as plt
            import numpy as np
            import seaborn as sns

            plt.close("all")
            plt.style.use("ggplot")

            safe_builtins = _copy_builtins()
            sandbox_globals = {
                "__builtins__": safe_builtins,
                "__name__": "__plot_sandbox__",
                "df": df,
                "np": np,
                "pd": pd,
                "plt": plt,
                "sns": sns,
            }

            compiled_code = compile(code, "<plot-sandbox>", "exec")
            exec(compiled_code, sandbox_globals, sandbox_globals)

            if not plt.get_fignums():
                result_queue.put(
                    {
                        "ok": False,
                        "error": "Code executed but no matplotlib figure was produced.",
                    }
                )
                return

            img_buffer = io.StringIO()
            plt.gcf().savefig(img_buffer, format="svg", bbox_inches="tight")
            plt.close("all")
            svg = img_buffer.getvalue()

            if not svg.lstrip().startswith("<?xml") and "<svg" not in svg[:500]:
                result_queue.put(
                    {
                        "ok": False,
                        "error": "Code executed but did not produce valid SVG output.",
                    }
                )
                return
            if len(svg.encode("utf-8")) > MAX_SVG_BYTES:
                result_queue.put(
                    {
                        "ok": False,
                        "error": "Generated SVG is too large to display safely.",
                    }
                )
                return

            result_queue.put({"ok": True, "svg": svg})
    except Exception as exc:
        logger.exception("Sandbox plot execution error")
        result_queue.put({"ok": False, "error": str(exc)})


def execute_plot_code(code: str, df: pd.DataFrame) -> str:
    """
    Execute matplotlib code in an isolated child process and return SVG output.

    The generated code receives only df, plt, pd, sns, and np plus a small set of
    safe builtins. Imports are restricted to plotting/math libraries, filesystem
    access is blocked through the execution environment, and the child process is
    terminated if it exceeds the plotting timeout.
    """
    code = _clean_code(code)

    try:
        _validate_code(code)
    except SandboxValidationError as exc:
        return f"Sandbox Error: {exc}"

    ctx = mp.get_context("fork" if "fork" in mp.get_all_start_methods() else "spawn")
    result_queue = ctx.Queue(maxsize=1)
    process = ctx.Process(
        target=_plot_worker,
        args=(code, _prepare_dataframe(df), result_queue),
        daemon=True,
    )

    process.start()
    process.join(PLOT_TIMEOUT_SECONDS + 2)

    if process.is_alive():
        process.terminate()
        process.join(1)
        return "Sandbox Error: Plot execution timed out."

    try:
        result = result_queue.get(timeout=1)
    except queue.Empty:
        exitcode = process.exitcode
        return (
            "Sandbox Error: Plot process exited without output "
            f"(exit code {exitcode})."
        )
    if result.get("ok"):
        return result["svg"]
    return f"Sandbox Error: {result.get('error', 'Unknown plotting error.')}"
