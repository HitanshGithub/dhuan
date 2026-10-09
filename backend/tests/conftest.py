import os
import shutil
from pathlib import Path

TMP = Path(__file__).parent / ".tmp"
shutil.rmtree(TMP, ignore_errors=True)
TMP.mkdir()
os.environ["DHUAN_OUT_DIR"] = str(TMP)
os.environ["DHUAN_STORAGE"] = "local"
os.environ["DHUAN_LLM"] = "offline"
