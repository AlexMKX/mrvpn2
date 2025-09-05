# Configuration Guide for ipt_server

The `ipt_server` service is configured via a YAML file (default: `settings.yaml`), parsed using the Pydantic `MySettings` model. This file defines routing rules, interfaces, and service settings. Below is a detailed breakdown of the configuration structure.

## Configuration Structure

```yaml
routes:
  - country: <country code or list of codes>
    interface: <interface name>
    weight: <route weight>
    metric: <route metric>
    route_ttl: <time to live in seconds>
  - domain: <regex pattern or list of patterns>
    interface: <interface name>
    weight: <route weight>
    metric: <route metric>
    route_ttl: <time to live in seconds>
  - net: <CIDR subnet or list of subnets>
    interface: <interface name>
    weight: <route weight>
    metric: <route metric>
    route_ttl: <time to live in seconds>
interfaces:
  - <interface name>
pbr_mark: <PBR mark value>
table: <routing table number>
domain_route_ttl: <default TTL for domain routes>
ws_port: <WebSocket port>
db: <path to IP database>
clean_conntrack: <true/false>
```

## Example Configuration

```yaml
routes:
  - country: ['AM']
    interface: _DEFAULT
    weight: 100
  - domain: '.*\.ru'
    interface: _DEFAULT
    metric: 100
  - net: ['0.0.0.0/0']
    interface: docker0
    weight: 99
  - domain: ['.*\.chatgpt.com', 'chatgpt.com']
    interface: docker0
    weight: 500
    route_ttl: 10
interfaces:
  - wg-firezone
  - wg-firezone_1
pbr_mark: 200
table: 200
domain_route_ttl: 100
```

## Field Descriptions

### Top-Level Fields

| Field             | Type            | Description                                                                                  | Default           | Example                     |
|-------------------|-----------------|----------------------------------------------------------------------------------------------|-------------------|-----------------------------|
| `routes`          | `List[Union[CountryRoute, DomainRoute, NetRoute]]` | List of routing rules. Required.                                    | N/A               | See below                   |
| `interfaces`      | `List[str]`     | List of network interfaces available for routing.                                            | `['wg-firezone']` | `['wg-firezone', 'eth0']`   |
| `pbr_mark`        | `int`           | Firewall mark for PBR (used with NFTables).                                                  | `512`             | `200`                       |
| `table`           | `int`           | Routing table number in the Linux kernel.                                                    | `200`             | `200`                       |
| `domain_route_ttl`| `int`           | Default TTL (in seconds) for domain-based routes if not specified.                           | `300`             | `100`                       |
| `ws_port`         | `int`           | WebSocket server port for DNS A-record updates.                                              | `8765`            | `8080`                      |
| `db`              | `str`           | Path to the IP database (used for country routes).                                           | `'ipt.db'`        | `'/tmp/ip_db.duckdb'`       |
| `clean_conntrack` | `bool`          | Enable/disable cleanup of expired `conntrack` entries when removing routes.                  | `False`           | `True`                      |

### Common Route Fields (`BaseRoute`)

| Field       | Type            | Description                                                                                  | Default | Example              |
|-------------|-----------------|----------------------------------------------------------------------------------------------|---------|----------------------|
| `interface` | `str`           | Network interface for routing. Use `_DEFAULT` for the default gateway.                       | N/A     | `docker0`, `_DEFAULT`|
| `weight`    | `Optional[int]` | Priority weight for route selection (higher = more preferred).                               | `0`     | `100`                |
| `metric`    | `Optional[int]` | Route metric (priority in the routing table).                                                | `200`   | `100`                |
| `route_ttl` | `Optional[int]` | Time to live (in seconds) for the route. Overrides `domain_route_ttl` for domain routes.     | `None`  | `10`                 |

### `country` Route (`CountryRoute`)

| Field     | Type                  | Description                                                                                  | Default | Example            |
|-----------|-----------------------|----------------------------------------------------------------------------------------------|---------|--------------------|
| `country` | `Union[str, List[str]]` | ISO 3166-1 alpha-2 country code(s). Subnets are fetched from `IPDatabase`.                  | N/A     | `'AM'`, `['AM', 'RU']` |

### `domain` Route (`DomainRoute`)

| Field    | Type                  | Description                                                                                  | Default | Example                      |
|----------|-----------------------|----------------------------------------------------------------------------------------------|---------|------------------------------|
| `domain` | `Union[str, List[str]]` | Regular expression(s) to match domains for dynamic routing via DNS A-records.              | N/A     | `'.*\.ru'`, `['.*\.x', '.*\.a']` |

### `net` Route (`NetRoute`)

| Field | Type                  | Description                                                                                  | Default | Example                   |
|-------|-----------------------|----------------------------------------------------------------------------------------------|---------|---------------------------|
| `net` | `Union[str, List[str]]` | CIDR subnet(s) or single IP (e.g., `/32`). Static routes applied at startup.               | N/A     | `'1.0.0.0/8'`, `['0.0.0.0/0']` |

## Additional Examples

1. **Mixed Routes**:
   ```yaml
   routes:
     - country: 'RU'
       interface: wg-firezone
       weight: 200
     - domain: '.*\.google\.com'
       interface: eth0
       weight: 300
       route_ttl: 60
     - net: '192.168.1.0/24'
       interface: docker0
       metric: 50
   interfaces:
     - wg-firezone
     - eth0
     - docker0
   ```

For more on `weight`, `route_ttl`, and routing behavior, see [FEATURES.md](FEATURES.md).
