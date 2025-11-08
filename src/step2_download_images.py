from bs4 import BeautifulSoup
import cv2
import threading

import config
from globals import g
import utils as ut


bin_threshold = 96


def download_team_images():
    """バトルデータベースからすべての構築記事にアクセスし、レンタルパーティ画像をダウンロードする"""
    season, rule = g['season'], g['rule']
    print(f"s{season} {rule} : Downloading team images...")

    # ランカーの合計数
    n_ranker = 0

    # バトルデータベースの構築記事をすべて走査する
    for page in range(1, 4):
        url = config.get_pdb_portal_url(season, rule, page)
        dst = config.PDB_DIR / f"s{season}_{rule}_page{page}.html"

        print(str(dst))

        # バトルデータベースのポータルページのHTMLを取得
        ut.download_url(url, dst)

        if dst.exists():
            with open(dst, encoding="utf-8") as f:
                text = f.read()
        else:
            print(f"\tDownload failed : {url}")
            break

        soup = BeautifulSoup(text, 'html.parser')

        # 記事内のすべてのリンクを取得
        tags = soup.find_all('a', attrs={'class': 'mt-5'})

        # リンクの数 = プレイヤー数
        n_ranker += len(tags)

        print(f"\ts{season} {rule}: {len(tags)} articles in page{page}")

        if config.MULTIPROCESS:
            thread_list = []
            for tag in tags:
                thread_list.append(threading.Thread(target=_download_team_image, args=(tag,)))
                thread_list[-1].start()
            for th in thread_list:
                th.join()

        else:
            for tag in tags:
                _download_team_image(tag)

        # 取得したファイルを数える
        n_files = ut.count_files(config.TEAM_IMAGE_DIR / config.get_indiv_dir(season, rule))
        print(f"s{season} {rule} : Obtained {n_files}/{n_ranker} articles.\n")


def _download_team_image(tag):
    elem = tag.previous_element.previous_element

    # バトルデータベースのHTMLから順位を取得
    rank = int(elem.text)

    season, rule = g['season'], g['rule']
    dst_dir = config.TEAM_IMAGE_DIR / config.get_indiv_dir(season, rule)
    dst_stem = str(rank)

    # 並列計算時は、すでにパーティ画像が存在する場合はスキップする
    if config.MULTIPROCESS:
        if ut.check_file_existence_by_stem(dst_dir, dst_stem):
            print(f"\ts{g['season']} {rank}th : File exists. Skip.")
            return
    else:
        if rank != 91 and False:
            # DEBUGのため中断
            return

    # 構築記事のHTMLをダウンロード
    url_article = tag.get('href')
    dst = config.TEAM_ARTICLE_DIR / config.get_indiv_dir(season, rule) / f"{rank}.html"
    if not ut.download_url(url_article, dst):
        print(f"\ts{g['season']} {rank}th Failed to download article: {url_article}")
        return

    with open(dst, encoding="utf-8") as f:
        try:
            text = f.read()
            soup = BeautifulSoup(text, 'html.parser')
        except Exception as e:
            print(f"\tFailed to open {dst}")
            return

    # 記事内の画像URLをすべて取得
    image_tags = soup.find_all('img')
    image_urls = [tag2.get(attr) for attr in ['src', 'data-lazy-src'] for tag2 in image_tags if tag2.get(attr) is not None]

    # レンタルパーティ画像を識別するテンプレート画像
    team_template = ut.BGR2BIN(cv2.imread(str(config.TEAM_TEMPLATE_IMAGE)),
                               threshold=bin_threshold)

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
        dst = str(config.MISC_DIR / url[url.rfind('/')+1:])
        if '?' in dst:
            dst = dst[:dst.find('?')]

        if not ut.download_url(url, dst):
            continue

        img = cv2.imread(dst)
        if img is None:
            continue

        # テンプレートマッチ
        resized = cv2.resize(img, (1920, 1080))  # FullHD
        bin_img = ut.BGR2BIN(resized[290:390, 870:930], threshold=bin_threshold)
        score = ut.template_match_score(bin_img, team_template)

        # DEBUG
        if not config.MULTIPROCESS and False:
            print(f"\t{rank}\t{score:.3f}\t{url}")

        if score > 0.88:
            if img.shape[1] <= 480:
                # print(f"画像が小さすぎます {url}")
                continue

            # 目的の画像が見つかったら保存して終了する
            dst = dst_dir / f"{dst_stem}.{ext}"
            cv2.imwrite(str(dst), img)
            print(f"\ts{g['season']} {rank}th : {dst}")
            return
