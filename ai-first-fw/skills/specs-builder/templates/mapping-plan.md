# Mapping plan: `<feature name>`

`<area>` · `<spec folder path>` · <yyyy-MM-dd>

| § | Section | Holds |
| --- | --- | --- |
| 1 | Spec File Tree Changes | which spec files this run creates, and which it updates |
| 2 | Mapping rows | every boundary field: where it came from, how sure you are, what it costs if it is wrong |
| 3 | Unmapped Fields | every target with no source, and every inbound field dropped |

<!-- HOW TO FILL THIS FILE

     Fill in this order; each step feeds the next, and the same order says which question is
     askable when.
       1. §2 mapping rows, one `## 2. File:` section per spec file. A row settles BEFORE the spec
          line it produces gets written — the spec is filled from this file, so a spec line
          written first makes this file a transcript rather than the authority.
       2. §1 the file tree, from what §2 turned out to touch. Written first it is a guess at
          scope; written second it is a record of it.
       3. §3 the unmapped fields, from what §2 left over — every target §2 never reached, and
          every inbound field §2 dropped.
     A row lands as the read that produced it comes back, not from memory at the end. That is why
     the copy is open from Entry: a grade written before its citation is a grade from memory, and
     that is exactly what the reviewer goes looking for.

     Delete a section you have nothing for: an empty section is noise, a missing one is
     information. §3 is the exception — an empty §3 is a claim, so write "nothing unmapped"
     rather than dropping it.

     These comments do not ship. The run strips them, and what is handed over is the headings and
     the tables; when that happens is the run's business, in `SKILL.md`.

     The hand-over list — one line, one check, and the last thing in this comment:
       - every boundary field carries a `MAP-xx` row with a grade in its Confidence cell;
       - every vital key resolves in the mapping table (§2) or the unmapped-fields table (§3) —
         the coverage comment below §3 is the list, and a key in neither is the defect it exists
         to prevent;
       - every silent-failure row — keys, identifiers, money, state — carries Reason, Contract
         role, Near-miss and Consequence, all four filled;
       - every copied value names its source, and every derived value names the file AND the
         field it was derived from;
       - every carried-over or unknown value is re-derived this run, or flagged;
       - every `<placeholder>` is replaced, and every example row is deleted. -->

<!-- WRITING RULES — they apply to every section

     Copy evidence exactly. A rewritten quote is a defect, not a shorter sentence. Where you
     quote a partner doc, a payload or a line of code, it arrives verbatim or it does not arrive.

     This document mints `MAP-xx`, and nothing else. Every other identifier — a Jira key, a
     requirement number, an ID another document minted — is cited here, never restated: if the
     meaning of one is worth repeating here, it was in the wrong place.

     Narrative lives here. This is the plan-side half of the rule whose spec-side half is the output
     contract in `SKILL.md`: a fact needing a clause of justification to stand up is a row in this file,
     and the spec line is the fact alone. Reasoning, consequences, trade-offs, provenance, a
     harness claim that does not hold for this integration — all of it lands in a row here, and
     none of it in a spec.

     Two registers, no pointer outward. Where a harness `recommended:` block's `why` and a row
     here cover the same decision, the `why` states the reason short enough to stand alone and
     the row carries the full justification. Same meaning twice, at two lengths — never a
     cross-reference from one to the other.

     A cell states its own content. No cell in this file says "see" anything: pointers run plan →
     spec, never back, and never plan → plan.

     Check: every quote is verbatim, no identifier but `MAP-xx` is minted here, and no cell
     points outward. -->

## 1. Spec File Tree Changes

```text
<area>/specs/<code>/
├── <ExistingSpec>.yaml            UPDATE
└── <NewSpec>.yaml                 NEW
```

<!-- The tree is where the run's implementation status is recorded.

     Every file this run touched gets a line, with one verb:
       NEW     — this run created it.
       UPDATE  — it existed and this run changed it.
     A file you opened and left alone gets no line. A file you disabled rather than deleted is an
     UPDATE, and which way the trim went belongs in the §2 section for that file.

     Check: every spec file this run created or changed has a line, and every line carries NEW or
     UPDATE. -->

## 2. File: `<spec file name>`

### `<DTO / object / model name>`

