import requests
from bs4 import BeautifulSoup
import os
import urllib
import pathlib
import cv2
import pyocr, pyocr.builders
from PIL import Image
import Levenshtein
import jaconv
import json
import glob
import numpy as np
import pandas as pd
import shutil


TESSERACT_PATH = os.getcwd()+'/Tesseract-OCR'
TESSDATA_PATH = TESSERACT_PATH + '/tessdata'
os.environ["PATH"] += os.pathsep + TESSERACT_PATH
os.environ["TESSDATA_PREFIX"] = TESSDATA_PATH


def get_html(url, dst):
    res = None
    try:
        res = requests.get(url)
        with open(dst, 'w', encoding='utf-8') as f:
            f.write(res.text)
    except:
        print(f"{url}\n\tis not available")
    return res
        
def cv2pil(image):
    new_image = image.copy()
    if new_image.ndim == 2:  # モノクロ
        pass
    elif new_image.shape[2] == 3:  # カラー
        new_image = cv2.cvtColor(new_image, cv2.COLOR_BGR2RGB)
    elif new_image.shape[2] == 4:  # 透過
        new_image = cv2.cvtColor(new_image, cv2.COLOR_BGRA2RGBA)
    new_image = Image.fromarray(new_image)
    return new_image

def BGR2BIN(img, threshold=128, bitwise_not=False):
    img1 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, img1 = cv2.threshold(img1, threshold, 255, cv2.THRESH_BINARY)
    if bitwise_not:
        img1 = cv2.bitwise_not(img1)
    return img1

def most_similar_element(str_list, s, ignore_dakuten=False):
    if s in str_list:
        return s
    s1 = jaconv.hira2kata(s)
    if ignore_dakuten:
        trans = str.maketrans('ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ',
            'カキクケコサシスセソタチツテトハヒフヘホハヒフヘホ')
        s1 = s1.translate(trans)
        distances = [Levenshtein.distance(s1, jaconv.hira2kata(s).translate(trans)) for s in str_list]
    else:
        distances = [Levenshtein.distance(s1, jaconv.hira2kata(s)) for s in str_list]
    return str_list[distances.index(min(distances))]

OCR_history = []

def OCR(img, lang='jpn', candidates=[], ignore_dakuten=False, scale=1, log_dir=''):
    result = ''
    
    # 履歴と照合
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        if log_dir[-1] != '/':
            log_dir += '/'
        for s in glob.glob(log_dir + '*'):
            template = cv2.cvtColor(cv2.imread(s), cv2.COLOR_BGR2GRAY)
            if template_match_score(img, template) > 0.99:
                s = os.path.splitext(os.path.basename(s))[0]
                result = OCR_history[int(s)]
    
    # 履歴に合致しなければOCRする
    if not result:
        builder = pyocr.builders.TextBuilder(tesseract_layout=7)
        match lang:
            case 'all':
                lang = 'jpn+chi+kor+eng+fra+deu'
            case 'num':
                lang = 'eng'
                builder = pyocr.builders.DigitBuilder(tesseract_layout=7)
        if scale > 1:
            img = cv2.resize(img, (img.shape[1]*scale, img.shape[0]*scale), interpolation=cv2.INTER_CUBIC)
        tools = pyocr.get_available_tools()
        result = tools[0].image_to_string(cv2pil(img), lang=lang, builder=builder)
        #print(f'\tOCR: {result}')
        
        # 履歴を保存
        if result and log_dir:
            OCR_history.append(result)
            cv2.imwrite(f"{log_dir}{len(OCR_history)-1}.png", img)
    
    if len(candidates):
        result = most_similar_element(candidates, result, ignore_dakuten=ignore_dakuten)

    return result

