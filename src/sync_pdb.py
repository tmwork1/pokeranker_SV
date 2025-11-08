# -*- coding: utf-8 -*-

import json
import numpy as np
import pandas as pd
import csv

from config import *
from globals import g
import utils as ut


def sync_team_with_pdb():
    """パーティ画像の情報をバトルデータベースと照合し、シーズンの最終出力"""
    season, rule = g['season'], g['rule']

    # 特性一覧の読み込み
    abilities = ut.load_abilities()

    # バトルデータベース情報の読み込み
    with open(PDB_PATH / f"s{season}_{rule}_ranked_teams.json", encoding='utf-8') as fin:
        pdb = json.load(fin)
    players = pdb['teams']

    # 図鑑(辞書)を生成
    zukan, aliases = {}, {}
    with open(DATA_PATH / 'zukan.csv', encoding='utf-8') as fin:
        reader = csv.reader(fin)
        header = next(reader)
        header[0:2], header[3], header[9:11] = ['id', 'id2'], 'pokemon', ['type1', 'type2']  # pbd表記に統一
        for row in reader:
            name, form, alias = row[3:6]
            zukan[alias] = dict(zip(header, row))
            if not name in aliases:
                aliases[name] = {}
            aliases[name][form] = alias

    for player in players:
        for poke in player['team']:
            # 修正
            # ザシアン, ザマゼンタ
            if poke['pokemon'] in ['ザシアン', 'ザマゼンタ'] and 'くちた' in poke['item']:
                alias = aliases[poke['pokemon']][f"{poke['item'][-2:]}のおう"]
                for k in ['id', 'pokemon', 'form', 'type1', 'type2']:
                    poke[k] = zukan[alias][k]

            # ケンタロス
            if len(poke['form']) >= 2 and poke['form'][-2:] == 'しゅ':
                poke['form'] = poke['form'][:-2] + '種'  # 公式(内部)名称

            # ガチグマ
            if poke['form'] == 'アカツキのすがた':
                poke['form'] = 'アカツキ'  # 公式名称

            # Aliasを適用
            try:
                poke['alias'] = aliases[poke['pokemon']][poke['form']]
            except Exception as e:
                poke['alias'] = poke['pokemon']

    # パーティ画像解析結果の読み込み
    with open(TEAM_SUMMARY_PATH / f"team_s{season}_{rule}.json", encoding='utf-8') as fin:
        team_image_data = json.load(fin)

    pokemon_list = []

    # バトルデータベースにある全パーティのループ
    for player in players:
        rank = player['rank']
        rate = player['rating_value']

        # パーティのポケモンのループ
        for poke in player['team']:
            # ポケモンに順位とレートを付与
            poke['rank'] = int(rank)
            poke['rate'] = rate

            # パーティ画像から得た情報(特性・技)を付与
            if rank in team_image_data:
                team = team_image_data[rank]
                names = [d['name'] for d in team]
                name = ut.find_most_similar(names, poke['pokemon'])
                idx = names.index(name)
                ability = team[idx]['ability']

                if ability not in abilities[poke['pokemon']]:
                    # 特性に矛盾があれば中断
                    print(f"\t不適切な特性\t{rank}位 {idx+1} {poke['pokemon']}\t{ability}\t{team[idx]['move']}")
                    continue

                # パーティ画像解析結果を付与
                poke['ability'] = ability
                for i, move in enumerate(team[idx]['move']):
                    poke[f'move_{i}'] = move

            pokemon_list.append(poke)

    df = pd.DataFrame(pokemon_list)
    df['season'] = season

    # 列の並び替え
    columns = df.columns.values
    first_keys = ['season', 'rank', 'rate', 'alias']
    for key in first_keys:
        columns = columns[columns != key]
    columns = np.insert(columns, 0, first_keys)
    df = df.reindex(columns, axis=1)

    dst = OUTPUT_PATH / f"s{season}_{rule}.csv"
    with open(dst, 'w', encoding='utf-8') as fout:
        df.to_csv(dst)

    print(f"保存 {dst}\n")