| ID | OMS Property | External Property | Reason | Confidence | Contract role | Near-miss | Consequence if wrong | Fallback / null-vs-absent | Value set / cardinality |
|---|---|---|---|---|---|---|---|---|---|
| MAP-01 | `property` | `external_prop` | `<what makes these the same field, and where you read it>` | `<A / B / C>` | `<who assigns it; request vs response>` | `<the candidate you rejected, or none>` | `<the business consequence of getting it wrong>` | `<the fallback; null vs absent answered separately>` | `<what closed the value set; cardinality where shapes differ, else —>` |

<!-- Repeat this whole section — same `## 2. File:` heading form — once per spec file, and §3
     stays last. Every `## 2. File:` section is checked exactly like the first. Where one spec
     file carries several DTOs, each gets its own `###` table under that file's section.

     THE COLUMNS

       ID          — `MAP-01` upward, minted here and never reused. The unmapped table (§3) and
                     the hand-off report cite these numbers, so a number that changes meaning
                     between runs is worse than a gap.
       OMS Property
                   — our side of the boundary, as the field is actually named.
       External Property
                   — the partner's side, as their contract names it. Where their contract and
                     their live payload disagree, that disagreement is the row's finding, not a
                     detail to pick between.
       Reason      — what makes these two the same field, AND where you read it. "Same business
                     meaning" alone is not a reason; "same business meaning, partner doc §4.2" is.
                     This cell carries the citation the grade rests on.
       Confidence  — the grade. See below; it is the longest rule in this file for a reason.
       Contract role
                   — who assigns the value, and whether it lives in a request input or a response
                     payload. An identifier placed on the wrong side of that split fails silently
                     and is found in production.
       Near-miss   — the candidate you considered and rejected, and why. `none` where there was
                     no plausible second choice. This is the column that survives you: the next
                     reader's first instinct is usually the field you already ruled out.
       Consequence if wrong
                   — what happens to the business, not to the code. "Orders strand before
                     fulfillment", not "the mapping throws".
       Fallback / null-vs-absent
                   — what happens when the value is missing, and null versus absent answered
                     SEPARATELY. They are two questions and the partner answers them differently;
                     one cell holding one answer means you asked one question.
       Value set / cardinality
                   — what closed the value set: a schema, an enum, a partner doc section. A value
                     set is closed by documentation, never by a sample: a payload showing three of
                     five statuses looks complete, and a row resting on it grades `C`. Cardinality
                     where the shapes differ across the boundary — one row per unit against one
                     row per SKU with a quantity is a mapping, not a detail — and `—` where they
                     do not.

     THE SILENT-FAILURE ROWS

     Keys, identifiers, money and state fail without an error: nothing throws, nothing logs, and
     the damage surfaces days later in reconciliation. On those rows Reason, Contract role,
     Near-miss and Consequence are all four mandatory, and naming the source field is not enough
     — say why that field and not the alternatives, who assigns it in the contract, and what it
     costs the business to choose wrong. Every other row may write `—` in Near-miss, Consequence,
     Fallback and Value set where the question genuinely does not arise.

     THE GRADE

     The Confidence cell carries the grade itself, not prose about it. An empty cell fails. The
     reviewer reads the grade to decide how hard to look, so a grade that flatters the row costs
     more than a gap.

     The hierarchy is per question type. "The documents" is two families that can conflict, so the
     grade means nothing until you know which question the row answers.

       WIRE facts — field names, formats, enum values, null-versus-absent, cardinality.
         Order: the partner's API doc → captured payloads → our code.
       CONTRACT facts — serviceParam, operation, publisher, direction, inputAccessor, outputRoot.
         Order: the platform docs and core code. The partner has no standing here, and a silent
         partner doc does not lower the grade.

     Then, whichever it is:

       A — surely.  A first-grade source for that question type states it.
       B — likely.  A second-grade source states it, or a first-grade source states it in part.
       C — assumed. It rests on a sibling integration, or on logic and assumption alone.

     Inherit a grade, never re-mint one. Where the harness already graded its own claim — a
     `recommended:` block carrying its `why` inside a stub's `contract:`, or a README marker
     meaning "name-matched but stubbed in sampled integrations; confirm on implementation" — carry
     that grade through. Re-deriving stamps `A` on a claim the harness itself flagged as
     unconfirmed, and the flag sits in a first-grade document.

     A sibling-sourced row names its impl. Sibling code looks second-grade — it compiles, it is
     right there — while carrying a known failure mode. Any row whose Reason cites another
     integration states three things in that cell: which impl, whether it is live, and whether the
     behaviour was confirmed or only a candidate. A `B` laundered from a sibling is more dangerous
     than an honest `C`, because a `B` does not get re-checked.

     Grade by what was cited, never by who said it. A human's recollection grades `C`, and `C` is
     what the reviewer sends back. The same fact read out of the partner's API doc grades `A`. A
     question you could have looked up downgrades a row that was entitled to an `A` — which is why
     finding facts is the run's job and not the human's.

     Where the grade is expressed. Where the area's harness has a mechanism for unresolved
     contract fields, use it: an `A`-grade value is filled directly, while `B` and `C` leave the
     slot blank and let the area's recommendation block carry the fallback. Where the area has no
     such mechanism, the grade lives in this file and the hand-off report only — never invent
     one in the spec.

     Check: every row carries a grade in its Confidence cell, every silent-failure row has all
     four of its mandatory cells filled, every row citing a sibling names which impl and whether
     it is live and confirmed, and no cell points outward. -->

