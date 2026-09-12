# Cache semantics

`ttlMs=0` is not retained. A positive TTL is recorded with a monotonic expiry. For a paginated list, the shortest page TTL governs the assembled catalog. A public entry is reusable only with equal source identity and an explicit `public` hint. Private entries are keyed by the caller-supplied principal (or a source instance fallback), so URL-only sharing cannot leak a catalog between security contexts. `refresh()` bypasses reads; source invalidation is available through `CatalogCache.invalidate()`.

