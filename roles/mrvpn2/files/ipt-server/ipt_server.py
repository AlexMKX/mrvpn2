import logging
import sqlite3
import tempfile

from pyroute2 import IPRoute

import gzip, urllib, csv, io, datetime, re, ipaddress

from Config import MySettings, State
from MrRoute import MrRoute
from typing import Dict, Set, Any, List

import websockets
import asyncio
import subprocess
from collections import defaultdict
import concurrent.futures
from lib import *
import random
import urllib.request

logging.basicConfig(level=logging.DEBUG)

DEFAULT_METRIC = 100
ALL_METRICS = set()

CONFIG: MySettings
ROUTES: List[MrRoute] = []

logger = logging.getLogger(__name__)


def get_request(l_url) -> urllib.request.Request:
    buster = random.Random().randint(1, 1000000)
    if -1 != l_url.find('?'):
        l_url = l_url + f"&buster_{buster}"
    else:
        l_url = l_url + f"?buster_{buster}"
    return urllib.request.Request(
        l_url,
        data=None,
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
        }
    )


def process_ipdb(state: State, cfg: MySettings):
    outdated = False
    with sqlite3.connect(cfg.db) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS ip_db (start, end, country)")
        cursor = conn.cursor()
        cursor.execute("SELECT count(1) FROM ip_db")
        rows = cursor.fetchall()
        if rows[0][0] == 0:
            logger.info("No dbip data found")
            outdated = True
    now = datetime.datetime.now()
    if not outdated:
        if state.updated.year != now.year or state.updated.month != now.month:
            logger.info("dbip data outdated")
            outdated = True

    if not outdated:
        outdated = (now - state.updated) > datetime.timedelta(days=7)
    if outdated:
        logger.info("Updating dbip data")
        d = "{:%Y-%m}".format(datetime.datetime.now())
        url = f"https://download.db-ip.com/free/dbip-country-lite-{d}.csv.gz"
        with urllib.request.urlopen(get_request(url)) as f:
            nets = []
            g = gzip.GzipFile(fileobj=io.BytesIO(f.read()), mode='r')
            subnets = list(csv.reader(g.read().decode('utf-8').splitlines()))
            for subnet in subnets:
                nets.append({
                    "start": subnet[0],
                    "end": subnet[1],
                    "country": subnet[2]
                })
            with sqlite3.connect(cfg.db) as conn:
                conn.execute("DELETE from ip_db where True")
                conn.executemany("INSERT INTO ip_db VALUES (?, ?, ?)",
                                 [(n['start'], n['end'], n['country']) for n in nets])
                conn.commit()
                state.updated = now


@timeit
def loadConfig(cfg) -> List[MrRoute]:
    """
    Load the configuration from a database and populate the routes configuration.

    :return: None
    """

    n = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(MrRoute, r, cfg): r for r in cfg.routes}
    for f in concurrent.futures.as_completed(futures):
        if f.exception() is not None:
            logging.exception(f"Failed to load route {futures[f]}", exc_info=f.exception())
        else:
            n.append(f.result())
    return n


def apply_pbr():
    import jinja2, tempfile
    logging.debug(f"Applying PBR")
    subprocess.check_call(f'ip rule add fwmark 0x{CONFIG.pbr_mark} table {CONFIG.table}', shell=True)
    with open("templates/pbr.nft.j2") as f:
        t = jinja2.Template(f.read())
    for i in CONFIG.interfaces:
        logging.debug(f'PBR for {i}')
        ruleset = tempfile.mktemp(prefix=f"pbr_{i}", suffix=".nft")
        with open(ruleset, "w") as f:
            f.write(t.render(interface=i, mark=CONFIG.pbr_mark, table=CONFIG.table))
        logging.info(f'PBR ruleset {ruleset}')
        subprocess.check_call(f'nft -f {ruleset}', shell=True)


def remove_pbr():
    subprocess.check_call(f'ip rule del fwmark 0x{CONFIG.pbr_mark} table {CONFIG.table}', shell=True)
    for i in CONFIG.interfaces:
        subprocess.check_call(f'nft flush table ipt_server_pbr', shell=True)
        subprocess.check_call(f'nft delete table ipt_server_pbr', shell=True)


def main():
    global CONFIG, ROUTES
    CONFIG = MySettings.load("settings.yaml")
    st = State.load(CONFIG)
    process_ipdb(st, CONFIG)
    ROUTES = loadConfig(CONFIG)
    apply_pbr()
    logging.debug(f"Loading config")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(MrRoute.sync_subnets, ROUTES)

    asyncio.run(async_main())


def process_a_record(record):
    global ROUTES
    # todo: add ip route flush cache if route added
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for r in ROUTES:
            executor.submit(r.on_a_record, record)


async def echo(websocket):
    async for message in websocket:
        import json
        msg = json.loads(message)
        logging.debug(f"Got message {msg}")
        if msg['type'] == 1:
            process_a_record(msg)
        await websocket.send("OK")


async def async_main():
    async with websockets.serve(echo, "0.0.0.0", CONFIG.ws_port, ping_timeout=30, ping_interval=30):
        await asyncio.Future()  # run forever


if __name__ == '__main__':
    import os

    if srv := os.environ.get('PYDEV', False):
        try:
            import pydevd_pycharm

            pydevd_pycharm.settrace(srv.split(':')[0], port=int(srv.split(':')[1]), stdoutToServer=True,
                                    stderrToServer=True,
                                    suspend=False)
        except Exception as e:
            logging.exception("Failed to connect to pydevd", exc_info=e)
    main()
