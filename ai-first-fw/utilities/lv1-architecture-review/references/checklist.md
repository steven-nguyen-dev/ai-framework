# Backend Architecture Review Checklist

51 checks. **1–5** are the AWS Well-Architected pillars. **6** is an addition — maintainability is
not a WAF pillar, but it is what a code review sees. **7** is stack-specific: each block is either
applicable or `n/a`.

Severity tags: `critical` = outage, breach or data loss; flag regardless of context ·
`important` = worth a conversation; it costs the team later · `good` = quality signal, absence is
not a defect.

A check tagged `+team` **splits**: the repo settles one clause and cannot settle another. It takes a
status on the clause the code answers and sends the other to **Ask the team** — one status and one
question, both recorded. Tag a new check `+team` when writing it, not when grading it.

**Every check is phrased so a tick means healthy** — if you cannot tick it, you have a finding.

---

## 1. Operational Excellence — `OPS`

> Can you ship it, see it, and fix it at 3am?

- [ ] **OPS-1** Deployment is automated end to end, and rollback is a path someone has actually used — not a theory? `critical` `+team`
- [ ] **OPS-2** Config is externalised per environment — one artifact promoted, no rebuild to change a setting? `important`
- [ ] **OPS-3** Logs are structured, one request can be reconstructed across every service and queue it touched, and security-relevant actions are attributable to a principal? `important` `+team`
- [ ] **OPS-4** Every endpoint has latency (p95/p99), error rate, throughput and saturation — as numbers someone actually looks at, not just exported? `important` `+team`
- [ ] **OPS-5** Alerts fire on symptoms users feel, and each one points at a runbook naming the first action? `important` `+team`

## 2. Security — `SEC`

> Deny by default, at every layer.

- [ ] **SEC-1** Authentication is deny-by-default — a newly added endpoint is protected unless someone explicitly opens it? `critical`
- [ ] **SEC-2** Authorisation is checked on the **object**, not just the route — a user cannot reach someone else's record by changing an ID in the request? `critical`
- [ ] **SEC-3** Untrusted input is validated at the boundary, and every query is parameterised? `critical`
- [ ] **SEC-4** Secrets live in a manager — absent from source, images, config files and logs — and rotate without a code change? `critical` `+team`
- [ ] **SEC-5** TLS in transit, encryption at rest for sensitive data, and no PII in logs or error bodies? `critical` `+team`
- [ ] **SEC-6** Least privilege per component, and dependencies and base images are scanned in CI with a named owner for the findings? `important` `+team`

## 3. Reliability — `REL`

> Does it survive its dependencies failing?

- [ ] **REL-1** Every outbound call has an explicit connect **and** read timeout, and retries are bounded, jittered, and attempted only on retryable failures? `critical`
- [ ] **REL-2** Write paths are idempotent — a client retry cannot double-charge, double-create or double-ship? `critical`
- [ ] **REL-3** Concurrent updates are safe — optimistic version, atomic operation or explicit lock, not read-modify-write? `critical`
- [ ] **REL-4** More than one instance actually runs across failure domains, the service is stateless enough for that to hold, and no dependency is a singleton — one DB primary with no failover, one cache node, one broker? `critical` `+team`
- [ ] **REL-5** Scheduled and background jobs are single-flight across instances — leader election or a distributed lock, not one timer firing per replica? `critical`
- [ ] **REL-6** A slow dependency is contained — circuit breaker or bulkhead, with defined behaviour when it trips — and inbound load is bounded by rate limiting and a capped request body, so overload sheds rather than collapses? `important`
- [ ] **REL-7** Liveness and readiness are distinct, and liveness does **not** depend on a downstream system? `important`
- [ ] **REL-8** The consistency model is explicit per flow — strong or eventual — and the API does not promise more than it delivers? `important`
- [ ] **REL-9** A restore from backup has actually been performed, and RTO/RPO are written down? `important` `+team`

## 4. Performance Efficiency — `PERF`

> Measured, not assumed.

- [ ] **PERF-1** Hot-path queries are index-backed, confirmed by an execution plan rather than by assumption? `critical` `+team`
- [ ] **PERF-2** A list endpoint issues a bounded number of queries regardless of result size — no N+1? `important`
- [ ] **PERF-3** Pagination is enforced **and capped** on every list and search endpoint? `important`
- [ ] **PERF-4** Work that need not block the response is off the request path? `important`

## 5. Cost & Efficiency — `COST`

> Does the bill track the work done? *(absorbs the Sustainability pillar — same levers, same evidence)*

