#!/usr/bin/env python3
"""Generates a realistic ~300MB Amazon GET_XML_BROWSE_TREE_DATA report for Germany.

Target size: >= 300 MB (~314,572,800 bytes).
Conforms to BrowseTreeReport.xsd element schema.
Preserves existing fixture nodes (e.g. leaf 3010075031 with recommended_browse_nodes 4147288051 for PRODUCT)
so that all existing tests and assertions continue to match, while exercising streaming and memory safety.
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK_DATA_DIR = os.path.join(HERE, "mock-data")
TARGET_FILE = os.path.join(MOCK_DATA_DIR, "browse-tree-de-300mb.xml")
TARGET_BYTES = 300 * 1024 * 1024  # 314,572,800 bytes (300 MB)

# The canonical German fixture nodes from amazon.mock.json
GERMAN_BASE_NODES = """  <Node>
    <browseNodeId>908824031</browseNodeId>
    <browseNodeAttributes count="1">
      <attribute name="item_type_keyword">major_appliances</attribute>
    </browseNodeAttributes>
    <browseNodeName>Elektro-Großgeräte</browseNodeName>
    <browseNodeStoreContextName>Elektro-Großgeräte</browseNodeStoreContextName>
    <browsePathById>908823031,908824031</browsePathById>
    <browsePathByName>Elektro-Großgeräte</browsePathByName>
    <hasChildren>true</hasChildren>
    <childNodes count="1">
      <id>13528201031</id>
    </childNodes>
    <productTypeDefinitions>MAJOR_APPLIANCES</productTypeDefinitions>
    <refinementsInformation count="0">
    </refinementsInformation>
  </Node>
  <Node>
    <browseNodeId>13528201031</browseNodeId>
    <browseNodeAttributes count="1">
      <attribute name="item_type_keyword">refrigerator</attribute>
    </browseNodeAttributes>
    <browseNodeName>Kühlschränke, Gefrierschränke &amp; Eiswürfelbereiter</browseNodeName>
    <browseNodeStoreContextName>Kühlschränke, Gefrierschränke &amp; Eiswürfelbereiter</browseNodeStoreContextName>
    <browsePathById>908823031,908824031,13528201031</browsePathById>
    <browsePathByName>Elektro-Großgeräte,Kühlschränke, Gefrierschränke &amp; Eiswürfelbereiter</browsePathByName>
    <hasChildren>true</hasChildren>
    <childNodes count="3">
      <id>3495086031</id>
      <id>1399937031</id>
      <id>16231641</id>
    </childNodes>
    <productTypeDefinitions>REFRIGERATOR</productTypeDefinitions>
    <refinementsInformation count="0">
    </refinementsInformation>
  </Node>
  <Node>
    <browseNodeId>3169011</browseNodeId>
    <browseNodeAttributes count="1">
      <attribute name="item_type_keyword">home</attribute>
    </browseNodeAttributes>
    <browseNodeName>Küche, Haushalt &amp; Wohnen</browseNodeName>
    <browseNodeStoreContextName>Küche, Haushalt &amp; Wohnen</browseNodeStoreContextName>
    <browsePathById>3167641,3169011</browsePathById>
    <browsePathByName>Küche, Haushalt &amp; Wohnen</browsePathByName>
    <hasChildren>true</hasChildren>
    <childNodes count="1">
      <id>16075741</id>
    </childNodes>
    <productTypeDefinitions>HOME</productTypeDefinitions>
    <refinementsInformation count="0">
    </refinementsInformation>
  </Node>
  <Node>
    <browseNodeId>16075741</browseNodeId>
    <browseNodeAttributes count="1">
      <attribute name="item_type_keyword">major_appliances</attribute>
    </browseNodeAttributes>
    <browseNodeName>Haushaltsgroßgeräte</browseNodeName>
    <browseNodeStoreContextName>Haushaltsgroßgeräte</browseNodeStoreContextName>
    <browsePathById>3167641,3169011,16075741</browsePathById>
    <browsePathByName>Küche, Haushalt &amp; Wohnen,Haushaltsgroßgeräte</browsePathByName>
    <hasChildren>true</hasChildren>
    <childNodes count="1">
      <id>13528201031</id>
    </childNodes>
    <productTypeDefinitions>MAJOR_APPLIANCES</productTypeDefinitions>
    <refinementsInformation count="0">
    </refinementsInformation>
  </Node>
  <Node>
    <browseNodeId>13528201031</browseNodeId>
    <browseNodeAttributes count="1">
      <attribute name="item_type_keyword">refrigerator</attribute>
    </browseNodeAttributes>
    <browseNodeName>Kühl- &amp; Gefrierschränke</browseNodeName>
    <browseNodeStoreContextName>Kühlschränke, Gefrierschränke &amp; Eiswürfelbereiter</browseNodeStoreContextName>
    <browsePathById>3167641,3169011,16075741,13528201031</browsePathById>
    <browsePathByName>Küche, Haushalt &amp; Wohnen,Haushaltsgroßgeräte,Kühl- &amp; Gefrierschränke</browsePathByName>
    <hasChildren>true</hasChildren>
    <childNodes count="3">
      <id>3495086031</id>
      <id>1399937031</id>
      <id>16231641</id>
    </childNodes>
    <productTypeDefinitions>REFRIGERATOR</productTypeDefinitions>
    <refinementsInformation count="0">
    </refinementsInformation>
  </Node>
  <Node>
    <browseNodeId>3010075031</browseNodeId>
    <browseNodeAttributes count="2">
      <attribute name="item_type_keyword">refrigerator</attribute>
      <attribute name="recommended_browse_nodes">4147288051</attribute>
    </browseNodeAttributes>
    <browseNodeName>Kühlschränke ohne Gefrierfach</browseNodeName>
    <browseNodeStoreContextName>Kühlschränke ohne Gefrierfach</browseNodeStoreContextName>
    <browsePathById>3167641,3169011,16075741,3010075031</browsePathById>
    <browsePathByName>Elektro-Großgeräte,Haushaltsgroßgeräte,Kühlschränke ohne Gefrierfach</browsePathByName>
    <hasChildren>false</hasChildren>
    <childNodes count="0" />
    <productTypeDefinitions>PRODUCT</productTypeDefinitions>
    <refinementsInformation count="0">
    </refinementsInformation>
  </Node>
  <Node>
    <browseNodeId>3010076031</browseNodeId>
    <browseNodeAttributes count="1">
      <attribute name="item_type_keyword">freezer</attribute>
    </browseNodeAttributes>
    <browseNodeName>Gefrierschränke</browseNodeName>
    <browseNodeStoreContextName>Gefrierschränke</browseNodeStoreContextName>
    <browsePathById>3167641,3169011,16075741,3010076031</browsePathById>
    <browsePathByName>Elektro-Großgeräte,Haushaltsgroßgeräte,Gefrierschränke</browsePathByName>
    <hasChildren>false</hasChildren>
    <childNodes count="0" />
    <productTypeDefinitions>PRODUCT</productTypeDefinitions>
    <refinementsInformation count="0">
    </refinementsInformation>
  </Node>
  <Node>
    <browseNodeId>3010077031</browseNodeId>
    <browseNodeAttributes count="1">
      <attribute name="item_type_keyword">unlisted</attribute>
    </browseNodeAttributes>
    <browseNodeName>Nicht listbar</browseNodeName>
    <browseNodeStoreContextName>Nicht listbar</browseNodeStoreContextName>
    <browsePathById>3167641,3169011,16075741,3010077031</browsePathById>
    <browsePathByName>Elektro-Großgeräte,Haushaltsgroßgeräte,Nicht listbar</browsePathByName>
    <hasChildren>false</hasChildren>
    <childNodes count="0" />
    <productTypeDefinitions></productTypeDefinitions>
    <refinementsInformation count="0">
    </refinementsInformation>
  </Node>
