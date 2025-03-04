import logging
import duckdb
import urllib.request
import datetime
import ipaddress
import tempfile
import os

from typing import List, Optional, Union, Iterator
import random
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class IPDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self.process_ipdb()

    @staticmethod
    def get_request(l_url: str) -> urllib.request.Request:
        buster = random.randint(1, 1000000)
        url_suffix = f"&buster_{buster}" if '?' in l_url else f"?buster_{buster}"
        return urllib.request.Request(
            l_url + url_suffix,
            data=None,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
            }
        )

    @contextmanager
    def _connection(self):
        conn = duckdb.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_table(self):
        # Load the inet extension for IP address support
        with self._connection() as conn:
            conn.execute("""
                         CREATE TABLE IF NOT EXISTS ip_db
                         (
                             start_ip
                             VARCHAR,
                             end_ip
                             VARCHAR,
                             country
                             VARCHAR,
                             last_updated
                             TIMESTAMP
                         )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_country ON ip_db(country)")

    def process_ipdb(self):
        current_timestamp = int(datetime.datetime.now().timestamp())
        outdated = True
        self._ensure_table()
        with self._connection() as conn:
            try:
                data_lag = conn.query(
                    "select extract(epoch from (current_localtimestamp() - max(last_updated))) from ip_db").fetchone()[
                    0]
                if data_lag is not None and data_lag <= 604800:  # 7 days in seconds
                    outdated = False
                else:
                    logger.info("dbip data outdated or not found")
            except duckdb.Error as e:
                logger.error(f"Database error: {e}")
                outdated = True

            if outdated:
                logger.info("Updating dbip data")
                try:
                    d = datetime.datetime.now().strftime("%Y-%m")
                    url = f"https://download.db-ip.com/free/dbip-country-lite-{d}.csv.gz"
                    with urllib.request.urlopen(self.get_request(url)) as f:
                        # Create a temporary file for bulk loading
                        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.csv.gz') as temp_file:
                            temp_file.write(f.read())
                            temp_file_name = temp_file.name
                        # Use COPY for bulk loading
                        with conn:
                            conn.execute("DROP TABLE IF EXISTS ip_db")
                            self._ensure_table()
                            conn.execute(f"""
                                                            COPY ip_db (start_ip, end_ip, country) FROM '{temp_file_name}' 
                                                            (FORMAT CSV, HEADER FALSE, COMPRESSION 'gzip')
                                                        """)
                            conn.execute("update ip_db set last_updated = current_localtimestamp()")
                            logger.info("dbip data updated successfully")

                        # Clean up temporary file
                        os.unlink(temp_file_name)

                except Exception as e:
                    logger.error(f"Error updating dbip data: {e}")
                    # Clean up temp file in case of error
                    if 'temp_file_name' in locals():
                        try:
                            os.unlink(temp_file_name)
                        except:
                            pass
                    raise

    def __getitem__(self, countries: Union[str, List[str]]) -> Iterator[ipaddress.IPv4Network]:
        return self.country_nets(countries)

    def country_nets(self, countries: Union[str, List[str]]) -> Iterator[ipaddress.IPv4Network]:
        if not isinstance(countries, (str, list)):
            raise ValueError("countries must be string or list of strings")

        countries = [countries] if isinstance(countries, str) else countries

        with self._connection() as conn:
            try:
                placeholders = ','.join([f"'{country}'" for country in countries])
                if len(countries) > 100:  # Reasonable limit
                    raise ValueError("Too many countries specified")

                query = f"""
                    SELECT start_ip, end_ip 
                    FROM ip_db 
                    WHERE country IN ({placeholders})
                """
                cursor = conn.execute(query)
                while rows := cursor.fetchmany(1000):
                    # if not rows:
                    #     break
                    for start_ip, end_ip in rows:
                        try:
                            start_ip_obj = ipaddress.ip_address(start_ip)
                            end_ip_obj = ipaddress.ip_address(end_ip)
                            if (isinstance(start_ip_obj, ipaddress.IPv4Address) and
                                    isinstance(end_ip_obj, ipaddress.IPv4Address)):
                                for network in ipaddress.summarize_address_range(start_ip_obj, end_ip_obj):
                                    yield network
                        except ValueError:
                            logger.warning(f"Invalid IP address range: {start_ip} - {end_ip}")
                            continue
            except duckdb.Error as e:
                logger.error(f"Database error when fetching country nets: {e}")
                raise


IPDB = IPDatabase('/tmp/ip_db.duckdb')
