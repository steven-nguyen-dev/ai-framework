# Palette

Seven roles. Colour encodes what a thing **is**, so two things of one kind share one colour.

| Role | Carries | Fill | Border | Text | Sequence `box rgb(...)` |
|---|---|---|---|---|---|
| `core` | Core or primary application | `#182449` | `#435db1` | `#d6e1ff` | `24,36,73` |
| `gateway` | API, gateway, connector, ingress | `#082c36` | `#11809c` | `#b6ecf7` | `8,44,54` |
| `bus` | Message bus, queue, event broker | `#212225` | `#5a6169` | `#edeef0` | `33,34,37` |
| `service` | Service, worker, processing engine | `#302008` | `#8f6424` | `#ffe7b3` | `48,32,8` |
| `external` | External system, third-party partner | `#381525` | `#b0436e` | `#fdd3e8` | `56,21,37` |
| `storage` | Database, storage, cache | `#162720` | `#2d6a4f` | `#d8f3dc` | `22,39,32` |
| `utility` | Internal step, helper | `#1c1c1c` | `#484848` | `#b4b4b4` | `28,28,28` |

Reading left to right or top to bottom, the hues run `gateway` → `core` → `bus` → `service` →
`external`, so the layout's direction and the colour's direction agree.

Declare the roles the block uses, and only those:

```
classDef core fill:#182449,stroke:#435db1,stroke-width:2px,color:#d6e1ff;
classDef gateway fill:#082c36,stroke:#11809c,stroke-width:2px,color:#b6ecf7;
classDef bus fill:#212225,stroke:#5a6169,stroke-width:2px,color:#edeef0;
classDef service fill:#302008,stroke:#8f6424,stroke-width:2px,color:#ffe7b3;
classDef external fill:#381525,stroke:#b0436e,stroke-width:2px,color:#fdd3e8;
classDef storage fill:#162720,stroke:#2d6a4f,stroke-width:2px,color:#d8f3dc;
classDef utility fill:#1c1c1c,stroke:#484848,stroke-width:2px,color:#b4b4b4;
```