"""

SYNTHETIC_NODE_TEMPLATE = """  <Node>
    <browseNodeId>{node_id}</browseNodeId>
    <browseNodeAttributes count="2">
      <attribute name="item_type_keyword">{item_type}</attribute>
      <attribute name="recommended_browse_nodes">{rbn_id}</attribute>
    </browseNodeAttributes>
    <browseNodeName>Kategorie {name_suffix}</browseNodeName>
    <browseNodeStoreContextName>Elektro-Großgeräte</browseNodeStoreContextName>
    <browsePathById>3167641,3169011,16075741,{node_id}</browsePathById>
    <browsePathByName>Elektro-Großgeräte,Haushaltsgroßgeräte,Kategorie {name_suffix}</browsePathByName>
    <hasChildren>{has_children}</hasChildren>
    <childNodes count="0" />
    <productTypeDefinitions>{ptd}</productTypeDefinitions>
    <refinementsInformation count="0">
    </refinementsInformation>
  </Node>
"""


def ensure_browse_tree_300mb(target_file=TARGET_FILE, min_bytes=TARGET_BYTES):
    """Ensures the 300MB browse tree file exists. Generates it if missing or undersized."""
    if os.path.exists(target_file) and os.path.getsize(target_file) >= min_bytes:
        return target_file

    os.makedirs(os.path.dirname(target_file), exist_ok=True)
    temp_target = target_file + ".tmp"
    t0 = time.time()

    with open(temp_target, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<Result>\n  <query>3167641</query>\n')
        f.write(GERMAN_BASE_NODES)

        current_bytes = f.tell()
        # Pre-compile chunks to write in fast batches of 5000 nodes
        batch = []
        node_counter = 4000000000

        while current_bytes < min_bytes:
            node_counter += 1
            is_leaf = (node_counter % 5 != 0)
            ptd = "PRODUCT" if (node_counter % 2 == 0) else "MAJOR_APPLIANCES"
            item_type = "appliance" if ptd == "MAJOR_APPLIANCES" else "product"
            rbn = str(node_counter)

            node_str = SYNTHETIC_NODE_TEMPLATE.format(
                node_id=node_counter,
                item_type=item_type,
                rbn_id=rbn,
                name_suffix=f"DE-{node_counter}",
                has_children="false" if is_leaf else "true",
                ptd=ptd
            )
            batch.append(node_str)
            if len(batch) >= 5000:
                f.write("".join(batch))
                current_bytes += sum(len(s.encode("utf-8")) for s in batch)
                batch.clear()

        if batch:
            f.write("".join(batch))
            batch.clear()

        f.write("</Result>\n")

    os.replace(temp_target, target_file)
    size_mb = os.path.getsize(target_file) / (1024 * 1024)
    print(f"Generated 300MB Browse Tree file at {target_file} ({size_mb:.2f} MB) in {time.time() - t0:.2f}s", flush=True)
    return target_file


if __name__ == "__main__":
    ensure_browse_tree_300mb()
