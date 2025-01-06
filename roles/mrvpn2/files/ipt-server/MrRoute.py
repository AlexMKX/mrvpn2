import logging

from Config import MySettings
from typing import Dict, Set, Any, List
import ipaddress
import concurrent.futures
from pyroute2 import IPRoute
from pyroute2.netlink.rtnl.rtmsg import rtmsg
import sqlite3


from lib import *


class MrRoute:
    # subnets: Set[ipaddress.IPv4Network]
    # __cfg: MySettings.Route
    # __iface_num: int
    # __app_cfg: MySettings
    # __route_spec: List[Dict[str, Any]]

    @staticmethod
    def _address_gen(r):
        start = r[0]
        end = r[1]
        if is_ipv4(start) and is_ipv4(end):
            r = ipaddress.summarize_address_range(ipaddress.IPv4Address(start),
                                                  ipaddress.IPv4Address(end))
            return list(r)
        else:
            return []

    def _build_route_spec(self):
        if self._cfg.interface == '_DEFAULT':
            ip = IPRoute()
            try:
                r = ip.get_default_routes()
                rrs = [{rtmsg.nla2name(k): v for k, v in route['attrs']} for route in r]
            finally:
                ip.close()
            for route_details in rrs:
                route_details['table'] = self._app_cfg.table
                route_details['priority'] = route_details.get('priority', 0) + self._cfg.metric
                self._route_spec.append(route_details)
        else:
            self._route_spec = [
                {"oif": self._iface_num, "table": self._app_cfg.table, "priority": self._cfg.metric}]

    @timeit
    def __init__(self, route_config: MySettings.Route, app_config: MySettings):
        from itertools import chain
        ipr = IPRoute()

        self.subnets = set()
        self._cfg = route_config
        self._app_cfg = app_config
        self._route_spec = []
        try:
            if self._cfg.interface != '_DEFAULT':
                lookup_res = ipr.link_lookup(ifname=self._cfg.interface)
                if len(lookup_res) == 1:
                    dev = lookup_res[0]
                elif len(lookup_res) > 1:
                    raise ValueError(f"Interface {self._cfg.interface} is ambiguous")
                else:
                    raise ValueError(f"Interface {self._cfg.interface} not found")
            else:
                dev = -1
        finally:
            ipr.close()
        self._iface_num = dev
        self._build_route_spec()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            with sqlite3.connect(self._app_cfg.db) as conn:
                for s in self._cfg.geo:
                    r = conn.execute(f"SELECT start,end FROM ip_db WHERE {s}")
                    nets = executor.map(self._address_gen, r)
                    self.subnets = set(ipaddress.collapse_addresses(list(chain(*nets))))
        self.subnets.update(set(self._cfg.static))
        self.subnets = set(ipaddress.collapse_addresses(self.subnets))

    def __repr__(self):
        return f"MrRoute({self._cfg.interface}, {self._cfg.metric}, {self._cfg.geo}, {self._cfg.static})"

    def _is_mine(self, rs) -> bool:
        t = rs.copy()
        if 'dst' in t.keys():
            t.pop('dst')
        if 'dst_len' in t.keys():
            t.pop('dst_len')
        return t in self._route_spec

    @staticmethod
    def _route_cmd(cmd, rspec):
        ipr = IPRoute()
        try:
            ipr.route(cmd, **rspec)
        finally:
            ipr.close()

    from collections.abc import Iterable

    def _build_route_set(self, dst_set: Iterable[ipaddress.IPv4Network]) -> Iterable[Dict[str, Any]]:
        for r in dst_set:
            rs = self._route_spec.copy()
            for rrs in rs:
                rrs['dst'] = str(r.network_address)
                rrs['dst_len'] = r.prefixlen
                yield rrs.copy()

    @timeit
    def sync_subnets(self):
        ipr = IPRoute()
        parsed_routes = []
        for r in ipr.get_routes(table=self._app_cfg.table):
            rt = {rtmsg.nla2name(k): v for k, v in r['attrs']}
            rt['dst_len'] = r['dst_len']
            if rt['dst_len'] == 0:
                rt['dst'] = '0.0.0.0'
            parsed_routes.append(rt)

        active_route_set = [x for x in parsed_routes if self._is_mine(x)]

        new_routes = self.subnets
        new_dset = ipaddress.collapse_addresses(new_routes)
        new_route_set = list(self._build_route_set(new_dset))
        route_cmd_set = []
        route_cmd_set.extend([('add', x) for x in new_route_set if x not in active_route_set])
        route_cmd_set.extend([('del', x) for x in active_route_set if x not in new_route_set])
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(MrRoute._route_cmd, r[0], r[1]): r for r in route_cmd_set}
        for f in concurrent.futures.as_completed(futures):
            if f.exception() is not None:
                logging.exception(f"Failed to load route {futures[f]}", exc_info=f.exception())

    def on_a_record(self, record):
        import pyroute2.netlink.exceptions
        for d in self._cfg.domains_re:
            if d.match(record['name'].rstrip('.')) or d.match(record['query'].rstrip('.')):
                for r in self._build_route_set({ipaddress.IPv4Network(record['content'])}):
                    try:
                        self._route_cmd('add', r)
                    except pyroute2.netlink.exceptions.NetlinkError as e:
                        logging.exception(f"{e}")
                        pass
                    except Exception as e:
                        logging.exception(f"Failed to add route {r}", exc_info=e)
                break
