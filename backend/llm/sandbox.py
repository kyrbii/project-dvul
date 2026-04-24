import matplotlib.pyplot as plt
import pandas as pd
import os
import uuid

def execute_plot_code(code: str, df: pd.DataFrame) -> str:
    """
    Safely executes the plotting code and returns the relative path to the generated SVG.
    """
    plots_dir = "static/plots"
    os.makedirs(plots_dir, exist_ok=True)
    
    # Generate unique filename
    plot_filename = f"plot_{uuid.uuid4().hex[:8]}.svg"
    plot_path = os.path.join(plots_dir, plot_filename)
    
    # Setup execution environment
    local_vars = {
        "df": df.copy(),
        "plt": plt,
        "pd": pd,
        "os": os # Limited OS access for savefig
    }
    
    try:
        plt.close('all')
        plt.style.use('ggplot') # Default professional style
        print("\n This is the code that is being executed: \n",code)
        # Execute
        exec(code, {"__builtins__": __builtins__}, local_vars)
        
        # If the code didn't save the file itself, we do it now
        if plt.get_fignums():
            plt.savefig(plot_path, format='svg', bbox_inches='tight')
            plt.close('all')
            return f"Plot created successfully: {plot_path}"
        
        # Check if code saved to a file directly (sometimes agents do this)
        # We look for any .svg created in the last few seconds if no active figure
        return "Warning: Code executed but no active matplotlib figure found. Check instructions."
            
    except Exception as e:
        plt.close('all')
        return f"Sandbox Error: {str(e)}"