## 3. Unmapped Fields

| Direction | Field | Why unmapped / dropped |
|---|---|---|
| `<target / inbound>` | `<field>` | `<reason>` |

<!-- Every target with no source, and every inbound field dropped, with its reason. Silence is a
     finding: a field that appears in neither table was not considered, and nothing downstream can
     tell that apart from a field that was considered and dismissed.

       Direction — `target` for something our side needs that the partner has no field for;
                   `inbound` for something the partner sends that we drop.
       Why       — for a target, what breaks in its absence and what stands in meanwhile. For an
                   inbound field, why dropping it is safe. "Not needed" is not a reason; "not
                   needed — the OMS derives it from the line total" is.

     An empty §3 is a claim, not an omission. Write `nothing unmapped — every vital key resolves
     in §2` rather than deleting the section.

     Check: every vital key absent from §2 has a row here, and every row says what breaks or why
     dropping it is safe. -->

<!-- COVERAGE — THE ORDER'S PASSPORT

     An order crosses four systems — sale channel → OMS → WMS → carrier — and its status flows
     back along the same path. The passport is the data that has to survive that round trip. Find
     these in the partner's payloads FIRST; everything else is decoration. Interview for them
     before the rest of the payload — this comment is in view from Entry precisely so that the
     payload rounds can be driven from it.

     EVERY KEY BELOW RESOLVES EXACTLY ONE OF TWO WAYS: a `MAP-xx` row in the mapping table (§2),
     or a row in the unmapped-fields table (§3) naming what the partner has no field for and what
     breaks in its absence. A key appearing in neither is the defect this list exists to prevent.

     The dual-identifier handshake. At every hop the sender includes ITS OWN reference, the
     receiver assigns ITS OWN ID and returns it, and every later message between them — webhook,
     ship confirmation, cancel, COD remittance — carries BOTH IDs side by side. Drop either and
     correlation dies on the return leg.

     One value keeps its meaning and changes its name at each hop: a channel's `seller_sku`
     arrives as `sku` on the next wire and `sellerSku` on the one after. These rows are VERBATIM
     STRING COPIES UNDER A NEW KEY, so a mapping row that computes or reformats an identifier is a
     finding. Store every ID as a string — they overflow integers and carry leading zeros.

     The property names below are variants seen across real platforms. The partner has its own
     name for each, and finding it is the mapping job.

     LEG 1 — sale channel ↔ OMS
       Channel order ID          `order_id` `order_sn` `order_number` `id` — the only key the
                                 channel accepts on every later call: order detail, ship, cancel,
                                 return. Some carry two: a system ID
                                 and a human-facing order number.
       Line-item ID              `order_item_id` `line_item_id` `item_id`+`model_id` — fulfillment,
                                 partial cancellation and returns are keyed at line level.
                                 Semantics differ: one row per unit (quantity exploded), or one
                                 row per SKU with a quantity.
       Package ID                `package_id` `package_number` — channels fulfill at package
                                 granularity; ship calls, labels and logistics webhooks all key
                                 on it. Split and combined shipments cannot round-trip on
                                 order ID alone.
       Seller SKU                `seller_sku` `sku` `shop_sku` `model_sku` — the exact-string join
                                 between channel listing, OMS catalog and WMS item. A mismatch
                                 strands the order before fulfillment starts.
       Order status              `order_status` `status` — drives the OMS state machine and which
                                 actions are legal. Every channel has its own vocabulary; each
                                 maps to one canonical internal status model.
       Status event + timestamp  webhook `type`/`code`, `status_update_time` — webhooks are
                                 at-least-once and incomplete on every platform: the event triggers
                                 a re-pull of order detail and the timestamp orders events. Polling
                                 stays the reconciliation baseline.
       Recipient address + phone `recipient_address{…}` `address_shipping{…}` — channels mask or
                                 virtualize buyer PII, so the payload is the only usable copy, and
                                 it can change after order creation. Re-pull before handover.
       Tracking number           `tracking_number` — channel-arranged logistics means the OMS
                                 RETRIEVES it; seller-arranged means the OMS SUPPLIES it. Both
                                 directions must be supported, per fulfillment type.
       Shipping provider code    `shipping_provider_id` `shipment_provider_code` — required when
                                 the seller supplies its own tracking number; the channel validates
                                 the pair.
       Reverse-flow IDs          `cancel_id` `return_id` `reverse_order_id` — cancels and returns
                                 arrive as their own objects referencing the original order. Both
                                 directions of that link are needed to reconcile refunds and
                                 restock.

     LEG 2 — OMS ↔ WMS
       External order reference  `reference_id` `partner_order_id` `external_order_id`
                                 `reference_num` — the echo key the WMS returns on every downstream
                                 event. Often doubles as the idempotency key: a duplicate is
                                 rejected, not merged. Unique per account/channel, and immutable.
       WMS-assigned order/shipment ID
                                 `id` `order_id` `shipment_id` — cancel, amend and shipment lookup
                                 often accept only the WMS's own ID. Capture it from the
                                 create-order response or lose those operations; it may be
                                 re-minted on cancel/replace.
       Channel / source identity `channel_id` `shop_name` `store_id` — scopes the external
                                 reference's uniqueness and routes ship confirmations back to the
                                 right upstream integration.
       Warehouse ID              `warehouse_id` `location_id` `facility_id` — multi-warehouse
                                 routing, and the second key (with SKU) for inventory sync. Ship
                                 confirms report which warehouse actually shipped.
       SKU per line              `sku` — resolved by exact string lookup at ingest. A SKU unknown
                                 to the WMS stops the order at the door: channel seller-SKU, OMS
                                 catalog SKU and WMS SKU must be the SAME STRING.
       Quantity — ordered vs shipped
                                 `quantity` `quantity_shipped` `backorder_quantity` — short-ships
                                 and partial shipments are normal; the per-line delta is what the OMS relays to the
                                 channel and re-plans from.
       Line-level external ID    `partner_line_item_id` `line_item_id` — lets line amendments,
                                 splits and confirmations correlate without guessing by SKU, which
                                 repeats across lines.
       Shipping method instruction
                                 `shipping_method` `carrier` `ship_option` — an unmapped value
                                 fails order creation or ships the wrong service. Its mapping table
                                 is a standing artifact of the integration.
       Ship confirmation payload `tracking_number` `carrier` `packages[]{sku, quantity}` timestamps
                                 — what the OMS forwards to the channel to trigger "shipped". It
                                 must carry the external-reference echo plus tracking, or the
                                 channel leg stalls.
       Inventory sync keys       `sku` + `warehouse_id`, `on_hand`, `available` — feeds
                                 available-to-sell per channel with no order reference involved, so
                                 these two keys carry the whole feed and must be exact.
       Secondary item identifiers
                                 `barcode` `lot_number` `serial_number` `expiry_date` — scanning,
                                 batch and expiry control, serial tracking, returns matching. They
                                 ride alongside the SKU and never replace it as the join key.

     LEG 3 — OMS/WMS ↔ carrier
       Merchant reference        `client_order_code` `partner_id` `reference`
                                 `merchant_order_number` — often OPTIONAL in the carrier's API, and
                                 the only carrier-independent join key; the carrier echoes it in
                                 webhooks beside its own code. Skip it and status updates
                                 match on the carrier's number alone.
       Waybill / tracking number `tracking_number` `order_code` `awb_no` — the universal handle for
                                 tracking, labels, cancellation and COD reconciliation — what
                                 buyer, channel and carrier all see. Persist it
                                 the moment it is returned.
       Consignee details         `to_name` `to_phone` `to_address`, district/ward codes, `postcode`
                                 — often required as structured location codes from the carrier's
                                 own geography, not free text. Unmappable geo codes are the top
                                 shipment-creation failure, and the address-to-geography mapping
                                 is a real task per carrier.
       COD amount                `cod_amount` `pick_money` `cod` — what the courier physically
                                 collects, in local currency with carrier-specific caps, and it anchors
                                 remittance reconciliation. A wrong value is a direct financial
                                 loss.
       Weight and dimensions     `weight` `length` `width` `height` — prices the shipment, and units
                                 vary (grams vs kg, cm). Carriers re-weigh and push back adjusted
                                 weight and fees, so declared vs actual is a pair, not one value.
       Service selection         `service_type_id` `service_level` `express_type` — determines SLA,
                                 cost, and the handover mode (pickup vs drop-off) the warehouse
                                 must physically execute.
       Freight payer             `payment_type_id` `payment_term` — shipper or receiver. Changes
                                 billing and sometimes the COD math; a wrong value misallocates
                                 cost on every parcel. Distinct from the buyer's
                                 payment method.
       Shipping label            `label_url` `postage_label`, label print token — the warehouse
                                 cannot hand over a parcel without it, and the fetch is keyed by the
                                 carrier's number, sometimes via a short-lived token.
       Tracking status + reason  `status` `status_id` `reason_code` `reason` — the milestone chain
                                 (created → picked up → in transit → out for delivery → delivered
                                 / failed / returning / returned) feeds the OMS state machine and
                                 the channel. Map each carrier's vocabulary to
                                 one canonical set, and treat RETURN-TO-SENDER as a first-class
                                 state that flows back to channel and inventory.
       Dual IDs in every callback
                                 carrier code + merchant reference together — the correlation
                                 mechanism. Establish WHICH ID the cancel API takes; carriers are
                                 inconsistent — some cancel by their code and some by yours — so
                                 store both.
       COD reconciliation fields `cod_amount` `cod_transfer_date` `fee{…}` — closes the money loop,
                                 keyed by the dual IDs. Where no reconciliation API exists this
                                 becomes a manual monthly process — flag it early.
       Declared / insurance value
                                 `insurance_value` `goods_value` — determines compensation on loss
                                 or damage claims, with carrier caps. Claims reference the waybill.

     THE INVERTED FLOW — channel-arranged logistics. Where the marketplace owns shipping, the OMS
     never calls the carrier: the channel books its own carrier and ASSIGNS the tracking number,
     the OMS retrieves it and fetches the label as a platform document, and carrier milestones
     arrive through the channel's webhooks. On this path the correlation keys are the channel order
     ID plus package ID, and the tracking number is a downstream attribute rather than a key anyone
     mints. Establish which model the partner uses — or whether both are live — before mapping the
     carrier leg at all.

     WHAT THE OMS PERSISTS. The OMS is the hub, so the passport is what it keeps per order: channel
     identity and channel order ID, channel line-item IDs with their semantics, channel package
     ID(s), seller SKU per line, the OMS internal ID, the external reference sent to the WMS PLUS
     the WMS-assigned IDs, warehouse ID, the merchant reference sent to the carrier PLUS the
     carrier waybill and carrier code, COD amount, an address snapshot with its update timestamp,
     per-hop status with event timestamps mapped to one canonical status model, and any
     reverse-flow IDs linked back to the original. Every ID a string; every consumer idempotent by
     the dual keys; periodic pull-reconciliation part of the contract rather than a fallback.

     Check: every key above resolves in the mapping table (§2) or the unmapped-fields table (§3),
     no identifier row computes or reformats its value, and the partner's logistics model is
     recorded — either Leg 3 rows are present, or §3 carries a row saying the channel arranges
     shipping and the OMS never calls the carrier. -->
