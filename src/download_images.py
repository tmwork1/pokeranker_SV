# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import cv2
import threading

from config import *
from globals import g
import utils as ut


def download_team_images():
    season, rule = g['season'], g['rule']
    print(f"s{season} {rule}: Download team images")

    rule_code = {'single': 0, 'double': 1}
    n_ranker = 0

    # パーティ画像を取得する
    for page in range(1, 4):
        # バトルデータベースのHTMLを取得
        url = f"https://sv.pokedb.tokyo/trainer/list?season={season}&rule={rule_code[rule]}&party=1&page={page}"
        dst = PDB_PATH / f"team_s{season}_{rule}_{page}.html"

        ut.download_url(url, dst)
        if dst.exists():
            with open(dst, encoding="utf-8") as f:
                text = f.read()
        else:
            print(f"Download failed: {url}")
            break  # 中断

        soup = BeautifulSoup(text, 'html.parser')

        # 構築記事のリンクを取得
        tags = soup.find_all('a', attrs={'class': 'mt-5'})
        print(f"\ts{season} {rule}: {len(tags)} articles in page{page}")
        n_ranker += len(tags)

        if MULTIPROCESS:
            thread_list = []
            for tag in tags:
                thread_list.append(threading.Thread(target=_download_team_image, args=(tag,)))
                thread_list[-1].start()
            for th in thread_list:
                th.join()
            ut.clear_tmp_dir()

        else:
            for tag in tags:
                ut.clear_tmp_dir()
                _download_team_image(tag)

        # 取得したファイルを数える
        print(f"s{season} {rule}: Completed")
        print(f"{ut.num_files(TEAM_IMAGE_PATH / ut.season_rule_dir(g))}/{n_ranker} articles are available\n")


def _download_team_image(tag):
    elem = tag.previous_element.previous_element

    # バトルデータベースのHTMLから順位を取得
    rank = int(elem.text)

    # 条件に応じて処理を中断
    if MULTIPROCESS:
        if ut.file_name_exists(TEAM_IMAGE_PATH / ut.season_rule_dir(g), f"{rank}"):
            print(f"\ts{g['season']} {rank}th: File exists. Skip.")
            return
    else:
        if rank != 91 and False:
            return

    # 構築記事のHTMLを取得
    url_article = tag.get('href')
    dst = TEAM_ARTICLE_PATH / ut.season_rule_dir(g) / f"{rank}.html"
    if not ut.download_url(url_article, dst):
        print(f"\ts{g['season']} {rank}th Failed to download article: {url_article}")
        return

    # 記事内の画像URLをすべて取得
    with open(dst, encoding="utf-8") as f:
        try:
            text = f.read()
            soup = BeautifulSoup(text, 'html.parser')
        except Exception as e:
            print(f"\tFailed to open {dst}")
            return

    image_tags = soup.find_all('img')
    image_urls = [tag2.get(attr) for attr in ['src', 'data-lazy-src'] for tag2 in image_tags if tag2.get(attr) is not None]

    # レンタルパーティ画像を識別するテンプレート画像
    team_template = ut.BGR2BIN(cv2.imread(str(DATA_PATH / 'team.png')), threshold=96)

    # 記事内の画像URLをすべて探索
    for url in image_urls:
        if not url:
            continue

        # 拡張子でフィルタ
        ext = url[url.rfind('.')+1:]
        if '?' in ext:
            ext = ext[:ext.find('?')]

        if ext == 'gif':
            continue
        elif len(ext) > 3:
            ext = 'jpg'

        # 相対パスの補完
        if url[0] == '/':
            url = url_article[:url_article.rfind('/')] + url
        elif url[0] == '.':
            url = url_article[:url_article.rfind('/')] + url[1:]

        # 画像を一時保存
        dst = str(TMP_PATH / url[url.rfind('/')+1:])
        if '?' in dst:
            dst = dst[:dst.find('?')]

        if not ut.download_url(url, dst):
            continue

        img = cv2.imread(dst)
        if img is None:
            continue

        # FullHD変換
        resized = cv2.resize(img, (1920, 1080))

        # パーティ画像の識別
        img1 = ut.BGR2BIN(resized[290:390, 870:930], threshold=96)
        score = ut.template_match_score(img1, team_template)

        if not MULTIPROCESS and False:
            print(f"\t{rank}\t{score:.3f}\t{url}")

        if score > 0.88:
            if img.shape[1] <= 480:
                # print(f"画像が小さすぎます {url}")
                continue

            s = TEAM_IMAGE_PATH / ut.season_rule_dir(g) / f"{rank}.{ext}"
            cv2.imwrite(str(s), img)
            print(f"\ts{g['season']} {rank}th: Saved as {s}")

            return img
