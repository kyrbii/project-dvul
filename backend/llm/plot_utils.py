import matplotlib.pyplot as plt
import io

def generate_dummy_svg(code: str) -> str:
    """
    Generates a dummy SVG string using matplotlib.
    This is used for testing the handoff between backend and frontend.
    """
    # Create a simple plot
    fig, ax = plt.subplots(figsize=(5, 4))
    
    # Dummy data
    x = [1, 2, 3, 4, 5]
    y = [2, 3, 5, 7, 11]
    
    ax.plot(x, y, marker='o', linestyle='-', color='b')
    ax.set_title("Dummy Matplotlib Plot")
    ax.set_xlabel("X-axis")
    ax.set_ylabel("Y-axis")
    ax.grid(True)
    
    # Save to a buffer
    buf = io.StringIO()
    fig.savefig(buf, format='svg')
    plt.close(fig)
    
    return buf.getvalue()
