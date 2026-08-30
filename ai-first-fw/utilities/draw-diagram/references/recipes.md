# Recipes

Open every block with its type's init header verbatim, then a `title:` block, then the `classDef`
lines from `palette.md` for the roles in use.

## flowchart

```
%%{init: {'theme':'base','themeVariables':{'primaryTextColor':'#b0b4ba','lineColor':'#5a6169','edgeLabelBackground':'#0d0d0d','titleColor':'#b0b4ba'}}}%%
```

Cylinder `[(...)]` marks a store or a broker; a rectangle marks everything else. A node label carries
its name then its role in parentheses. An edge label carries the verb and the payload the subject
names for that hop.

## sequenceDiagram

```
%%{init: {'theme':'base','themeVariables':{'textColor':'#b0b4ba','actorBkg':'#272a2d','actorTextColor':'#edeef0','actorBorder':'#5a6169','signalColor':'#5a6169','signalTextColor':'#edeef0','noteBkgColor':'#272a2d','noteTextColor':'#edeef0','noteBorderColor':'#5a6169','sequenceNumberColor':'#edeef0'}}}%%
```

Take `autonumber`. Group participants of one role inside a `box rgb(...)` carrying that role's
sequence value from `palette.md`. Each message carries the method or route the subject states.
`->>+` opens an activation and `-->>-` closes it, so every call shows its return.

## stateDiagram-v2

```
%%{init: {'theme':'base','themeVariables':{'textColor':'#b0b4ba','labelColor':'#edeef0','titleColor':'#b0b4ba'}}}%%
```

Every transition carries the event that fires it. Every terminal state reaches `[*]`. A lifecycle
inside a lifecycle nests as `state X { ... }`.

## erDiagram

```
%%{init: {'theme':'base','themeVariables':{'textColor':'#b0b4ba','attributeColorOdd':'#1c1c1c','attributeColorEven':'#272a2d','titleColor':'#b0b4ba'}}}%%
```

Column types, `PK`, `FK` and `UK` come from the migration or the entity class the subject holds.
Cardinality comes from the foreign key and its nullability, not from the relationship's name.
