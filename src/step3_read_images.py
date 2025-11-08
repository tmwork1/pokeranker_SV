import json
import multiprocessing
import csv
import cv2
import numpy as np

import config
from globals import g
import utils as ut


def read_team_images():
    season, rule = g['season'], g['rule']
    print(f"s{season} {rule} : Reading team images...")

    # バトルデータベースのパーティ一覧を読み込む
    file = config.PDB_DIR / ut.file_from_url(config.get_pdb_teamdata_url(season, rule))
    with open(file, encoding="utf-8") as f:
        pdb = json.load(f)

    print(f"\t{len(pdb['teams'])} teams in pokemon battle database.")
    print(f"\t{ut.count_files(config.TEAM_IMAGE_DIR)} articles are available.")

    # パーティ画像が保存場所
    src_dir = config.TEAM_IMAGE_DIR / config.get_indiv_dir(season, rule)

    # バトルデータベースに登録されているパーティだけ残す
    registered_ranks = [int(player["rank"]) for player in pdb["teams"]]
    images = []
    for path in src_dir.iterdir():
        rank = int(path.stem)
        if rank in registered_ranks:
            images.append(path)
        else:
            print(f"\t{rank}th is not in pokemon battle database. Skip.")

    # 画像解析
    if config.MULTIPROCESS:
        with multiprocessing.Pool(multiprocessing.cpu_count()) as pool:
            res = pool.map(_read_team_image, [(path, pdb, g) for path in images])
    else:
        res = [_read_team_image((path, pdb, g)) for path in images]

    # 解析結果をひとつのファイルにまとめて出力
    results = {str(data[0]): data[1] for data in res if data}
    dst = config.TEAM_SUMMARY_DIR / f"teams_s{season}_{rule}.json"
    with open(dst, 'w', encoding='utf-8') as fout:
        json.dump(results, fout, ensure_ascii=False, indent=4)

    print(f"\tDone. {dst}")


def _read_team_image(args):
    image_path, pdb, g = args

    rank = int(image_path.stem)
    season, rule = g['season'], g['rule']

    dst_dir = config.TEAM_TEXT_DIR / config.get_indiv_dir(season, rule)
    dst_stem = str(rank)
    dst = dst_dir / f"{dst_stem}.json"

    # 並列計算時は、過去の解析結果があればそれを流用する
    if config.MULTIPROCESS:
        if ut.check_file_existence_by_stem(dst_dir, dst_stem):
            print(f"\ts{g['season']} {rank}th : File exists. Skip.")
            with open(dst, encoding='utf-8') as fin:
                dict = json.load(fin)
            result = [dict[key] for key in dict]
            return [rank, result]
    else:
        if rank != 709 and False:
            # DEBUGのため中断
            return

    # バトルデータベースに登録されているポケモンを取得
    pdb_names = []
    for player in pdb['teams']:
        if int(player['rank']) == rank:
            pdb_names = [poke['pokemon'] for poke in player['team']]
            break

    # ポケモンの和名を全言語に変換したリストを取得
    foreign_names = []
    with open(config.DATA_DIR / 'name.csv', encoding='utf-8') as fin:
        reader = csv.reader(fin)
        next(reader)
        for row in reader:
            if row[1] in pdb_names:
                foreign_names += row[1:]

    # 特性の一覧と辞書を用意
    all_abilities = ut.load_abilities()
    abilities = {}
    for name in pdb_names:
        abilities[name] = all_abilities[name]

    # all_foreign_abilities['日本語'] = list[全言語]
    all_foreign_abilities = {}
    with open(config.DATA_DIR / 'ability.csv', encoding='utf-8') as fin:
        reader = csv.reader(fin)
        next(reader)
        for row in reader:
            all_foreign_abilities[row[1]] = row[1:]

    # all_jp_move['外国語'] = '日本語'
    # all_foreign_moves['日本語'] = list[全言語]
    all_jp_move, all_foreign_moves = {}, {}
    with open(config.DATA_DIR / 'move.csv', encoding='utf-8') as fin:
        reader = csv.reader(fin)
        next(reader)
        for row in reader:
            all_foreign_moves[row[1]] = row[1:]
            for s in all_foreign_moves[row[1]]:
                all_jp_move[s] = row[1]

    # DEBUG
    if not config.MULTIPROCESS and False:
        print(f"\t{rank}位")
        print(f"\t{pdb_names}")
        print(f"\t{foreign_names}")
        print(f"\t{abilities}")

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
            candidates = foreign_names[lang_idx::len(config.OCR_LANGS)]
        name = read_name(img, i, candidates, lang)

        # 一体目で言語を特定
        if lang_idx is None:
            lang_idx = candidates.index(name) % len(config.OCR_LANGS)
            lang = config.OCR_LANGS[lang_idx]
            if not config.MULTIPROCESS:
                print(f"\tLang: {lang}")

        # 外国語なら和訳する
        if lang_idx > 0:
            idx = int(foreign_names.index(name) / len(config.OCR_LANGS))
            name = pdb_names[idx]

        # 特性を読み取る
        candidates = [all_foreign_abilities[s][lang_idx] for s in abilities[name]]
        ability = read_ability(img, i, candidates, lang)
        if lang_idx > 0:
            ability = abilities[name][candidates.index(ability)]  # 和訳

        # 技を読み取る
        candidates = [all_foreign_moves[s][lang_idx] for s in all_foreign_moves]
        moves = [all_jp_move[s] for s in read_moves(img, i, candidates, lang)]

        if not config.MULTIPROCESS:
            print(f"\t{i+1}\t{name}\t{ability}\t{moves}")

        result.append({
            'name': name,
            'ability': ability,
            'move': moves
        })

    # パーティごとに結果を一時ファイルに出力する
    with open(dst, 'w', encoding='utf-8') as fout:
        new_dict = {}
        for i, dict in enumerate(result):
            new_dict[str(i)] = dict
        json.dump(new_dict, fout, ensure_ascii=False, indent=4)

    print(f"パーティ解析結果 {dst}")
    return [rank, result]


def read_name(img, i: int, candidates: list, lang: str) -> str:
    ix, iy = i % 2, int(i/2)
    x0, y0, w, h = 75, 165, 250, 60
    dx, dy = 912, 270

    x, y = x0+dx*ix, y0+dy*iy
    bin_img = ut.BGR2BIN(img[y:y+h, x:x+w], threshold=150, bitwise_not=True)
    return ut.OCR(bin_img, lang=lang, ignore_dakuten=True, candidates=candidates)


def read_ability(img, i: int, candidates: list, lang: str) -> str:
    ix, iy = i % 2, int(i/2)
    x0, y0, w, h = 75, 278, 280, 50
    dx, dy = 912, 270

    x, y = x0+dx*ix, y0+dy*iy
    bin_img = ut.BGR2BIN(img[y:y+h, x:x+w], threshold=170, bitwise_not=True)
    return ut.OCR(bin_img, lang=lang, ignore_dakuten=True, candidates=candidates)


def read_moves(img, i: int, candidates: list, lang: str) -> list:
    ix, iy = i % 2, int(i/2)
    x0, y0, w, h = 596, 168, 300, 54
    dx, dy = 912, 270

    moves = []
    for j in range(4):
        x, y = x0+dx*ix, y0+dy*iy+j*h
        bin_img = ut.BGR2BIN(img[y:y+h, x:x+w], threshold=170, bitwise_not=True)
        if not np.any(bin_img < 255):
            break  # 技なし
        s = ut.OCR(bin_img, lang=lang, ignore_dakuten=True, candidates=candidates)
        moves.append(s)

    return moves
