---
name: lv1-diagram-maker
description: Professional styling conventions and aesthetic muted-dark color system for creating, editing, styling, and reviewing Mermaid diagrams of all types (flowcharts, sequence diagrams, architecture topology, state machines, ER diagrams). Apply this skill whenever asked to draw, design, generate, or review Mermaid diagrams.
version: 0.1.0
---

# Mermaid Diagram Maker & Universal Styling Guide

Professional, publication-grade styling conventions for **all types of Mermaid diagrams** (flowcharts, sequence diagrams, architecture topologies, state machines, and entity-relationship models).

---

## 🎨 Core Design Principles

1. **Muted Dark Fills, Border Carries the Hue**:
   - Large node areas use deep, low-chroma background fills (step 3 of a 12-step scale).
   - A crisp 2px border carries the semantic hue (step 8) and separates the element from the canvas.
   - High-contrast text (step 12) ensures maximum readability (11.4:1+ contrast ratio).
2. **Semantic Meaning, Not Decorative Rainbows**:
   - Color strictly encodes **component/entity type** or structural role.
   - Hues flow logically (e.g., Cool/Indigo $\rightarrow$ Cyan/Gateway $\rightarrow$ Slate/Bus $\rightarrow$ Amber/Worker $\rightarrow$ Crimson/External).
3. **Information Density & Active Labels**:
   - Every diagram carries a clear `--- title: "..." ---` header.
   - Edge relationships use active, directional verbs (e.g., `-->|publishes order_created|`, not `-->|uses|`).
   - Node labels include both the friendly name and structural role (e.g., `["Order Service (Service)"]`).

---

## 🌈 Universal Semantic Palette

| Semantic Role | Node Fill | Border (2px) | Label Text | Sequence `box rgb(...)` | Class Name |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Core / Primary Application** | `#182449` (Dark Indigo) | `#435db1` | `#d6e1ff` | `24,36,73` | `core` |
| **API / Gateway / Connector / Ingress** | `#082c36` (Dark Cyan) | `#11809c` | `#b6ecf7` | `8,44,54` | `gateway` |
| **Message Bus / Queue / Event Broker** | `#212225` (Dark Slate) | `#5a6169` | `#edeef0` | `33,34,37` | `bus` |
| **Service / Worker / Processing Engine** | `#302008` (Dark Amber) | `#8f6424` | `#ffe7b3` | `48,32,8` | `service` |
| **External System / 3rd-Party Partner** | `#381525` (Dark Crimson) | `#b0436e` | `#fdd3e8` | `56,21,37` | `external` |
| **Database / Storage / Cache** | `#162720` (Dark Emerald) | `#2d6a4f` | `#d8f3dc` | `22,39,32` | `storage` |
| **Utility / Internal Step / Helper** | `#1c1c1c` (Dark Neutral) | `#484848` | `#b4b4b4` | `28,28,28` | `utility` |

---

## 📐 Template Recipes by Diagram Type

### 1. Flowchart / Architecture Topology (`flowchart`)

```mermaid
%%{init: {'theme':'base','themeVariables':{'primaryTextColor':'#b0b4ba','lineColor':'#5a6169','edgeLabelBackground':'#0d0d0d','titleColor':'#b0b4ba'}}}%%
---
title: "Order Ingestion & Fulfillment Flow"
---
flowchart LR
    classDef core fill:#182449,stroke:#435db1,stroke-width:2px,color:#d6e1ff;
    classDef gateway fill:#082c36,stroke:#11809c,stroke-width:2px,color:#b6ecf7;
    classDef bus fill:#212225,stroke:#5a6169,stroke-width:2px,color:#edeef0;
    classDef service fill:#302008,stroke:#8f6424,stroke-width:2px,color:#ffe7b3;
    classDef external fill:#381525,stroke:#b0436e,stroke-width:2px,color:#fdd3e8;
    classDef storage fill:#162720,stroke:#2d6a4f,stroke-width:2px,color:#d8f3dc;

    Client["Client App (Client)"]:::gateway
    API["API Gateway (Gateway)"]:::gateway
    Kafka[("Kafka Event Bus (Broker)")]:::bus
    Worker["Order Worker (Service)"]:::service
    DB[("Orders MySQL (DB)")]:::storage
    Partner["Carrier API (External)"]:::external

    Client -->|POST /orders| API
    API -->|publishes order_created| Kafka
    Kafka -->|consumes| Worker
    Worker -->|persists order| DB
    Worker -->|dispatches shipment| Partner
```

