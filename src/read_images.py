# -*- coding: utf-8 -*-

import json
import multiprocessing
import csv
import cv2
import numpy as np

from config import *
from globals import g
import utils as ut


def read_team_images():
    season, rule = g['season'], g['rule']
    print(f"s{season} {rule}: Read team images")

    # バトルデータベースのパーティ一覧を読み込む
    with open(PDB_PATH / f"s{season}_{rule}_ranked_teams.json", encoding='utf-8') as fin:
        pdb = json.load(fin)

    print(f"\t{len(pdb['teams'])} teams in Pokemon Battle Database")
    print(f"\t{ut.num_files(TEAM_IMAGE_PATH)} team articles are available")

    # バトルデータベースのjsonに登録されているパーティだけ抽出
    ranks = [int(player["rank"]) for player in pdb["teams"]]
    image_paths = []
    for path in (TEAM_IMAGE_PATH / ut.season_rule_dir(g)).iterdir():
        rank = int(path.stem)
        if rank in ranks:
            image_paths.append(path)
        else:
            print(f"\t{rank}th is not registered in Pokemon Battle Database. Skip.")

    if MULTIPROCESS:
        # 並列処理
        with multiprocessing.Pool(multiprocessing.cpu_count()) as pool:
            res = pool.map(_read_team_image, [(path, pdb, g) for path in image_paths])
    else:
        # 逐次処理
        res = [_read_team_image((path, pdb, g)) for path in image_paths]

    # 整形して出力
    results = {str(data[0]): data[1] for data in res if data}
    dst = TEAM_SUMMARY_PATH / f"team_s{season}_{rule}.json"
    with open(dst, 'w', encoding='utf-8') as fout:
        json.dump(results, fout, ensure_ascii=False)

    print(f"\tSaved as {dst}")


def _read_team_image(args):
    image_path, pdb, g = args

    rank = int(image_path.stem)
    dst = TEAM_TEXT_PATH / ut.season_rule_dir(g) / f"{rank}.json"

    # すでにファイルがあればスキップ
    if MULTIPROCESS:
        if ut.file_name_exists(TEAM_TEXT_PATH / ut.season_rule_dir(g), dst.stem):
            print(f"\ts{g['season']} {rank}th: File exists. Skip.")
            with open(dst, encoding='utf-8') as fin:
                dict = json.load(fin)
            result = [dict[key] for key in dict]
            return [rank, result]
    else:
        if rank != 709:
            pass
            # return

    # バトルデータベースからパーティのポケモン和名を取得
    jp_names = []
    for player in pdb['teams']:
        if int(player['rank']) == rank:
            jp_names = [poke['pokemon'] for poke in player['team']]
            break

    # ポケモン和名を全言語に変換したリストを取得
    foreign_names = []
    with open(DATA_PATH / 'name.csv', encoding='utf-8') as fin:
        reader = csv.reader(fin)
        next(reader)
        for row in reader:
            if row[1] in jp_names:
                foreign_names += row[1:]

    # 特性一覧
    all_abilities = ut.load_abilities()
    abilities = {}
    for name in jp_names:
        abilities[name] = all_abilities[name]

    # all_foreign_abilities['日本語'] = list[全言語]
    all_foreign_abilities = {}
    with open(DATA_PATH / 'ability.csv', encoding='utf-8') as fin:
        reader = csv.reader(fin)
        next(reader)
        for row in reader:
            all_foreign_abilities[row[1]] = row[1:]

    # all_jp_move['外国語'] = '日本語'
    # all_foreign_moves['日本語'] = list[全言語]
    all_jp_move, all_foreign_moves = {}, {}
    with open(DATA_PATH / 'move.csv', encoding='utf-8') as fin:
        reader = csv.reader(fin)
        next(reader)
        for row in reader:
            all_foreign_moves[row[1]] = row[1:]
            for s in all_foreign_moves[row[1]]:
                all_jp_move[s] = row[1]

    if not MULTIPROCESS and False:
        print(f"\t{rank}位")
        print(f"\t{jp_names}")
        print(f"\t{foreign_names}")
        print(f"\t{abilities}")

    langs = ['jpn', 'eng', 'fra', 'eng', 'deu', 'eng', 'kor', 'chi', 'chi']

    # 画像を解析
    img = cv2.imread(str(image_path))
    img = cv2.resize(img, (1920, 1080), interpolation=cv2.INTER_CUBIC)

    lang = 'all'
    lang_idx = None

    result = []
    for i in range(6):
        # 名前を読み取る
        if lang_idx is None:
            candidates = foreign_names
        else:
            candidates = foreign_names[lang_idx::len(langs)]
        name = read_name(img, i, candidates, lang)

        # 言語を特定
        if lang_idx is None:
            lang_idx = candidates.index(name) % len(langs)
            lang = langs[lang_idx]
            if not MULTIPROCESS:
                print(f"\tLang: {lang}")

        if lang_idx > 0:
            # 和訳
            idx = int(foreign_names.index(name) / len(langs))
            name = jp_names[idx]

        # 特性を読み取る
        candidates = [all_foreign_abilities[s][lang_idx] for s in abilities[name]]
        ability = read_ability(img, i, candidates, lang)
        if lang_idx > 0:
            ability = abilities[name][candidates.index(ability)]  # 和訳

        # 技を読み取る
        candidates = [all_foreign_moves[s][lang_idx] for s in all_foreign_moves]
        moves = [all_jp_move[s] for s in read_moves(img, i, candidates, lang)]

        if not MULTIPROCESS:
            print(f"\t{i+1}\t{name}\t{ability}\t{moves}")

        result.append({
            'name': name,
            'ability': ability,
            'move': moves
        })

    with open(dst, 'w', encoding='utf-8') as fout:
        new_dict = {}
        for i, dict in enumerate(result):
            new_dict[str(i)] = dict
        json.dump(new_dict, fout, ensure_ascii=False)

    print(f"パーティ読み取り結果保存 {dst}")
    return [rank, result]


