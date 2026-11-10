#!/usr/bin/env python3
"""只读核对组件计划与已保存的 FairyGUI 基础分支 XML；不连接编辑器。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    """拒绝 JSON 重复键，避免计划中的同名节点被静默覆盖。"""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"结构计划存在重复键：{key}")
        result[key] = value
    return result


def read_xml(path: Path) -> ET.Element:
    data = path.read_text(encoding="utf-8-sig")
    # 只需要普通 FGUI XML；不接受外部声明或实体扩展。
    if "<!DOCTYPE" in data or "<!ENTITY" in data:
        raise ValueError(f"不支持带 DTD/实体声明的 XML：{path}")
    return ET.fromstring(data)


def load_components(assets: Path) -> tuple[dict, dict]:
    """按 package ID/resource ID 定位真实文件，不信任实例的 fileName 提示。"""
    by_key, by_id, package_ids = {}, {}, set()
    for manifest in sorted(assets.glob("*/package.xml")):
        root = read_xml(manifest)
        package_id = root.get("id")
        if root.tag != "packageDescription" or not package_id or package_id in package_ids:
            raise ValueError(f"无效或重复的包 ID：{manifest}")
        package_ids.add(package_id)
        item_ids = set()
        for item in root.findall("./resources/*"):
            item_id = item.get("id")
            if not item_id or item_id in item_ids:
                raise ValueError(f"无效或重复的资源 ID：{manifest}: {item_id}")
            item_ids.add(item_id)
            if item.tag != "component":
                continue
            source = (manifest.parent / item.get("path", "/").lstrip("/") / item.get("name", "")).resolve()
            if not source.is_relative_to(manifest.parent.resolve()) or source.suffix != ".xml":
                raise ValueError(f"组件路径必须是包内 XML：{source}")
            key = source.relative_to(assets).with_suffix("").as_posix()
            if key in by_key:
                raise ValueError(f"组件路径重复：{key}")
            by_key[key] = (package_id, source, item.get("exported") == "true")
            by_id[package_id, item_id] = key
    return by_key, by_id


def validate_plan(plan: object) -> dict:
    if not isinstance(plan, dict) or set(plan) != {"root", "components"}:
        raise ValueError("结构计划必须且只能包含 root 和 components")
    components = plan["components"]
    if not isinstance(components, dict) or not components:
        raise ValueError("components 必须是非空对象")
    if not isinstance(plan["root"], str) or plan["root"] not in components:
        raise ValueError("root 必须指向计划中的组件")
    for key, children in components.items():
        if not isinstance(key, str) or "/" not in key or not isinstance(children, dict):
            raise ValueError(f"组件计划必须使用 包/组件路径 和子节点对象：{key}")
        for name, expected in children.items():
            if not isinstance(name, str) or not name or re.fullmatch(r"n\d+", name):
                raise ValueError(f"计划节点必须使用语义名称：{key}/{name}")
            if isinstance(expected, str) and expected and expected != "component":
                continue
            if (isinstance(expected, dict) and set(expected) == {"component"}
                    and isinstance(expected["component"], str) and expected["component"]):
                continue
            raise ValueError(f"节点应为 XML 类型或 {{component: 包/组件路径}}：{key}/{name}")
    return plan


def check_local_contract(key: str, root: ET.Element, nodes: list[ET.Element]) -> None:
    """检查局部 ID/坐标以及最基本的动画、gear、relation 目标；不代替行为验收。"""
    ids = [node.get("id", "") for node in nodes]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"节点 ID 缺失或重复：{key}")
    controllers = [node.get("name", "") for node in root.findall("controller")]
    if any(not value for value in controllers) or len(controllers) != len(set(controllers)):
        raise ValueError(f"Controller 名称缺失或重复：{key}")
    for node in [root, *nodes]:
        for field in ("xy", "size"):
            if field in node.attrib and not re.fullmatch(r"-?\d+,-?\d+", node.get(field, "")):
                raise ValueError(f"{field} 必须为整数对：{key}/{node.get('name', '(root)')}")
        for gear in node:
            if gear.tag.startswith("gear") and gear.get("controller") not in controllers:
                raise ValueError(f"gear 引用不存在的局部 Controller：{key}/{node.get('name')}")
        for relation in node.findall("relation"):
            if relation.get("target", "") not in ["", *ids]:
                raise ValueError(f"relation 引用不存在的局部节点：{key}/{node.get('name')}")
    for item in root.findall("./transition/item"):
        if item.get("target", "") not in ["", *ids]:
            raise ValueError(f"Transition 引用不存在的局部节点：{key}/{item.get('target')}")


def check_structure(project: Path, plan: dict) -> dict:
    plan = validate_plan(plan)
    project = project.expanduser().resolve()
    if project.is_file() and project.suffix.lower() == ".fairy":
        project = project.parent
    assets = project / "assets"
    if not assets.is_dir():
        raise ValueError(f"工程缺少 assets 目录：{project}")
    by_key, by_id = load_components(assets)
    visited, active = set(), []

    def visit(key: str) -> None:
        if key in active:
            raise ValueError(f"组件循环引用：{' -> '.join([*active, key])}")
        if key in visited:
            return
        if key not in by_key:
            raise ValueError(f"组件未在 package.xml 登记：{key}")
        package_id, source, _ = by_key[key]
        root = read_xml(source)
        if root.tag != "component":
            raise ValueError(f"资源文件不是组件：{key}")
        nodes = root.findall("./displayList/*")
        references = {}
        for node in nodes:
            if node.tag != "component":
                continue
            target_package = node.get("pkg") or package_id
            target = by_id.get((target_package, node.get("src")))
            if target is None:
                raise ValueError(f"组件引用不存在：{key}/{node.get('name')} ({target_package}/{node.get('src')})")
            if target_package != package_id and not by_key[target][2]:
                raise ValueError(f"跨包组件未导出：{key}/{node.get('name')} -> {target}")
            references[node] = target

        if key in plan["components"]:
            expected = plan["components"][key]
            names = [node.get("name", "") for node in nodes]
            if any(not name for name in names) or len(names) != len(set(names)):
                raise ValueError(f"节点名称缺失或重复：{key}")
            missing, extra = set(expected) - set(names), set(names) - set(expected)
            if missing or extra:
                raise ValueError(f"节点归属不符：{key}; 缺少={sorted(missing)}; 多余={sorted(extra)}")
            for node in nodes:
                name = node.get("name")
                wanted = expected[name]
                if isinstance(wanted, str):
                    if node.tag != wanted:
                        raise ValueError(f"节点类型不符：{key}/{name}; 需要 {wanted}，实际 {node.tag}")
                elif node.tag != "component" or references.get(node) != wanted["component"]:
                    raise ValueError(f"必须引用指定独立组件：{key}/{name} -> {wanted['component']}")
            check_local_contract(key, root, nodes)

        active.append(key)
        for target in references.values():
            visit(target)
        active.pop()
        visited.add(key)

    visit(plan["root"])
    unused = set(plan["components"]) - visited
    if unused:
        raise ValueError(f"计划中的组件未被根组件引用：{sorted(unused)}")
    return {"ok": True, "scope": "saved-base-xml", "plannedComponents": sorted(plan["components"]),
            "checkedComponents": sorted(visited), "editorVerified": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path, help="工程目录或 .fairy 文件，只读")
    parser.add_argument("--plan", required=True, type=Path, help="制作前确定的结构计划 JSON")
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
        result = check_structure(args.project, plan)
    except (OSError, ValueError, ET.ParseError, RecursionError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
