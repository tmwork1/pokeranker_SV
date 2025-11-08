# -*- coding: utf-8 -*-

import json
import collections
import pandas as pd
import csv

from config import *


# 型として登録されていないフォルム -> 登録されているフォルム、の変換辞書
valid_alias = {
    'メテノ(コア)': 'メテノ(りゅうせい)',
    'コオリッポ(ナイス)': 'コオリッポ(アイス)',
    'イルカマン(マイティ)': 'イルカマン(ナイーブ)',
    'テラパゴス(テラスタル)': 'テラパゴス(ノーマル)',
    'テラパゴス(ステラ)': 'テラパゴス(ノーマル)',
}


def make_kata(name: str,
              ability: str,
              item: str,
              moves: list,
              include_ability: bool = False) -> str:
    if include_ability:
        return f"{name}_{ability}_{item}"
    else:
        return f"{name}_{item}"


def load_regulation():
    filepath = OUTPUT_PATH / 'regulation.csv'
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        return {row[0]: row[1] for row in reader}


def normalize(counter, denom=0, ndigits=3):
    if not denom:
        denom = sum(counter.values())
    for key in counter:
        counter[key] = round(counter[key]/denom, ndigits)
    return collections.OrderedDict(sorted(counter.items(), key=lambda x: 1/x[1]))


def create_kata_data(rule: str):
    season2reg = load_regulation()

    for reg in season2reg.values():
        seasons = [int(i) for i in season2reg.keys() if season2reg[i] == reg]
        kata_data = _create_data(seasons, rule)

        dst = OUTPUT_PATH / f"kata_reg{reg}.json"
        with open(dst, 'w', encoding='utf-8') as fout:
            json.dump(kata_data, fout, ensure_ascii=False)

        print(f"reg{reg} {rule} >>> {dst}\n")


def _create_data(seasons: list, rule: str) -> dict:
    dfs = []
    for season in seasons:
        path = OUTPUT_PATH / f"s{season}_{rule}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path)
        df = df.dropna(subset=['move_0'])  # 技が欠損しているデータを削除
        print(f"s{season}\tポケモン数{len(df)}\t構築数{len(df)/6:.0f}")
        dfs.append(df)

    df = pd.concat(dfs).reset_index()
    print(f"Total\t\t構築 {len(df)/6:.0f}\tポケモン {len(df)}")

    # 型に分類
    df['kata'] = None

    for idx, row in df.iterrows():
        name = row['alias']
        ability = row['ability']
        item = row['item']
        moves = [row[f'move_{i}'] for i in range(4)]

        # 特性の採用率を計算
        df1 = df[df['alias'] == name]
        rates = df1['ability'].value_counts()
        rates = rates/rates.sum()

        df.at[idx, 'kata'] = make_kata(
            name, ability, item, moves,
            include_ability=(rates.shape[0] > 1 and rates.iloc[1] > 0.1)
        )

    # 列の並び替え
    columns = df.columns.to_list()
    idx = columns.index('id')
    columns = columns[:idx] + columns[-1:] + columns[idx:-1]
    df = df.reindex(columns, axis=1)

    # 型ごとに採用されている特性やアイテムをリストに詰める
    dict, alias2kata = {}, {}
    teams = {}

    for idx, row in df.iterrows():
        alias = row['alias']
        kata = row['kata']

        if alias not in alias2kata:
            alias2kata[alias] = []

        if kata not in dict:
            dict[kata] = {
                'ability': [],
                'item': [],
                'terastal': [],
                'move': [],
                'team': [],
                'team_kata': [],
            }

        alias2kata[alias].append(kata)

        dict[kata]['ability'].append(row['ability'])
        dict[kata]['item'].append(row['item'])
        dict[kata]['terastal'].append(row['terastal'])
        dict[kata]['move'] += [row[f"move_{i}"] for i in range(4) if row[f"move_{i}"]]

        key = f"{row['season']}_{row['rank']}"
        if key not in teams:
            teams[key] = []
        teams[key].append(row['kata'])

    for key in teams:
        for kata in teams[key]:
            dict[kata]['team_kata'] += [c for c in teams[key] if c != kata]

    # 収集したリストを集計
    for alias in alias2kata:
        alias2kata[alias] = collections.Counter(alias2kata[alias])

    for kata in dict:
        dict[kata]['team'] = [s[:s.index('_')] for s in dict[kata]['team_kata']]
        for key in dict[kata]:
            dict[kata][key] = collections.Counter(dict[kata][key])

    # アイテムの逆引き辞書を作成
    item2kata = {}
    for alias in alias2kata:
        item2kata[alias] = {}
        for kata in alias2kata[alias]:
            for v in dict[kata]['item']:
                if v not in item2kata[alias]:
                    item2kata[alias][v] = []
                item2kata[alias][v] += [kata]*dict[kata]['item'][v]

        # 集計
        for v in item2kata[alias]:
            item2kata[alias][v] = collections.Counter(item2kata[alias][v])

    # 技の逆引き辞書を作成
    move2kata = {}
    for alias in alias2kata:
        move2kata[alias] = {}
        for kata in alias2kata[alias]:
            for v in dict[kata]['move']:
                if v not in move2kata[alias]:
                    move2kata[alias][v] = []
                move2kata[alias][v] += [kata]*dict[kata]['move'][v]

        # 集計
        for v in move2kata[alias]:
            move2kata[alias][v] = collections.Counter(move2kata[alias][v])

    # 正規化
    for alias in alias2kata:
        alias2kata[alias] = normalize(alias2kata[alias])

    for kata in dict:
        n = sum(dict[kata]['ability'].values())
        for key in dict[kata]:
            dict[kata][key] = normalize(dict[kata][key], denom=n)

    for d in [item2kata, move2kata]:
        for alias in d:
            for v in d[alias]:
                d[alias][v] = normalize(d[alias][v])

    # 出力
    return {
        'valid_alias': valid_alias,
        'alias2kata': alias2kata,
        'kata': dict,
        'item2kata': item2kata,
        'move2kata': move2kata
    }
