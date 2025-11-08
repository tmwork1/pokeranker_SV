from pathlib import Path
import os
import shutil


MULTIPROCESS = True

OCR_LANGS = ['jpn', 'eng', 'fra', 'eng', 'deu', 'eng', 'kor', 'chi', 'chi']

VALID_ALIASES = {
    'メテノ(コア)': 'メテノ(りゅうせい)',
    'コオリッポ(ナイス)': 'コオリッポ(アイス)',
    'イルカマン(マイティ)': 'イルカマン(ナイーブ)',
    'テラパゴス(テラスタル)': 'テラパゴス(ノーマル)',
    'テラパゴス(ステラ)': 'テラパゴス(ノーマル)',
}


SRC_DIR = Path(__file__).resolve().parent

DATA_DIR = SRC_DIR / "../data"
TEAM_TEMPLATE_IMAGE = DATA_DIR / "team.png"
REGULATION_FILE = DATA_DIR / "regulation.csv"

TMP_DIR = SRC_DIR / "../tmp"
MISC_DIR = TMP_DIR / "misc"
PDB_DIR = TMP_DIR / "pdb"
TEAM_ARTICLE_DIR = TMP_DIR / "team_article"
TEAM_IMAGE_DIR = TMP_DIR / "team_image"
TEAM_TEXT_DIR = TMP_DIR / "team_text"
TEAM_SUMMARY_DIR = TMP_DIR / "team_summary"

OUTPUT_DIR = SRC_DIR / "../output"


def get_indiv_dir(season, rule) -> str:
    return f"s{season}_{rule}"


def get_pdb_teamdata_url(season, rule):
    return f"https://sv.pokedb.tokyo/opendata/s{season}_{rule}_ranked_teams.json"


def get_pdb_portal_url(season, rule, page):
    rule_code = 0 if rule == "single" else 1
    return f"https://sv.pokedb.tokyo/trainer/list?season={season}&rule={rule_code}&party=1&page={page}"


def create_temporary_dirs():
    for path in [MISC_DIR, PDB_DIR, TEAM_ARTICLE_DIR, TEAM_IMAGE_DIR, TEAM_TEXT_DIR, TEAM_SUMMARY_DIR, OUTPUT_DIR]:
        os.makedirs(path, exist_ok=True)


def delete_temporary_dirs():
    for path in [MISC_DIR]:
        if os.path.exists(path):
            shutil.rmtree(path)


TESSERACT_PATH = SRC_DIR / ".." / "Tesseract-OCR"
TESSDATA_PATH = TESSERACT_PATH / "tessdata"
os.environ["PATH"] += os.pathsep + str(TESSERACT_PATH)
os.environ["TESSDATA_PREFIX"] = str(TESSDATA_PATH)
