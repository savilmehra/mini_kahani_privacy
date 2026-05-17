from pathlib import Path
import runpy


APP_PATH = Path(
    r"C:\Users\savka\OneDrive\Documents\Blackmagic Design\Desktop"
    r"\lightricks\reel_creator_app.py"
)


if not APP_PATH.exists():
    raise FileNotFoundError(f"Reel creator app was not found at: {APP_PATH}")

runpy.run_path(str(APP_PATH), run_name="__main__")
