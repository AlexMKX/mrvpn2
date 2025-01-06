from pydantic_settings import BaseSettings
from pydantic import PrivateAttr
from typing import List, Any
from pydantic import Field, field_validator
import ipaddress, re, yaml
import datetime

import urllib.request, random

ALL_METRICS = set()

import pickle, gzip, io, csv, sqlite3


class MySettings(BaseSettings):
    table: int = Field(200)
    ws_port: int = Field(8765)
    db: str = Field('ipt.db')
    pbr_mark: int = Field(200)
    interfaces: List[str] = Field(['wg-firezone'])
    state_file: str = Field('/tmp/state.pkl')

    class Route(BaseSettings):
        interface: str = Field()
        geo: List[str] = Field([])
        domains: List[str] = Field([])
        metric: int = Field(-1)
        default: bool = Field(True)
        _domains_re: [re] = None
        static: List[ipaddress.IPv4Network] = Field([])

        @property
        def domains_re(self) -> [re]:
            """
                Retrieve the compiled regular expression patterns for the domains.

                :return: a list of compiled regular expression patterns for the domains.
                :rtype: list[re]
            """
            if self._domains_re is None:
                self._domains_re = [re.compile(n) for n in self.domains]
            return self._domains_re

        @field_validator("static")
        def set_static(cls, v: List[str]) -> List[ipaddress.IPv4Network]:
            """
            Set the static subnets.

            :param v: A list of strings representing the subnets to set.
            :type v: List[str]
            :return: A list of ipv4 subnets.
            :rtype: List[ipaddress.IPv4Network]
            """
            return [ipaddress.IPv4Network(n) for n in v]

        @field_validator("metric")
        def set_metric(cls, v: int) -> int:
            """
            Set the domains for the given field validator.

            :param v: A list of strings representing the domains to set.
            :type v: List[str]
            :return: A list of compiled regular expression patterns based on the given domains.
            :rtype: List[re.Pattern]
            """
            global ALL_METRICS
            if v == -1:
                m = max(ALL_METRICS) + 1
                ALL_METRICS.add(m)
                return m
            if v in ALL_METRICS:
                raise ValueError(f"Metric {v} already in use")
            ALL_METRICS.add(v)
            return v

    routes: List[Route]

    @classmethod
    def load(cls, filename_or_b64: str):
        config = yaml.load(open(filename_or_b64, 'r'), Loader=yaml.FullLoader)
        return cls(**config)


class State(BaseSettings):
    updated: datetime.datetime = Field(datetime.datetime(1970, 1, 1))
    _cfg: MySettings = PrivateAttr()

    def __init__(self, **kwargs):
        t_cfg = kwargs['cfg']
        kwargs.pop('cfg')
        super().__init__(**kwargs)
        self._cfg = t_cfg

    def __setattr__(self, key, val):
        super().__setattr__(key, val)
        self.save()

    @classmethod
    def load(cls, cfg: MySettings):
        try:
            d = pickle.load(open(cfg.state_file, 'rb'))
            st = cls(cfg=cfg, **d)
        except Exception as e:
            st = cls(cfg=cfg)
        return st

    def save(self):
        with open(self._cfg.state_file, 'wb') as f:
            pickle.dump(self.model_dump(), f)
