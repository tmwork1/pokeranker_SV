import json
import numpy as np
import pandas as pd
import csv

import config
from globals import g
import utils as ut


def create_ranker_data():
    """パーティ画像の情報をバトルデータベースと照合して最終結果を出力する"""
    season, rule = g['season'], g['rule']

    # 表記を調整するために、図鑑とエイリアス(ポケモンの呼称)の辞書を用意する
    zukan, aliases = {}, {}
    with open(config.DATA_DIR / 'zukan.csv',
              encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)

        # pbd表記に統一
        header[0:2], header[3], header[9:11] = ['id', 'id2'], 'pokemon', ['type1', 'type2']

        for row in reader:
            name, form, alias = row[3:6]
            zukan[alias] = dict(zip(header, row))
            aliases.setdefault(name, {})[form] = alias

    # バトルデータベースの情報を読み込む
    file = config.PDB_DIR / ut.file_from_url(config.get_pdb_teamdata_url(season, rule))
    with open(file, encoding='utf-8') as f:
        pdb = json.load(f)
    players = pdb['teams']

    # バトルデータベースの辞書の情報を加筆修正する
    for player in players:
        for poke in player['team']:
            # 修正
            # ザシアン, ザマゼンタ : "xxのおう" は別ポケモン扱いのため図鑑を差し替える
            if (name := poke['pokemon']) in ['ザシアン', 'ザマゼンタ'] and \
                    'くちた' in (item := poke['item']):
                alias = aliases[name][f"{item[-2:]}のおう"]
                for k in ['id', 'pokemon', 'form', 'type1', 'type2']:
                    poke[k] = zukan[alias][k]

            # ケンタロス >> "種"を漢字に変更
            if len(poke['form']) >= 2 and poke['form'][-2:] == 'しゅ':
                poke['form'] = poke['form'][:-2] + '種'

            # ガチグマ >> "のすがた"を削除
            if poke['form'] == 'アカツキのすがた':
                poke['form'] = 'アカツキ'

            # エイリアスを登録
            try:
                poke['alias'] = aliases[poke['pokemon']][poke['form']]
            except Exception:
                poke['alias'] = poke['pokemon']

    # パーティ画像解析結果の読み込み
    file = config.TEAM_SUMMARY_DIR / f"teams_s{season}_{rule}.json"
    with open(file, encoding='utf-8') as f:
        image_data = json.load(f)

    # 特性一覧
    abilities = ut.load_abilities()

    pokemons = []

    # バトルデータベースのすべてのパーティに対して、画像解析結果を追記する
    for player in players:
        rank = player['rank']
        rate = player['rating_value']

        # 画像解析結果
        team_from_img = image_data.get(str(rank), {})
        names_from_img = [d['name'] for d in team_from_img]

        for poke in player['team']:
            # プレイヤーの順位とレートを付与
            poke['rank'] = int(rank)
            poke['rate'] = rate

            # 画像情報がなければ、バトルデータベースの情報だけ記録して終了
            if not team_from_img:
                pokemons.append(poke)
                continue

            name = ut.find_most_similar(names_from_img, poke['pokemon'])
            idx = names_from_img.index(name)
            ability = team_from_img[idx]['ability']

            # 特性が図鑑情報と矛盾する場合は、画像解析の結果は使わない
            if ability not in abilities[poke['pokemon']]:
                print(f"\t不適切な特性\t{rank}位 {idx+1} {poke['pokemon']}\t{ability}\t{team_from_img[idx]['move']}")
                continue

            # 画像解析の結果を追加
            poke['ability'] = ability
            for i, move in enumerate(team_from_img[idx]['move']):
                poke[f'move-{i+1}'] = move

            pokemons.append(poke)

    df = pd.DataFrame(pokemons)
    df['season'] = season

    # 列の並び替え
    columns = df.columns.values
    first_keys = ['season', 'rank', 'rate', 'alias']
    for key in first_keys:
        columns = columns[columns != key]
    columns = np.insert(columns, 0, first_keys)
    df = df.reindex(columns, axis=1)

    dst = config.OUTPUT_DIR / "team" / f"s{season}_{rule}.csv"
    with open(dst, 'w', encoding='utf-8') as fout:
        df.to_csv(dst)

    print(f"保存 {dst}\n")