- [ ] **COST-1** Cost scales linearly or better with load — doubling traffic does not more than double the bill? `important`
- [ ] **COST-2** Expensive external calls are cached, batched or debounced, and responses return only what the client needs? `important`
- [ ] **COST-3** Data has a lifecycle — logs, old rows and objects tiered, archived or purged on a schedule; compute right-sized against observed use, not defaults? `good` `+team`

## 6. Maintainability & Testability — `MNT`

> Can the team change it confidently in six months?

- [ ] **MNT-1** Errors are handled explicitly — no swallowed exceptions, no generic 500 hiding a known failure mode? `important`
- [ ] **MNT-2** Tests assert behaviour and cover failure paths, and a meaningful change breaks at least one of them? `important`
- [ ] **MNT-3** One concern lives in one place, layers follow one consistent pattern, and dependencies are injected? `important`
- [ ] **MNT-4** Public contracts — API, event payloads, DB schema — are versioned with a stated compatibility rule and a migration path? `important`
- [ ] **MNT-5** Domain concepts are named as the business names them? `good`

---

## 7. Stack-Specific

> Each block is applicable or `n/a`.

### 7a. Spring Boot service — `SB`

- [ ] **SB-1** Client and pool bounds are explicit — Boot ships **no** default HTTP connect/read timeout (`spring.http.clients.*` in 4.x, `spring.http.client.*` in 3.4–3.5), and the DB pool is sized against database capacity × instance count with an acquisition timeout shorter than the request timeout? `critical` `+team`
- [ ] **SB-2** Schema changes go through Flyway/Liquibase with `ddl-auto=none`, forward-only, and each migration is compatible with the version still running during rollout? `critical`
- [ ] **SB-3** `@Transactional` spans one unit of work — no HTTP or queue call inside it, `readOnly` on reads, and no self-invocation (proxies do not intercept it)? `important`
- [ ] **SB-4** `spring.jpa.open-in-view=false` — it still defaults to `true` (Boot 4.x, Aug 2026), holding a DB connection for the whole request and hiding N+1 — and the lazy loading it was covering is fixed with fetch joins or `@EntityGraph`? `important`
- [ ] **SB-5** Graceful shutdown is on with a pod termination grace period longer than the drain timeout? `important`
- [ ] **SB-6** Trace sampling is a deliberate choice, not the inherited default — `management.tracing.sampling.probability` is `0.1`, 10% of requests, unless set (Boot 4.1 docs, Aug 2026)? `important`

### 7b. Asynchronous messaging — `MQ`

- [ ] **MQ-1** No dual write — the event and the state change commit together via a transactional outbox or CDC, never "save to DB, then publish"? `critical`
- [ ] **MQ-2** Consumers are idempotent on a **producer-supplied**, retry-stable key, deduplicated in the same transaction as the effect — no broker gives exactly-once across an external system, so assume redelivery? `critical`
- [ ] **MQ-3** Every queue/topic has a DLQ, a bounded attempt count and a replay path? `important` `+team`
  *Ask the team what their broker does without one: redelivered until retention expires, or discarded after N attempts.*
- [ ] **MQ-4** Ordering requirements are explicit and keyed on the aggregate ID — guarantees are per partition, message group or queue, never per topic, and standard SQS gives none — and no downstream fan-out discards them? `important` `+team`
- [ ] **MQ-5** Consumer lag (or age of oldest message) and DLQ depth are alarmed — a small stuck queue is worse than a large moving one? `important`

### 7c. Distributed cache — `CACHE`

- [ ] **CACHE-1** The system still serves correct results with the cache cold or down, and that has been load-tested rather than assumed? `critical` `+team`
- [ ] **CACHE-2** Writes update the store **first**, then invalidate — and every key has a TTL as the backstop that turns a missed invalidation into bounded staleness? `critical`
- [ ] **CACHE-3** Stampede is handled — TTL jitter plus single-flight/coalescing — so an expiry, a deploy or a cold node does not hit the origin N times at once? `important`
- [ ] **CACHE-4** A memory ceiling and eviction policy are set deliberately, and every value is safe to evict at any moment — anything that is not is a datastore, not a cache? `important` `+team`

### 7d. Multi-tenant SaaS — `TEN`

- [ ] **TEN-1** Tenant context is derived from the authenticated principal — never from a client-supplied header, path or body field? `critical`
- [ ] **TEN-2** Tenant scoping is enforced below the application layer — row-level security, a schema boundary, or a repository that cannot be bypassed — so a hand-written query cannot omit the predicate? `critical`
- [ ] **TEN-3** Every cache key, message and background job carries the tenant, and tenant context is restored on async, consumer and scheduled threads? `critical`
- [ ] **TEN-4** Per-tenant quotas or rate limits stop one tenant consuming the shared pool, and per-tenant usage is measurable in logs and traces (tenant as a metric tag is a cardinality bomb)? `important`
