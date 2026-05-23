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
    # 1. Hardened execution environment (No 'os', No 'sys', No 'open')
    import seaborn as sns
    import numpy as np
    local_vars = {
        "df": df.copy(),
        "plt": plt,
        "pd": pd,
        "sns": sns,
        "np": np
    }
    
    # 2. Prevent malicious builtins
    safe_builtins = __builtins__.copy()
    # Remove dangerous functions if they exist in this environment's builtins
    for dangerous in ['open', 'eval', 'exec', 'getattr', 'setattr', 'help']:
        safe_builtins.pop(dangerous, None)

    # Clean code (remove markdown blocks if present)
    code = code.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        if len(lines) > 2:
            code = "\n".join(lines[1:-1])
        else:
            code = code.replace("```python", "").replace("```", "").strip()

    try:
        plt.close('all')
        plt.style.use('ggplot')
        
        # 3. Execute in restricted scope
        # We use an empty dict for globals to isolate the execution
        exec(code, {"__builtins__": safe_builtins}, local_vars)
        
        # 4. Capture result as SVG string
        if plt.get_fignums():
            img_buffer = io.StringIO()
            plt.savefig(img_buffer, format='svg', bbox_inches='tight')
            plt.close('all')
            return img_buffer.getvalue()
        
        return "Error: Code executed but no matplotlib figure was produced."
            
    except Exception as e:
        logger.exception("Sandbox plot execution error")
        plt.close('all')
        return f"Sandbox Error: {str(e)}"
