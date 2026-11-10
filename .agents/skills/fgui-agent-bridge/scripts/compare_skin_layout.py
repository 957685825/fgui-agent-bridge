#!/usr/bin/env python3
"""只读比较同族皮肤的已保存基础 XML；差异需逐条说明，不推断视觉正确性。"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.dont_write_bytecode = True
from check_component_structure import check_local_contract, load_components, read_xml, unique_object

# 换皮允许替换美术与文案；保留字号、描边、排版和状态属性，避免漏掉影响位置的变化。
IGNORED = {"src", "pkg", "fileName", "text", "title", "icon", "url", "color", "fillColor",
           "lineColor", "strokeColor", "shadowColor", "remark", "bgColor"}


def snapshot(project: Path, roots: list[str]) -> dict:
    project = project.expanduser().resolve()
    if project.is_file() and project.suffix.lower() == ".fairy":
        project = project.parent
    assets = project / "assets"
    if not assets.is_dir():
        raise ValueError(f"工程缺少 assets 目录：{project}")
    by_key, by_id = load_components(assets)
    result, active = {}, []

    def resolve(package: str, resource: str) -> str:
        key = by_id.get((package, resource))
        if key is None:
            raise ValueError(f"组件引用不存在：{package}/{resource}")
        if package != active[-1][1] and not by_key[key][2]:
            raise ValueError(f"跨包组件未导出：{key}")
        visit(key)
        return key

    def normalize_url(value: str) -> str:
        # 列表默认项、滚动条和扩展引用也会改变布局，必须沿真实资源 ID 检查。
        if not value.startswith("ui://"):
            raise ValueError(f"需要资源 ID 格式的组件 URL：{value}")
        return resolve(value[5:13], value[13:])

    def properties(element: ET.Element) -> dict:
        props = {key: value for key, value in element.attrib.items()
                 if key not in IGNORED and key != "id" and not key.startswith("designImage")}
        if element.tag == "component" and element.get("src"):
            props["component"] = resolve(element.get("pkg", active[-1][1]), element.get("src"))
        if element.tag == "item" and element.get("url"):
            props["url"] = element.get("url")
        elif element.tag == "loader":
            url = element.get("url", "")
            # Loader 也会引用图片，不能把正常图片换皮误判成缺失组件。
            if url.startswith("ui://") and (url[5:13], url[13:]) in by_id:
                props["url"] = url
        if element.tag == "gearIcon":
            props.pop("values", None)
            props.pop("default", None)
        for field in ("url", "defaultItem", "scrollBarRes"):
            if props.get(field):
                props[field] = ",".join(normalize_url(part) if part else ""
                                         for part in props[field].split(","))
        return props

    def state_tree(element: ET.Element) -> dict:
        return {"type": element.tag, "attributes": properties(element),
                "children": [state_tree(child) for child in element]}

    def visit(key: str) -> None:
        if key in [entry[0] for entry in active]:
            raise ValueError(f"组件循环引用：{key}")
        if key in result:
            return
        if key not in by_key:
            raise ValueError(f"组件未在 package.xml 登记：{key}")
        package, source, _ = by_key[key]
        root = read_xml(source)
        if root.tag != "component":
            raise ValueError(f"资源文件不是组件：{key}")
        nodes = root.findall("./displayList/*")
        check_local_contract(key, root, nodes)
        if any(node.get("id") in {"$root", "$order", "$states"} for node in nodes):
            raise ValueError(f"节点 ID 与报告保留键冲突：{key}")
        active.append((key, package))
        # 按稳定对象 ID 配对；重命名仍单独报告，绝不靠相近坐标猜测节点对应关系。
        rows = {"$root": properties(root),
                "$order": {"ids": [node.get("id") for node in nodes]},
                "$states": {"children": [state_tree(child) for child in root if child.tag != "displayList"]}}
        for node in nodes:
            rows[node.get("id")] = {"type": node.tag, **properties(node),
                                    "states": [state_tree(child) for child in node]}
        active.pop()
        result[key] = rows

    for key in roots:
        visit(key)
    return result


def compare(reference: Path, target: Path, roots: list[str], reviews: object = None) -> dict:
    before, after = snapshot(reference, roots), snapshot(target, roots)
    differences = []
    for component in sorted(before.keys() | after.keys()):
        old_rows, new_rows = before.get(component, {}), after.get(component, {})
        for node in sorted(old_rows.keys() | new_rows.keys()):
            old, new = old_rows.get(node, {}), new_rows.get(node, {})
            for field in sorted(old.keys() | new.keys()):
                if old.get(field) != new.get(field):
                    differences.append({"component": component, "node": node, "property": field,
                                        "before": old.get(field), "after": new.get(field)})
    if reviews is None:
        reviews = []
    if not isinstance(reviews, list):
        raise ValueError("差异确认文件必须是数组，每项包含完整差异与 reason")
    pending = list(differences)
    checked = []
    for review in reviews:
        if (not isinstance(review, dict)
                or set(review) != {"component", "node", "property", "before", "after", "reason"}
                or not isinstance(review["reason"], str) or not review["reason"].strip()):
            raise ValueError("每条确认必须包含 component/node/property/before/after 和非空 reason")
        change = {key: value for key, value in review.items() if key != "reason"}
        if change not in pending:
            raise ValueError(f"确认已过期、重复或不匹配当前差异：{review['component']}/{review['node']}/{review['property']}")
        pending.remove(change)
        checked.append(review)
    return {"ok": not pending, "scope": "saved-base-xml", "editorVerified": False,
            "runtimeVerified": False, "roots": roots,
            "checkedComponents": sorted(before.keys() | after.keys()),
            "differences": differences, "reviewed": checked, "unreviewed": pending}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--component", required=True, action="append", help="包/组件路径，可重复；两端使用相同路径")
    parser.add_argument("--review", type=Path, help="逐条确认的精确差异及原因 JSON")
    args = parser.parse_args()
    try:
        reviews = (json.loads(args.review.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)
                   if args.review else None)
        result = compare(args.reference, args.target, args.component, reviews)
    except (OSError, ValueError, ET.ParseError, RecursionError) as error:
        result = {"ok": False, "scope": "saved-base-xml", "error": str(error),
                  "editorVerified": False, "runtimeVerified": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
