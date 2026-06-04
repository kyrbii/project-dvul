import ast
import io
import sys
import os
import traceback
import resource

import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import numpy as np

# Runner invoked as: python sandbox_runner.py <code-file> <csv-file>

DISALLOWED_NAMES = {
    'open', 'exec', 'eval', 'compile', '__import__', 'os', 'sys', 'subprocess',
    'shutil', 'socket', 'requests', 'ctypes', 'mmap', 'fork', 'spawn', 'Popen',
}

DISALLOWED_NODES = (ast.Import, ast.ImportFrom)


def ast_is_safe(code: str) -> (bool, str):
    try:
        tree = ast.parse(code)
    except Exception as e:
        return False, f"AST parse error: {e}"

    for node in ast.walk(tree):
        if isinstance(node, DISALLOWED_NODES):
            return False, f"Use of import statements is disallowed: {ast.dump(node)}"

        # Names used in code
        if isinstance(node, ast.Name) and node.id in DISALLOWED_NAMES:
            return False, f"Use of name '{node.id}' is disallowed"

        # Attribute access to dunder or system attributes
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if attr.startswith('__'):
                return False, f"Access to dunder attribute '{attr}' is disallowed"

    return True, ''


def harden_limits():
    # Limit CPU time (seconds)
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    # Limit address space (bytes) - ~300MB
    resource.setrlimit(resource.RLIMIT_AS, (300 * 1024 * 1024, 300 * 1024 * 1024))
    # Limit file size writes (bytes)
    resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
    # No core dumps
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def main():
    if len(sys.argv) < 3:
        print("Usage: sandbox_runner.py <code-file> <csv-file>", file=sys.stderr)
        sys.exit(2)

    code_path = sys.argv[1]
    csv_path = sys.argv[2]

    try:
        with open(code_path, 'r', encoding='utf-8') as f:
            code = f.read()
    except Exception as e:
        print(f"Runner Error: cannot read code file: {e}", file=sys.stderr)
        sys.exit(3)

    safe, msg = ast_is_safe(code)
    if not safe:
        print(f"Runner Error: unsafe code detected: {msg}", file=sys.stderr)
        sys.exit(4)

    # Apply resource limits in this process
    try:
        harden_limits()
    except Exception:
        # If resource is not available, continue but warn
        pass

    try:
        # Load dataframe from CSV (read-only)
        df = pd.read_csv(csv_path)

        # Prepare a minimal set of safe builtins
        safe_builtins = {
            'None': None,
            'True': True,
            'False': False,
            'abs': abs,
            'min': min,
            'max': max,
            'sum': sum,
            'len': len,
            'range': range,
            'enumerate': enumerate,
            'float': float,
            'int': int,
            'str': str,
            'bool': bool,
            'list': list,
            'dict': dict,
            'set': set,
            'tuple': tuple,
            'sorted': sorted,
            'zip': zip,
        }

        # Local variables exposed to the executed code
        local_vars = {
            'df': df,
            'pd': pd,
            'plt': plt,
            'sns': sns,
            'np': np,
        }

        plt.close('all')
        plt.style.use('ggplot')

        # Execute in very restricted globals
        exec(code, {"__builtins__": safe_builtins}, local_vars)

        if plt.get_fignums():
            buf = io.StringIO()
            plt.savefig(buf, format='svg', bbox_inches='tight')
            plt.close('all')
            svg = buf.getvalue()
            # Print SVG to stdout for capture by the parent
            print(svg)
            sys.exit(0)

        print("Runner Error: no figure produced", file=sys.stderr)
        sys.exit(5)

    except SystemExit:
        raise
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.exit(6)


if __name__ == '__main__':
    main()
