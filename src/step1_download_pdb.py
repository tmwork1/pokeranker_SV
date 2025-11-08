import requests

import config
from globals import g
import utils as ut


def download_pdb_ranking():
    print("Downloading battle database ranking...")

    season, rule = g['season'], g['rule']

    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://sv.pokedb.tokyo/'
    }

    url = config.get_pdb_teamdata_url(season, rule)
    dst = config.PDB_DIR / ut.file_from_url(url)

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        with open(dst, "wb") as f:
            f.write(response.content)
            print(f"Done. {dst}")
    else:
        print(f"Failed. {response.status_code}")

    print("="*50)
