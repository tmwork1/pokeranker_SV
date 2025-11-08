# -*- coding: utf-8 -*-

import os
import requests
import subprocess

from config import *
from globals import g
import utils as ut

from download_images import download_team_images
from read_images import read_team_images
from sync_pdb import sync_team_with_pdb
from kata import create_kata_data


TESSERACT_PATH = SRC_PATH / '../Tesseract-OCR'
TESSDATA_PATH = TESSERACT_PATH / 'tessdata'
os.environ["PATH"] += os.pathsep + str(TESSERACT_PATH)
os.environ["TESSDATA_PREFIX"] = str(TESSDATA_PATH)


def download_pdb_ranking():
    print("Download team raking from pokemon battle DB")
    season, rule = g['season'], g['rule']
    url = f"https://sv.pokedb.tokyo/opendata/s{season}_{rule}_ranked_teams.json"
    dst = PDB_PATH / f"{url[url.rfind('/')+1:]}"
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://sv.pokedb.tokyo/'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        with open(dst, "wb") as f:
            f.write(response.content)
            print(f"\t出力 {dst}")
    else:
        print(f"\tFailed: {response.status_code}")


if __name__ == '__main__':
    season_start = ut.current_season() - 1
    season_stop = 1
    g['rule'] = 'single'

    # ディレクトリ作成
    for path in [PDB_PATH, TEAM_SUMMARY_PATH, TMP_PATH]:
        os.makedirs(path, exist_ok=True)

    # 過去シーズンのループ
    for season in range(season_start, season_stop-1, -1):
        # グローバル変数の設定
        g['season'] = season

        # 一時ディレクトリを空にする
        ut.clear_tmp_dir()

        # ディレクトリ作成
        for path in [TEAM_ARTICLE_PATH, TEAM_IMAGE_PATH, TEAM_TEXT_PATH]:
            os.makedirs(path / ut.season_rule_dir(g), exist_ok=True)

        # 1. バトルデータベースのランキングを取得
        download_pdb_ranking()

        # 2. 構築記事のパーティ画像を取得
        download_team_images()

        # 3. パーティ画像を解析
        read_team_images()

        # 4. バトルデータベースの情報と照合して最終出力する
        sync_team_with_pdb()

        # break

    # 型データを生成
    create_kata_data(g['rule'])

    # サーバにアップロード
    subprocess.run(["scp", "-r",
                    r"C:\Users\tmtmh\Documents\pokemon\pokeranker\output\*",
                    "pbasv:/home/pbasv/pbasv.cloudfree.jp/script/home/download/kata/"])
