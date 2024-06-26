import requests
from urllib.parse import urlparse, urlencode, urlunparse, quote_plus
from datetime import datetime, timedelta
from bs4 import BeautifulSoup as bs
from pymongo import MongoClient
import argparse
import time
import random
import json


def make_url(base_url, params):
    parts = urlparse(base_url)
    parts = parts._replace(query=urlencode(params, doseq=True))
    return urlunparse(parts)

def fetch_news_data(params, headers, url, db, args):
    flag = 0
    total = []
    while flag < 30:
        print(flag)
        naver_news_links = []
        batch = []

        new_url = make_url(url, params)
        response = requests.get(new_url, headers=headers)
        if response.status_code != 200:
            print("Connection Issue")
            time.sleep(float(random.uniform(0.2, 0.3)))
            continue

        soup = bs(response.content, 'html.parser')
        naver_news_links = [a['href'][2:-2] for a in soup.find_all('a', string='네이버뉴스') if a['href']]

        if not naver_news_links:
            params['start'] = str(int(params['start']) + 10)
            print("No NAVER NEWS Platforms")
            time.sleep(float(random.uniform(0.2, 0.3)))
            flag += 1
            continue

        for link in naver_news_links:
            print("link: ", link)

            if 'sports' in link or 'entertain' in link:
                continue

            article_res = requests.get(link)

            if article_res.status_code != 200:
                print("Connection Issue")
                time.sleep(float(random.uniform(0.2, 0.3)))
                continue

            article_soup = bs(article_res.content, 'html.parser')

            try:
                title = article_soup.select_one('#title_area > span').get_text(strip=True)
            except:
                article_res = requests.get(link)
                article_soup = bs(article_res.content, 'html.parser')
                title = article_soup.select_one('#title_area > span').get_text(strip=True)

            if params['query'] not in title:
                time.sleep(float(random.uniform(0.2, 0.3)))
                continue
            press_select = article_soup.select_one('#ct > div.media_end_head.go_trans > div.media_end_head_top._LAZY_LOADING_WRAP > a > img.media_end_head_top_logo_img.light_type._LAZY_LOADING._LAZY_LOADING_INIT_HIDE')
            press = press_select['title'] if 'title' in press_select.attrs else 'Title attribute not found'
            date = article_soup.select_one('#ct > div.media_end_head.go_trans > div.media_end_head_info.nv_notrans > div.media_end_head_info_datestamp > div:nth-child(1) > span')['data-date-time']
            summary = article_soup.select_one('#dic_area > strong').get_text(strip=True) if article_soup.select_one('#dic_area > strong') else None

            for span in article_soup.find_all('span', class_='end_photo_org'):
                span.decompose()

            content = article_soup.select_one('#dic_area').get_text(strip=True).replace("\n\n\n", "")

            if summary is not None:
                index = content.find(summary)
                content = content[index + len(summary):] if index != -1 else content
            tmp = {
                'news_date': date.split(" ")[0],
                'news_time': date.split(" ")[1],
                'query': params['query'],
                'title': title,
                'press': press,
                'summary': summary,
                'content': content,
                'url': link,
            }
            batch.append(tmp)
            time.sleep(float(random.uniform(0.2, 0.3)))

        if batch:
            urls = [news['url'] for news in batch]
            existing_news = db.news.find({"url": {"$in": urls}, "query": params['query']})
            existing_urls = {news['url'] for news in existing_news}

            new_batch = [news for news in batch if news['url'] not in existing_urls]

            if new_batch:
                db.news.insert_many(new_batch)
                flag = 0
            else:
                print("All batch data is Duplicated")
                flag += 1
            total.extend(new_batch)

        print("start: ", params['start'])
        params['start'] = str(int(params['start']) + 10)
        time.sleep(float(random.uniform(0.4, 0.6)))

    return total

def main(args):
    start = time.time()
    start_date = datetime.strptime(args.get("ds", datetime.now().strftime("%Y.%m.%d")), "%Y.%m.%d")
    end_date = datetime.strptime(args.get("de", datetime.now().strftime("%Y.%m.%d")), "%Y.%m.%d") + timedelta(days=1)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    if args.get("port", "") == '':
        client = MongoClient(args.get("host", "mongo.stockhelper-mongodb.store"), username=args.get("username", "root"), password=args.get("password", "financial"))
    else:
        client = MongoClient(args.get("host", "mongo.stockhelper-mongodb.store"), port=args.get("port", "27017"),username=args.get("username", "root"), password=args.get("password", "financial"))

    db = client[args.get("database", "financial")]

    current_date = start_date
    while current_date < end_date:
        next_date = current_date + timedelta(days=1)
        params = {
            'filed': '0',
            'is_dts': '0',
            'is_sug_officeid': '0',
            'office_category': '0',
            'office_section_code': '0',
            'service_area': '0',
            'query': args.get("query", "삼성전자"),
            'sort': '1',
            'start': '1',
            'where': 'news_tab_api',
            'nso': f'so:dd,p:from{current_date.strftime("%Y%m%d")}to{current_date.strftime("%Y%m%d")}',
            'ds': current_date.strftime("%Y.%m.%d"),
            'de': current_date.strftime("%Y.%m.%d")
        }

        url = 'https://s.search.naver.com/p/newssearch/search.naver'
        tmp_news = fetch_news_data(params, headers, url, db, args)
        current_date = next_date

    print("Execution time: ", time.time() - start)
    
    result = {"payload": []}
    return result