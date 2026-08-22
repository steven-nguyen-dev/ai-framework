# Mapping Plan Review Rules

When a `mapping-plan.md` exists, apply these checks during **Pass 1 — Evidence**:

- **Silent-failure mappings justified**: Where a mapping would fail silently (wrong key/identifier, SKU, money, state), the row carries all four justifications — target business purpose (the *Reason* column), contract placement role, near-miss field (or `none`), and the stated business consequence if wrong. Any one of the four blank is a finding.
- **Contract placement role & provenance**: The source field's assignment (channel vs seller) and contract location (request input vs response payload) must be evaluated.
- **Near-misses defined**: Every row names a near-miss with a distinguishing property, or `none`.
- **Business consequence**: The stated business consequence must be true and domain-focused, not purely technical.
- **Value set closed**: Every value set names what closed it (schema, enum, partner doc) in the row's *Value set / cardinality* column. Closed by a sample payload is a finding.
- **Fallbacks explicit**: No fallback is blank or a language default standing in for a decision (`0`, `false`, `""`).
- **Cardinality resolved**: Cardinality mismatches must carry a rule in the *Value set / cardinality* column or a `GAP-xx`.
- **Null and absent**: Null and absent conditions must be answered separately.
- **§2 and §3 populated**: A target with no source or a dropped inbound field must be explicitly documented; silence is a finding.