def template_match_score(img, template):
    result = cv2.matchTemplate(img, template, cv2.TM_CCORR_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val


def download_party_image(season, rule):
    """構築記事のパーティ画像をダウンロードする"""
    rule_code = {'single': 0, 'double': 1}
    n_ranker = 0
    n_data = 0

    # 構築記事を保存するフォルダを作成
    dir_article = f"party/article/s{season}_{rule}/"
    os.makedirs(dir_article, exist_ok=True)

    # パーティ画像を保存するフォルダを作成
    dir_party = f"party/image/s{season}_{rule}/"
    os.makedirs(dir_party, exist_ok=True)

    # レンタルパーティ判定用のテンプレート画像
    templ_party = BGR2BIN(cv2.imread('data/party.png'), threshold=85)

    for page in range(1, 4):
        # バトルデータベースのHTMLを取得
        url = f"https://sv.pokedb.tokyo/trainer/list?season={season}&rule={rule_code[rule]}&party=1&page={page}"
        res = get_html(url, dst=f"pdb/party_s{season}_{rule}_{page}.html")
        if res is None:
            break
        soup = BeautifulSoup(res.text, 'html.parser')

        # 構築記事のリンクを取得
        tags = soup.find_all('a', attrs={'class': 'mt-5'})
        print(f"s{season} {rule} {page}ページ目 構築記事 {len(tags)}件")
        n_ranker += len(tags)

        for k, tag in enumerate(tags):
            # 順位を取得
            elem = tag.parent.previous_element.previous_element.previous_element.previous_element
            rank = int(elem.text)

            #if rank != 13:
            #    continue

            print(f"{rank}位 ({k+1}/{len(tags)})")

            # すでにファイルがあればスキップ
            if f"{dir_party}{rank}." in ' '.join(glob.glob(f"{dir_party}*")).replace('\\', '/'):
                print('\tすでに画像が保存されています')
                n_data += 1
                continue

            # 構築記事を取得
            url_article = tag.get('href')
            res = get_html(url_article, dst=f"{dir_article}{rank}.html")
            if res is None:
                continue

            # 記事内の画像URLをすべて取得
            soup = BeautifulSoup(res.text, 'html.parser')
            image_tags = soup.find_all('img')
            image_urls = [tag2.get(attr) for attr in ['src', 'data-lazy-src']
                          for tag2 in image_tags if tag2.get(attr) is not None]
            
            for url in image_urls:
                # 拡張子でフィルタ
                ext = url[url.rfind('.')+1:]
                if '?' in ext:
                    ext = ext[:ext.find('?')]
                
                if ext == 'gif':
                    continue
                elif len(ext) > 3:
                    ext = 'jpg'

                # 相対パスの補完
                match url[0]:
                    case '/':
                        url = url_article[:url_article.rfind('/')] + url
                    case '.':
                        url = url_article[:url_article.rfind('/')] + url[1:]

                # 画像を一時保存
                img_file = f"tmp/{url[url.rfind('/')+1:]}"
                if '?' in img_file:
                    img_file = img_file[:img_file.find('?')]
                try:
                    urllib.request.urlretrieve(url, img_file)
                except:
                    print(f"{url} is not available")
                    continue

                img = cv2.imread(img_file)
                if img is None:
                    continue

                # FullHD変換
                resized = cv2.resize(img, (1920, 1080))
                
                # パーティ画像かどうか判定する
                img1 = BGR2BIN(resized[290:390, 870:930], threshold=85)
                score = template_match_score(img1, templ_party)

                if score > 0.95:
                    # 画像が小さい場合はスキップ
                    if img.shape[1] <= 480:
                        print(f"画像が小さすぎます {url}")
                        continue
                    
                    s = f"{dir_party}{rank}.{ext}"
                    cv2.imwrite(s, img)
                    print(f"\t{score=:.2f} {url}")
                    print(f"Saved as {s}")
                    n_data += 1
                    #cv2.imwrite('tmp/img1.png', img1) # テンプレート画像保存
                    break

            # 一時保存した画像を削除
            for file in pathlib.Path('tmp/').iterdir():
                file.unlink()

    print(f"パーティ画像取得 {n_data}/{n_ranker}件")

def read_party_image(season, rule):
    """パーティ画像を解析する"""

    # 名前一覧の読み込み
    # names['外国語'] = '日本語', names2['日本語'] = list[全言語]
    names, names2 = {}, {}
    with open('data/foreign_name.txt', encoding='utf-8') as fin:
        next(fin)
        for line in fin:
            data = line.split()
            names2[data[0]] = data
            for d in data:
                names[d] = data[0]
    #print(names)

    # 特性一覧の読み込み
    # abilities['外国語'] = '日本語', abilities2['日本語'] = list[全言語]
    abilities, abilities2 = {}, {}
    with open('data/foreign_ability.txt', encoding='utf-8') as fin:
        next(fin)
        for line in fin:
            data = line.split()
            abilities2[data[0]] = data
            for d in data:
                abilities[d] = data[0]

    # 技一覧の読み込み
    # moves['外国語'] = '日本語', moves2['日本語'] = list[全言語]
    moves, moves2 = {}, {}
    with open('data/foreign_move.txt', encoding='utf-8') as fin:
        next(fin)
        for line in fin:
            data = line.replace('\n', '').split('\t')
            moves2[data[0]] = data
            for d in data:
                moves[d] = data[0]
    #print(moves)

    # SV図鑑の読み込み
    zukan_abilities = {}
    with open('data/zukan.txt', encoding='utf-8') as fin:
        next(fin)
        for line in fin:
            data = line.split()
            name = data[1]
            if 'ロトム' in name:
                name = 'ロトム'
            else:
                if '(' in name:
                    name = name[:name.find('(')]
                name = name.replace('パルデア','')
                name = name.replace('ヒスイ','')
                name = name.replace('ガラル','')
                name = name.replace('アローラ','')
                name = name.replace('ホワイト','')
                name = name.replace('ブラック','')
            
            if name not in zukan_abilities:
                zukan_abilities[name] = []
            
            # 特性
            for s in data[4:8]:
                if s != '-' and s not in zukan_abilities[name]:
                    zukan_abilities[name].append(s)

    #print(zukan_abilities)

    # SV図鑑にない名前と特性を削除
    new_dict = {}
    for s in names:
        if names[s] in zukan_abilities:
            new_dict[s] = names[s]
    names = new_dict.copy()

    new_dict = {}
    for s in abilities:
        if abilities[s] in sum(zukan_abilities.values(), []):
            new_dict[s] = abilities[s]
    abilities = new_dict.copy()

    # パーティ画像の解析
    result = {}
    files = glob.glob(f"party/image/s{season}_{rule}/*")
    print(f"パーティ画像 {len(files)}件")

    langs = ['jpn', 'eng', 'fra', 'deu', 'eng', 'eng', 'kor', 'chi', 'chi']

    for k, file in enumerate(files):
        rank = int(file[file.find('\\')+1:file.rfind('.')])

        #if rank != 228:
        #    continue

        print(f"{rank}位 ({k+1}/{len(files)})")
        result[str(rank)] = []

        img = cv2.imread(file)
        img = cv2.resize(img, (1920, 1080), interpolation=cv2.INTER_CUBIC)
        cv2.imwrite('tmp/party.png', img)

        lang_idx = None

        dx, dy = 912, 270
        for i in range(6):
            ix, iy = i%2, int(i/2)

            # 名前
            x0, y0, w, h = 75, 165, 250, 60
            x, y = x0+dx*ix, y0+dy*iy
            img1 = BGR2BIN(img[y:y+h, x:x+w], threshold=160, bitwise_not=True)
            if lang_idx is None:
                s = OCR(img1, lang='all', log_dir='tmp/OCR/name/', ignore_dakuten=True,
                        candidates=list(names.keys()))
            else:
                s = OCR(img1, lang=langs[lang_idx], log_dir='tmp/OCR/name/', ignore_dakuten=True,
                        candidates=[names2[s1][lang_idx] for s1 in names2])
            cv2.imwrite(f'tmp/name{i}.png', img1)
            s = OCR(img1, lang='all', log_dir='tmp/OCR/name/', ignore_dakuten=True,
                    candidates=list(names.keys()))
            name = names[s]
            print(i+1, name)

            # 言語を判定
            lang_idx = names2[name].index(s) % 7

            # 特性
            x0, y0, w, h = 75, 278, 280, 50
            x, y = x0+dx*ix, y0+dy*iy
            img1 = BGR2BIN(img[y:y+h, x:x+w], threshold=170, bitwise_not=True)
            cv2.imwrite(f'tmp/ability{i}.png', img1)
            s = OCR(img1, lang=langs[lang_idx], log_dir='tmp/OCR/ability/', ignore_dakuten=True,
                    candidates=[abilities2[s1][lang_idx] for s1 in zukan_abilities[name]])
            ability = abilities[s]
            print('\t', ability)

            # 技
            move = []
            x0, y0, w, h = 596, 168, 300, 54
            for j in range(4):
                x, y = x0+dx*ix, y0+dy*iy+j*h
                img1 = BGR2BIN(img[y:y+h, x:x+w], threshold=170, bitwise_not=True)
                cv2.imwrite(f'tmp/move{i}_{j}.png', img1)
                s = OCR(img1, lang=langs[lang_idx], log_dir='tmp/OCR/move/', ignore_dakuten=True,
                    candidates=[moves2[s1][lang_idx] for s1 in moves2])
                move.append(moves[s])
                print('\t', j+1, move[-1])

            # 記録
            result[str(rank)].append({
                'name': name,
                'ability': ability,
                'move': move
            })

    # 最終出力
    dst = f"party/party_s{season}_{rule}.json"
    with open(dst, 'w', encoding='utf-8') as fout:
        json.dump(result, fout, ensure_ascii=False)
    print(f"Saved as {dst}")

def unify_data(season, rule):
    """バトルデータベースとパーティ画像の情報を統合する"""

    # バトルデータベースの上位構築一覧をダウンロード
    url = f"https://sv.pokedb.tokyo/opendata/s{season}_{rule}_ranked_teams.json"
    dst = f"pdb/{url[url.rfind('/')+1:]}"
    urllib.request.urlretrieve(url, dst)
    print(f"Saved as {dst}")

    # バトルデータベース情報の読み込み
    with open(f"pdb/s{season}_{rule}_ranked_teams.json", encoding='utf-8') as fin:
        pdb = json.load(fin)
    teams = pdb['teams']
    
    # パーティ画像情報の読み込み
    with open(f"party/party_s{season}_{rule}.json", encoding='utf-8') as fin:
        party_list = json.load(fin)

    pokemon_list = []

    # 全パーティのループ
    for team in teams:
        rank = team['rank']
        rate = team['rating_value']

        # ポケモンの辞書に順位とレートを追加
        for p in team['team']:
            p['rank'] = int(rank)
            p['rate'] = rate
            
            # レンタル画像の情報を追加
            if rank in party_list:
                party = party_list[rank]
                names = [d['name'] for d in party]
                
                name = most_similar_element(names, p['pokemon'])
                idx = names.index(name)

                p['ability'] = party[idx]['ability']
                for i in range(4):
                    p[f'move_{i}'] = party[idx]['move'][i]

            pokemon_list.append(p)

    df = pd.DataFrame(pokemon_list)

    # 列の並び替え
    columns = df.columns.values
    first_keys = ['rank', 'rate']
    for key in first_keys:
        columns = columns[columns != key]
    columns = np.insert(columns, 0, first_keys)
    df = df.reindex(columns, axis=1)

    os.makedirs('output', exist_ok=True)
    dst = f"output/s{season}_{rule}.csv"
    with open(dst, 'w', encoding='utf-8') as fout:
        df.to_csv(dst)

def test():
    img = cv2.imread("party/image/s22_single/2.jpg")
    resized = cv2.resize(img, (1920, 1080))
    img1 = resized[290:390, 870:930]
    img1 = BGR2BIN(img1, threshold=85)
    cv2.imwrite('tmp/trim.png', img1)
    exit()

if __name__ == '__main__':
    #----------------------------
    season = 22

    rule = 'single'
    #rule = 'double'
    #----------------------------

    # 一時フォルダを空にする
    if os.path.exists('tmp/'):
        shutil.rmtree('tmp/')
    os.makedirs('tmp/', exist_ok=True)
    print('./tmp フォルダを空にしました')

    # 過去シーズンのループ
    for i in range(season, 0, -1):
        print(f"シーズン{i} {rule}")

        # 1. 構築記事のパーティ画像をダウンロード
        download_party_image(i, rule)

        # 2. パーティ画像を解析
        read_party_image(i, rule)

        # 3. バトルデータベースとパーティ画像の情報を統合
        unify_data(i, rule)

        break