---

### 2. Sequence Diagram (`sequenceDiagram`)

```mermaid
%%{init: {'theme':'base','themeVariables':{'textColor':'#b0b4ba','actorBkg':'#272a2d','actorTextColor':'#edeef0','actorBorder':'#5a6169','signalColor':'#5a6169','signalTextColor':'#edeef0','noteBkgColor':'#272a2d','noteTextColor':'#edeef0','noteBorderColor':'#5a6169','sequenceNumberColor':'#edeef0'}}}%%
---
title: "E2E Payment Authorization Flow"
---
sequenceDiagram
    autonumber
    actor User as User (Client)
    box rgb(8,44,54) API Gateway
        participant GW as APIGateway
    end
    box rgb(24,36,73) Core Services
        participant Auth as AuthService
        participant Pay as PaymentService
    end
    box rgb(38,21,37) External Systems
        participant Stripe as Stripe Gateway
    end

    User->>+GW: POST /checkout (token)
    GW->>+Auth: validateToken(token)
    Auth-->>-GW: 200 OK (userId)
    GW->>+Pay: authorizePayment(amount, userId)
    Pay->>+Stripe: POST /v1/charges
    Stripe-->>-Pay: 200 OK (chargeId)
    Pay-->>-GW: PaymentAuthorized
    GW-->>-User: 200 OK (receipt)
```

---

### 3. State Diagram (`stateDiagram-v2`)

```mermaid
%%{init: {'theme':'base','themeVariables':{'textColor':'#b0b4ba','labelColor':'#edeef0','titleColor':'#b0b4ba'}}}%%
---
title: "Order Lifecycle State Machine"
---
stateDiagram-v2
    [*] --> Pending : Order Placed
    Pending --> PaymentAuthorized : Payment Success
    Pending --> Cancelled : Payment Failed / User Cancel
    
    state PaymentAuthorized {
        [*] --> Preparing
        Preparing --> Packed : WMS Pick & Pack
        Packed --> Shipped : Handover to Carrier
    }
    
    PaymentAuthorized --> Delivered : Proof of Delivery
    Delivered --> [*]
    Cancelled --> [*]
```

---

### 4. Entity Relationship Diagram (`erDiagram`)

```mermaid
%%{init: {'theme':'base','themeVariables':{'textColor':'#b0b4ba','attributeColorOdd':'#1c1c1c','attributeColorEven':'#272a2d','titleColor':'#b0b4ba'}}}%%
---
title: "E-Commerce Core Schema"
---
erDiagram
    CUSTOMER ||--o{ ORDER : places
    CUSTOMER {
        bigint id PK
        string email UK
        string full_name
        timestamp created_at
    }
    ORDER ||--|{ ORDER_ITEM : contains
    ORDER {
        bigint id PK
        bigint customer_id FK
        string status
        decimal total_amount
        timestamp created_at
    }
    ORDER_ITEM {
        bigint id PK
        bigint order_id FK
        string sku
        int quantity
        decimal unit_price
    }
```

---

## ✅ Pre-Ship Quality Checklist

Before finalizing any Mermaid diagram:
1. [ ] **Title Block**: Added `--- title: "..." ---` frontmatter describing the diagram purpose.
2. [ ] **Consistent Semantic Palette**: Applied colors matching the role table (Indigo = Core, Cyan = Gateway, Slate = Bus, Amber = Service, Crimson = External, Emerald = Storage).
3. [ ] **Active Edge Verbs**: Edges explicitly describe actions (`publishes`, `synchronizes`, `validates`, `persists`).
4. [ ] **Legible Node Labels**: Labels state the component name and structural role in parentheses.
5. [ ] **No Cryptic Codes**: Free of undocumented internal ticket codes or bare shorthand.
