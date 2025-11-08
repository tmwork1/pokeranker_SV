from pathlib import Path
import os
import cv2
import pyocr
import pyocr.builders
from PIL import Image
import Levenshtein
import jaconv
import glob
from datetime import datetime, timedelta, timezone
import csv
import shutil
import urllib.request
import shutil
import socket

from config import *

OCR_history = []


def download_url(url: str, dst, timeout: int = 10) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as res:
            with open(dst, 'wb') as f:
                shutil.copyfileobj(res, f)
        return True
    except socket.timeout:
        return False
    except Exception as e:
        return False


def season_rule_dir(g) -> str:
    return f"s{g['season']}_{g['rule']}"


def clear_tmp_dir():
    """tmpフォルダを空にする"""
    if os.path.exists('tmp/'):
        shutil.rmtree('tmp/')
    os.makedirs('tmp/', exist_ok=True)


def num_files(dir: Path):
    return sum(1 for f in dir.iterdir() if f.is_file())


def load_zukan():
    zukan = {}
    with open(DATA_PATH / 'zukan.csv', encoding='utf-8') as fin:
        reader = csv.reader(fin)
        header = next(reader)
        for row in reader:
            # 特定の世代のみ抽出
            # if int(row[14]) != 9:
            #    continue
            alias = row[5]
            zukan[alias] = dict(zip(header, row))
    return zukan


def load_abilities():
    abilities = {}
    with open(DATA_PATH / 'zukan.csv', encoding='utf-8') as fin:
        reader = csv.reader(fin)
        next(reader)
        for row in reader:
            # 特定の世代のみ抽出
            # if int(row[14]) != 9:
            #    continue
            name = row[3]
            if name not in abilities:
                abilities[name] = []
            for s in row[11:14]:
                if s and s not in abilities[name]:
                    abilities[name].append(s)
    return abilities


def current_season():
    dt_now = datetime.now(timezone(timedelta(hours=+9), 'JST'))
    y, m, d = dt_now.year, dt_now.month, dt_now.day
    return max(12*(y-2022) + m - 11 - (d == 1), 1)


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


def find_most_similar(str_list, s, ignore_dakuten=False):
    if s in str_list:
        return s
    s1 = jaconv.hira2kata(s)
    if ignore_dakuten:
        trans = str.maketrans('ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ',
                              'カキクケコサシスセソタチツテトハヒフヘホハヒフヘホ')
        s1 = s1.translate(trans)
        distances = [Levenshtein.distance(
            s1, jaconv.hira2kata(s).translate(trans)) for s in str_list]
    else:
        distances = [Levenshtein.distance(
            s1, jaconv.hira2kata(s)) for s in str_list]
    return str_list[distances.index(min(distances))]


def file_name_exists(dir, stem: str) -> bool:
    for file in Path(dir).iterdir():
        if file.is_file() and file.stem == stem:
            return True
    return False


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

        if lang == 'all':
            lang = 'jpn+chi+kor+eng+fra+deu'
        elif lang == 'num':
            lang = 'eng'
            builder = pyocr.builders.DigitBuilder(tesseract_layout=7)

        if scale > 1:
            img = cv2.resize(img, (img.shape[1]*scale, img.shape[0]*scale), interpolation=cv2.INTER_CUBIC)

        tools = pyocr.get_available_tools()
        result = tools[0].image_to_string(cv2pil(img), lang=lang, builder=builder)
        # print(f'\tOCR: {result}')

        # 履歴を保存
        if result and log_dir:
            OCR_history.append(result)
            cv2.imwrite(f"{log_dir}{len(OCR_history)-1}.png", img)

    if candidates:
        result = find_most_similar(
            candidates, result, ignore_dakuten=ignore_dakuten)

    return result


def template_match_score(img, template):
    result = cv2.matchTemplate(img, template, cv2.TM_CCORR_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val
