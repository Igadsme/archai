"""Small Space entry point; it exposes configured evidence only."""
try:
    import gradio as gr
except ImportError:  # allows packaging without Space dependencies
    gr = None


def status():
    return "ArchAI Studio: no trained generator checkpoint is configured. Run the research protocol first."


if gr:
    demo = gr.Interface(fn=status, inputs=None, outputs="text", title="ArchAI Studio")
    if __name__ == "__main__":
        demo.launch()
