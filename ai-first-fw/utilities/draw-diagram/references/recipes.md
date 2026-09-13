# Recipes

Start line 1 directly with the diagram type identifier. Place diagram titles in Markdown headings directly above the code fence. Declare `classDef` lines from `palette.md` inside the diagram.

## flowchart

```mermaid
flowchart LR
    classDef core fill:#182449,stroke:#435db1,stroke-width:2px,color:#d6e1ff;
```

A cylinder `[(...)]` marks a store or broker. A rectangle marks every other component. Node labels state the component name and role. Edge labels state the verb and payload for that hop.

## sequenceDiagram

```mermaid
sequenceDiagram
    autonumber
```

Group participants by role inside `box rgb(...)` using the role sequence value from `palette.md`. Each message states the method or route. Use `->>+` to open an activation and `-->>-` to close it.

## stateDiagram-v2

```mermaid
stateDiagram-v2
```

Each transition states the event that triggers it. Terminal states reach `[*]`. Nested lifecycles use `state X { ... }`.

## erDiagram

```mermaid
erDiagram
```

Column types, `PK`, `FK`, and `UK` derive from database migrations or entity classes. Foreign key constraints and nullability define relationship cardinality.
