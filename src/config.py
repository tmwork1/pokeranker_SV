from pathlib import Path
import os

MULTIPROCESS = True

SRC_PATH = Path(__file__).resolve().parent
TMP_PATH = SRC_PATH / "../tmp"
DATA_PATH = SRC_PATH / "../data"
TEAM_TEMPLATE_PATH = DATA_PATH / "team.png"
PDB_PATH = DATA_PATH / "pdb"
TEAM_ARTICLE_PATH = DATA_PATH / "team_article"
TEAM_IMAGE_PATH = DATA_PATH / "team_image"
TEAM_TEXT_PATH = DATA_PATH / "team_text"
TEAM_SUMMARY_PATH = DATA_PATH / "team_summary"

if os.name == 'nt':
    OUTPUT_PATH = SRC_PATH / "../output"
else:
    OUTPUT_PATH = SRC_PATH / "../download/kata"
REGULATION_PATH = OUTPUT_PATH / "regulation.csv"
