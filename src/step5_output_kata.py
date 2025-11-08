import json
import collections
import pandas as pd
import csv

import config


def create_kata_data(rule: str):
    # レギュレーション一覧の取得
    filepath = config.REGULATION_FILE
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        regulations = {row[0]: row[1] for row in reader}  # {"season": "regulation"}

    for reg in regulations.values():
        target_seasons = [int(i) for i in regulations.keys() if regulations[i] == reg]
        kata_data = _create_data(target_seasons, rule)

        if not kata_data:
            continue

        dst = config.OUTPUT_DIR / "kata" / f"kata_reg{reg}.json"
        with open(dst, 'w', encoding='utf-8') as fout:
            json.dump(kata_data, fout, ensure_ascii=False, indent=4)

        print(f"reg{reg} {rule} >>> {dst}\n")


def to_kata(name: str,
            ability: str,
            item: str,
            moves: list,
            use_ability: bool = False,
            ) -> str:
    if use_ability:
        return f"{name}_{ability}_{item}"
    else:
        return f"{name}_{item}"


def _create_data(seasons: list[int], rule: str) -> dict:
    dfs = []
    for season in seasons:
        # パーティ情報の読み込み
        path = config.OUTPUT_DIR / "team" / f"s{season}_{rule}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path)

        # 技が欠損しているデータを削除
        if (s := "move-1") in df.columns:
            df = df.dropna(subset=[s])

        print(f"s{season}\tポケモン数{len(df)}\t構築数{len(df)/6:.0f}")
        dfs.append(df)

    if not dfs:
        return {}

    df = pd.concat(dfs).reset_index()
    print(f"Total\t\t構築 {len(df)/6:.0f}\tポケモン {len(df)}")

    df['kata'] = None

    # 型に分類
    for idx, row in df.iterrows():
        name = row['alias']
        ability = row['ability']
        item = row['item']
        moves = [row[f'move-{i+1}'] for i in range(4)]

        # 特性の採用率をもとに、特性で型を分類するか判断する
        df1 = df[df['alias'] == name]
        rates = df1['ability'].value_counts()
        rates = rates/rates.sum()
        is_ability_major = rates.shape[0] > 1 and rates.iloc[1] > 0.1  # 採用率 > 10%

        df.at[idx, 'kata'] = to_kata(name, ability, item, moves,  use_ability=is_ability_major)  # type: ignore

    # 列の並び替え
    columns = df.columns.to_list()
    idx = columns.index('id')
    columns = columns[:idx] + columns[-1:] + columns[idx:-1]
    df = df.reindex(columns, axis=1)

    # 型ごとに採用されている特性やアイテムをリストに詰める
    kata_data, alias2kata = {}, {}
    teams = {}

    for idx, row in df.iterrows():
        alias = row['alias']
        kata = row['kata']

        alias2kata.setdefault(alias, []).append(kata)
        kata_data.setdefault(kata, {
            'ability': [],
            'item': [],
            'terastal': [],
            'move': [],
            'team': [],
            'team_kata': [],
        })

        kata_data[kata]['ability'].append(row['ability'])
        kata_data[kata]['item'].append(row['item'])
        kata_data[kata]['terastal'].append(row['terastal'])
        kata_data[kata]['move'] += [row[f"move-{i+1}"] for i in range(4) if row[f"move-{i+1}"]]

        key = f"{row['season']}_{row['rank']}"
        teams.setdefault(key, []).append(row['kata'])

    for key in teams:
        for kata in teams[key]:
            kata_data[kata]['team_kata'] += [c for c in teams[key] if c != kata]

    # 収集したリストを集計
    for alias in alias2kata:
        alias2kata[alias] = collections.Counter(alias2kata[alias])

    for kata in kata_data:
        kata_data[kata]['team'] = [s[:s.index('_')] for s in kata_data[kata]['team_kata']]
        for key in kata_data[kata]:
            kata_data[kata][key] = collections.Counter(kata_data[kata][key])

    # アイテムの逆引き辞書を作成
    item2kata = {}
    for alias in alias2kata:
        item2kata[alias] = {}
        for kata in alias2kata[alias]:
            for v in kata_data[kata]['item']:
                if v not in item2kata[alias]:
                    item2kata[alias][v] = []
                item2kata[alias][v] += [kata]*kata_data[kata]['item'][v]

        # 集計
        for v in item2kata[alias]:
            item2kata[alias][v] = collections.Counter(item2kata[alias][v])

    # 技の逆引き辞書を作成
    move2kata = {}
    for alias in alias2kata:
        move2kata[alias] = {}
        for kata in alias2kata[alias]:
            for v in kata_data[kata]['move']:
                if v not in move2kata[alias]:
                    move2kata[alias][v] = []
                move2kata[alias][v] += [kata]*kata_data[kata]['move'][v]

        # 集計
        for v in move2kata[alias]:
            move2kata[alias][v] = collections.Counter(move2kata[alias][v])

    # 正規化
    for alias in alias2kata:
        alias2kata[alias] = normalize(alias2kata[alias])

    for kata in kata_data:
        n = sum(kata_data[kata]['ability'].values())
        for key in kata_data[kata]:
            kata_data[kata][key] = normalize(kata_data[kata][key], denom=n)

    for d in [item2kata, move2kata]:
        for alias in d:
            for v in d[alias]:
                d[alias][v] = normalize(d[alias][v])

    # 出力
    return {
        'valid_alias': config.VALID_ALIASES,
        'alias2kata': alias2kata,
        'kata': kata_data,
        'item2kata': item2kata,
        'move2kata': move2kata
    }


def normalize(counter, denom=0, ndigits=3):
    if not denom:
        denom = sum(counter.values())
    for key in counter:
        counter[key] = round(counter[key]/denom, ndigits)
    return collections.OrderedDict(sorted(counter.items(), key=lambda x: 1/x[1]))
