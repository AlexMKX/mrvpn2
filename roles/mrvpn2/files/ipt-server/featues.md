### FEATURES

```markdown
# Key Features of ipt_server

This document explains the core mechanisms of `ipt_server`, focusing on the `weight` parameter, `domain_route_ttl`, and routing principles. These features enable flexible and dynamic traffic management.

## `weight` Parameter

**Type**: `Optional[int]`  
**Default**: `0`  
**Purpose**: The `weight` parameter determines the priority of a route when multiple routes overlap (e.g., subnets or domains). Higher values indicate higher priority.

### How It Works
- **Conflict Resolution**: When a new route is added (via `Router.add_route()`), the service checks for overlaps in the `IntervalTree`. If an existing route covers the same IP range or domain and has a higher `weight`, the new route is skipped.
- **Behavior**: 
  - Routes with higher `weight` take precedence, even if they are less specific (e.g., a larger subnet).
  - Equal `weight` values do not guarantee a specific outcome; the existing route may persist.

### Example
```yaml
routes:
  - net: '1.0.0.0/8'
    interface: docker0
    weight: 98
  - net: '1.1.0.0/16'
    interface: docker0
    weight: 97
```
- Traffic to `1.1.0.1` uses the `1.0.0.0/8` route because `weight: 98` > `weight: 97`, despite `1.1.0.0/16` being more specific.

### Notes
- `weight` is only relevant for overlapping routes. Non-overlapping routes are unaffected.
- Use `weight` to prioritize specific domains or subnets over broader rules.

## `domain_route_ttl` Parameter

**Type**: `int`  
**Default**: `300` (in `MySettings`)  
**Purpose**: `domain_route_ttl` sets the default time-to-live (TTL) in seconds for routes created from DNS A-records (domain-based routes) when no specific `route_ttl` is defined.

### How It Works
- **Route Creation**: When a WebSocket message (e.g., `{"query": "example.com", "content": "93.184.216.34"}`) triggers a route via `Router.on_a_record()`, the TTL is determined as follows:
  1. If the `domain` route specifies `route_ttl`, it takes precedence.
  2. Otherwise, `domain_route_ttl` is used.
  3. The final TTL is the minimum of `route_ttl`, `domain_route_ttl`, and the A-record's `ttl` (if provided).
- **Expiration**: Routes with expired TTL are removed by `Router._cleanup_expired_routes()` every 10 seconds, unless active `conntrack` entries exist (checked if `clean_conntrack: True`).
- **Updates**: If a route already exists, its TTL is refreshed to the maximum of its current TTL and the new value.

### Example
```yaml
routes:
  - domain: '.*\.ru'
    interface: _DEFAULT
  - domain: '.*\.chatgpt.com'
    interface: docker0
    route_ttl: 10
domain_route_ttl: 100
```
- `example.ru` route lasts 100 seconds (from `domain_route_ttl`).
- `chatgpt.com` route lasts 10 seconds (from `route_ttl`), or 5 seconds if the A-record has `ttl: 5`.

### WebSocket Example
Request:
```json
{"query": "chatgpt.com", "content": "20.236.44.162", "type": 1, "ttl": 8}
```
Response:
```json
{"ttl": 8}
```
- Route TTL is 8 seconds (minimum of `route_ttl: 10`, `domain_route_ttl: 100`, `record.ttl: 8`).

### Notes
- TTL ensures temporary routes (e.g., from DNS) don’t persist indefinitely.
- `clean_conntrack` affects whether expired routes with active connections are preserved.

## Routing Principles

### Route Management
- **Static Routes**: `country` and `net` routes are loaded at startup from `settings.yaml`.
- **Dynamic Routes**: `domain` routes are added in real-time via WebSocket A-records.
- **Storage**: Routes are stored in an `IntervalTree` for efficient overlap detection.

### Conflict Resolution
- Overlapping routes are resolved by comparing `weight`. Higher `weight` wins.
- Example: A `domain` route for `.*\.com` (`weight: 100`) is overridden by `.*\.google.com` (`weight: 200`) for Google domains.

### PBR Integration
- Traffic is filtered using `nftables` with a `fwmark` (e.g., `200`) and routed via a custom table (e.g., `200`).
- Interfaces like `wg-firezone` or `docker0` are specified in the config.

### Cleanup
- Expired routes are removed every 10 seconds, preserving active connections if `clean_conntrack: False`.

This combination of `weight`, TTL, and PBR enables precise and dynamic control over network traffic.
```

---

### Инструкции по использованию
1. Сохраните `README.md` как основной файл в корне проекта.
2. Сохраните `CONFIGURATION.md` и `FEATURES.md` в корне или в папке `docs/`, добавив ссылки в `README.md` (они уже включены).
3. Убедитесь, что Mermaid поддерживается в вашей системе отображения Markdown (например, GitHub его поддерживает).

Если нужно что-то доработать (добавить больше примеров, изменить стиль или структуру), дайте знать!