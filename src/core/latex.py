
#!/usr/bin/env python3
"""
LaTeX rendering utilities for SAT Study application
"""
import io
import matplotlib.pyplot as plt

# Global cache for LaTeX rendered images
latex_cache = {}

def latex_to_image(latex_str, dpi=300):
    """Convert LaTeX string to inline PNG image data using mathtext rendering."""
    # Check cache first
    if latex_str in latex_cache:
        cached_data = latex_cache[latex_str]
        return io.BytesIO(cached_data.getvalue())

    plt.rcParams.update({
        'backend': 'Agg',
        'text.usetex': False,  # Use mathtext for performance and compatibility
        'font.family': 'sans-serif',
        'font.serif': ['Computer Modern Roman'],
        'font.size': 10,
        'figure.dpi': dpi
    })
    
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.patch.set_alpha(0)
    ax.axis('off')
    
    # Wrap in math mode if needed
    if not latex_str.strip().startswith('\\'):
        latex_str = r'$' + latex_str + r'$'
    
    text = ax.text(0.5, 0.5, latex_str,
                   ha='center', va='center',
                   transform=ax.transAxes)
    
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bbox = text.get_window_extent(renderer)
    bbox_inches = bbox.transformed(fig.dpi_scale_trans.inverted())
    
    img_data = io.BytesIO()
    try:
        fig.savefig(img_data, 
                    format='png',
                    bbox_inches=bbox_inches,
                    pad_inches=0.02,
                    transparent=True,
                    dpi=dpi)
        img_data.seek(0)
        # Store in cache (create a new BytesIO to preserve the data)
        latex_cache[latex_str] = io.BytesIO(img_data.getvalue())
        return img_data
    finally:
        plt.close(fig)
    
    return img_data