def read_name(img, i: int, candidates: list, lang: str) -> str:
    ix, iy = i % 2, int(i/2)
    x0, y0, w, h = 75, 165, 250, 60
    dx, dy = 912, 270

    x, y = x0+dx*ix, y0+dy*iy
    img1 = ut.BGR2BIN(img[y:y+h, x:x+w], threshold=150, bitwise_not=True)

    if not MULTIPROCESS:
        cv2.imwrite(str(TMP_PATH / f"name_{i}.png"), img1)

    log_dir = '' if MULTIPROCESS else str(TMP_PATH / 'OCR/name/')
    return ut.OCR(img1, lang=lang, log_dir=log_dir, ignore_dakuten=True, candidates=candidates)


def read_ability(img, i: int, candidates: list, lang: str) -> str:
    ix, iy = i % 2, int(i/2)
    x0, y0, w, h = 75, 278, 280, 50
    dx, dy = 912, 270

    x, y = x0+dx*ix, y0+dy*iy
    img1 = ut.BGR2BIN(img[y:y+h, x:x+w], threshold=170, bitwise_not=True)

    if not MULTIPROCESS:
        cv2.imwrite(str(TMP_PATH / f"ability{i}.png"), img1)

    log_dir = '' if MULTIPROCESS else str(TMP_PATH / 'OCR/ability/')
    return ut.OCR(img1, lang=lang, log_dir=log_dir, ignore_dakuten=True, candidates=candidates)


def read_moves(img, i: int, candidates: list, lang: str) -> list:
    ix, iy = i % 2, int(i/2)
    x0, y0, w, h = 596, 168, 300, 54
    dx, dy = 912, 270

    moves = []
    for j in range(4):
        x, y = x0+dx*ix, y0+dy*iy+j*h
        img1 = ut.BGR2BIN(img[y:y+h, x:x+w], threshold=170, bitwise_not=True)
        if not np.any(img1 < 255):
            break  # 技なし

        if not MULTIPROCESS:
            cv2.imwrite(str(TMP_PATH / f"move{i}_{j}.png"), img1)

        log_dir = '' if MULTIPROCESS else str(TMP_PATH / 'OCR/move/')
        s = ut.OCR(img1, lang=lang, log_dir=log_dir, ignore_dakuten=True, candidates=candidates)
        moves.append(s)

    return moves
