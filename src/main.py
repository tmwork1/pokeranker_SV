import utils as ut
from globals import g
import os
import subprocess

import config

from step1_download_pdb import download_pdb_ranking
from step2_download_images import download_team_images
from step3_read_images import read_team_images
from step4_output_ranker import create_ranker_data
from step5_output_kata import create_kata_data


def run(rule):
    g['rule'] = rule

    season_start = ut.current_season() - 1
    season_stop = 1

    # 過去シーズンのループ
    for season in range(season_start, season_stop-1, -1):
        # グローバル変数の設定
        g['season'] = season

        config.create_temporary_dirs()

        # シーズン・ルールごとのディレクトリを作成
        for path in [config.TEAM_ARTICLE_DIR, config.TEAM_IMAGE_DIR, config.TEAM_TEXT_DIR]:
            os.makedirs(path / config.get_indiv_dir(season, rule), exist_ok=True)

        # 1. バトルデータベースのランキングを取得
        download_pdb_ranking()

        # 2. 構築記事のパーティ画像を取得
        download_team_images()

        # 3. パーティ画像を解析
        read_team_images()

        # 4. バトルデータベースの情報と照合して最終出力する
        create_ranker_data()

        config.delete_temporary_dirs()

    # 型はレギュレーションごとに分類するため、シーズンのループ外で生成する
    create_kata_data(g['rule'])


if __name__ == '__main__':
    run(rule="single")
