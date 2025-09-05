from pydantic_settings import BaseSettings
from pydantic import PrivateAttr, ConfigDict, Field, field_validator, ValidationInfo
from typing import List, Union, Literal, Optional, Any, Dict
import ipaddress
import re
import yaml
from route import RouteObject


class BaseRoute(BaseSettings):
    interface: Optional[str] = None
    metric: Optional[int] = 200
    weight: Optional[int] = 0
    model_config = ConfigDict(extra='allow')
    route_ttl: Optional[int] = None
    _routes: List[RouteObject] = PrivateAttr(default_factory=list)

    def add_subnet(self, ip_net: Union[str, ipaddress.IPv4Network]) -> None:
        subnet = ipaddress.IPv4Network(ip_net, strict=False)

        route_spec = RouteObject(
            net=subnet,
            weight=self.weight,
            interface=self.interface,
            ttl=self.route_ttl,
            metric=self.metric,
        )

        self._routes.append(route_spec)

    @property
    def routes(self) -> List[RouteObject]:
        return self._routes

    def match(self, value: Any) -> bool:
        """
        Match the given value against this route's criteria.
        This method should be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement the match() method.")


class CountryRoute(BaseRoute):
    type: Literal["country"] = "country"
    country: str

    def model_post_init(self, __context: Any) -> None:
        from ip_database import IPDB
        for s in IPDB[self.country]:
            self.add_subnet(s)


class DomainRoute(BaseRoute):
    type: Literal["domain"] = "domain"
    domain: str
    _domain_re: Optional[re.Pattern] = None

    @property
    def domain_re(self) -> re.Pattern:
        """
        Returns a compiled regular expression for the domain pattern.
        """
        if self._domain_re is None:
            self._domain_re = re.compile(self.domain)
        return self._domain_re

    def match(self, value: Any) -> bool:
        """
        Returns True if the input (assumed to be a domain string)
        matches the compiled regular expression.
        """
        if isinstance(value, str):
            return bool(self.domain_re.match(value))
        return False

    def build_route(self, ip: Union[str, ipaddress.IPv4Address]) -> RouteObject:
        """
        Returns a RouteObject based on the DomainRoute's properties and the given IP address.
        """
        ip_network = ipaddress.IPv4Network(f"{ip}/32", strict=False)
        return RouteObject(
            net=ip_network,
            weight=self.weight,
            metric=self.metric,
            interface=self.interface,
            ttl=self.route_ttl
        )


class NetRoute(BaseRoute):
    type: Literal["net"] = "net"
    net: Union[str, ipaddress.IPv4Network]
    ttl: Optional[int] = None

    @field_validator("net", mode="before")
    def set_net(cls, v) -> ipaddress.IPv4Network:
        """
        Accepts a string and converts it into an IPv4Network object.
        """
        return ipaddress.IPv4Network(v)

    def model_post_init(self, __context: Any) -> None:
        self.add_subnet(self.net)

    def add_subnet(self, ip_net: Union[str, ipaddress.IPv4Network]) -> None:
        subnet = ipaddress.IPv4Network(ip_net, strict=False)

        route_spec = RouteObject(
            net=subnet,
            weight=self.weight,
            interface=self.interface,
            ttl=self.ttl,
            metric=self.metric,
        )

        self._routes.append(route_spec)


class MySettings(BaseSettings):
    table: int = Field(200)
    ws_port: int = Field(8765)
    db: str = Field('ipt.db')
    pbr_mark: int = Field(512)
    interfaces: List[str] = Field(['wg-firezone'])
    clean_conntrack: bool = Field(False)
    # state_file: str = Field('/tmp/state.pkl')
    domain_route_ttl: int = 300  # Default TTL for domain routes in seconds
    # The routes field is declared as a list of unions of the three route types.
    routes: List[Union[CountryRoute, DomainRoute, NetRoute]]

    @field_validator("routes", mode="before")
    def parse_routes(cls, v: list, model_values: ValidationInfo) -> list:
        """
        Accepts the entire list of routes from YAML, inspects each route dictionary,
        injects the appropriate 'type' field, and returns a list of proper route instances.
        """
        if not isinstance(v, list):
            raise ValueError("routes must be a list")

        route_classes = {
            "country": CountryRoute,
            "domain": DomainRoute,
            "net": NetRoute
        }

        new_routes = []
        for item in v:
            if not isinstance(item, dict):
                new_routes.append(item)
                continue

            base_route = {k: v for k, v in item.items() if k not in route_classes.keys()}
            route_type = next((k for k in route_classes.keys() if k in item), None)

            if not route_type:
                raise ValueError("Invalid route configuration: no valid key found")

            values = item[route_type]
            values = [values] if not isinstance(values, list) else values

            for value in values:
                new_route = base_route.copy()
                new_route["type"] = route_type
                new_route[route_type] = value

                # Set default domain_route_ttl for domain routes if not specified
                if route_type == "domain" and "route_ttl" not in new_route:
                    new_route["route_ttl"] = model_values.data["domain_route_ttl"]

                new_routes.append(route_classes[route_type](**new_route))
        return new_routes

    @classmethod
    def load(cls, filename_or_b64: str):
        with open(filename_or_b64, 'r') as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
        return cls(**config)
