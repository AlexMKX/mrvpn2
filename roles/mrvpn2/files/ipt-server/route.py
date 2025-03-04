from typing import List, Dict, Tuple, Optional, Any
import ipaddress
from dataclasses import dataclass

import logging
from pyroute2 import IPRoute
import expiring_lru_cache
from datetime import datetime, timedelta
from functools import lru_cache

from pyroute2.netlink.rtnl.rtmsg import rtmsg


@dataclass
class RouteObject:
    net: ipaddress.IPv4Network
    family: int = 2  # AF_INET
    proto: int = 3  # RTPROT_BOOT
    type: int = 1  # RTN_UNICAST
    weight: int = 0
    metric: int = 0
    interface: Optional[str] = None
    ttl: Optional[int] = None
    net_start: int = 0
    net_end: int = 0
    expiration: Optional[datetime] = None

    @property
    def route_spec(self) -> Dict[str, Any]:
        spec = {
            'dst': str(self.net.network_address),
            'dst_len': self.net.prefixlen,
            'family': self.family,
            'proto': self.proto,
            'type': self.type,
            'oif': RouteObject.interfaces[self.interface][0][0],
            'priority': self.metric
        }
        if self.interface == '_DEFAULT':
            spec['gateway'] = RouteObject._default_gw_route_spec[0]['gateway']
        return spec

    @property
    def expired(self) -> bool:
        if self.expiration is None:
            return False
        return datetime.now() > self.expiration

    def __post_init__(self):
        if not isinstance(self.net, ipaddress.IPv4Network):
            self.net = ipaddress.IPv4Network(self.net, strict=False)
        self.net_start = int(self.net.network_address)
        self.net_end = int(self.net.broadcast_address)

    def reset_expiration(self, new_ttl: Optional[int] = None):
        if new_ttl is not None:
            if self.ttl is None:
                self.ttl = new_ttl
            else:
                self.ttl = max(self.ttl, new_ttl)
            self.expiration = datetime.now() + timedelta(seconds=self.ttl)
        elif self.ttl is not None:
            self.expiration = datetime.now() + timedelta(seconds=self.ttl)
        else:
            self.expiration = None

    @classmethod
    @property
    @lru_cache(maxsize=None)
    def _default_gw_route_spec(cls) -> List[Tuple[int, dict]]:
        route_specs = []
        for route in IPRoute().get_default_routes():
            attrs = dict(route['attrs'])
            oif = attrs.get('RTA_OIF')
            priority = attrs.get('RTA_PRIORITY', 0)
            gateway = attrs.get('RTA_GATEWAY')
            if oif is not None:
                route_specs.append({'oif': oif, 'metric': priority, 'gateway': gateway, })
        return route_specs

    @classmethod
    @property
    @lru_cache(maxsize=None)
    def interfaces(cls) -> Dict[str, int]:
        """
        Get a dictionary of interface names and their corresponding index numbers.
        :return:
        """
        rv = {}
        with IPRoute() as ipr:
            rv['_DEFAULT'] = [(RouteObject._default_gw_route_spec[0]['oif'],RouteObject._default_gw_route_spec[0]['metric'])]
            for link in ipr.get_links():
                rv[link.get_attr('IFLA_IFNAME')] = [(link['index'], None)]
            return rv
