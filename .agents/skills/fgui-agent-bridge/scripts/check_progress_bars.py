#!/usr/bin/env python3
"""只读检查选定 FGUI 百分比进度条的基础 XML；不替代编辑器与运行时验收。"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import sys

from check_component_structure import load_components, read_xml


def check_progress(project: Path, components: list[str], nine_grid_images: dict[str, str] | None = None) -> dict:
    project = project.expanduser().resolve()
    if project.suffix == '.fairy':
        project = project.parent
    assets = project / 'assets'
    by_key, by_id = load_components(assets)
    images = {}
    for manifest in sorted(assets.glob('*/package.xml')):
        package = read_xml(manifest)
        for item in package.findall('./resources/image'):
            image = (manifest.parent / item.get('path', '/').lstrip('/') / item.get('name', '')).resolve()
            if not image.is_relative_to(manifest.parent.resolve()):
                raise ValueError(f'图片路径超出包目录：{image}')
            images[package.get('id'), item.get('id')] = (item, image)
    nine_grid_images = nine_grid_images or {}
    if any(not reason.strip() for reason in nine_grid_images.values()):
        raise ValueError('九宫格例外必须写明素材原因')
    reviewed = set()
    issues, checked = [], []

    def resolve(node, package):
        """沿用结构检查的 ID 索引，不依赖可能过时的 fileName。"""
        target = by_id.get((node.get('pkg') or package, node.get('src')))
        if target is None:
            raise ValueError(f'组件引用不存在：{node.get("name")} / {node.get("src")}')
        return target

    def number(config, field, default):
        value = float(config.get(field, default))
        if not math.isfinite(value):
            raise ValueError(f'进度 {field} 不是有限数值')
        return value

    def fill_images(key, nodes, package, active):
        """只检查原生 bar 子树，兼容保持原纹理尺寸的嵌套裁剪填充。"""
        found = 0
        for node in nodes:
            if node.tag == 'image':
                item, image = images.get((node.get('pkg') or package, node.get('src')), (None, None))
                if item is None or not image.is_file():
                    raise ValueError(f'进度图片引用或文件不存在：{key}/{node.get("name")}')
                found += 1
                image_id = f"{node.get('pkg') or package}/{node.get('src')}"
                # 仅精确资源 ID 和说明可以豁免九宫格；不能借此接受拉伸或跳过缺失文件。
                if image_id in nine_grid_images and item.get('scale') == '9grid' and item.get('scale9grid'):
                    reviewed.add(image_id)
                elif item.get('scale') != 'tile':
                    issues.append(f'{key}/{node.get("name")}：填充图片必须平铺，当前 scale={item.get("scale", "none")}')
            elif node.tag == 'component':
                target = resolve(node, package)
                if target in active:
                    raise ValueError(f'填充组件循环引用：{target}')
                target_package, source, _ = by_key[target]
                found += fill_images(target, read_xml(source).findall('./displayList/*'), target_package, [*active, target])
        return found

    def visit(key, override=None, label=None, active=()):
        if key in active:
            raise ValueError(f'组件循环引用：{key}')
        if key not in by_key:
            raise ValueError(f'组件未登记：{key}')
        package, source, _ = by_key[key]
        root = read_xml(source)
        nodes = root.findall('./displayList/*')
        progress = root.get('extention') == 'ProgressBar'
        if progress:
            # 实例覆盖优先于组件默认值；缺省范围采用 FGUI 的 0–100。
            config = dict(root.find('ProgressBar').attrib) if root.find('ProgressBar') is not None else {}
            if override is not None:
                config.update(override.attrib)
            minimum, maximum, value = number(config, 'min', 0), number(config, 'max', 100), number(config, 'value', 0)
            checked.append({'component': key, 'value': value, 'min': minimum, 'max': maximum})
            if minimum != 0 or maximum != 100 or not 0 <= value <= 100:
                issues.append(f'{key}：百分比进度要求 min=0、max=100、value 在 0–100，当前 {minimum}/{maximum}/{value}')
            title = next((n.get('text') for n in nodes if n.get('name') == 'title'), None)
            for text in [label, title]:
                if text is not None and re.fullmatch(r'\s*\d+(?:\.\d+)?%\s*', text) and float(text.strip()[:-1]) != value:
                    issues.append(f'{key}：进度 {value:g} 与文字 {text} 不一致')
            bars = [n for n in nodes if n.get('name') in ('bar', 'bar_v')]
            if not bars or not fill_images(key, bars, package, [key]):
                issues.append(f'{key}：无法确认填充图片，需人工核对遮罩/自定义实现')
        references = [(node, resolve(node, package)) for node in nodes if node.tag == 'component']
        progress_nodes = [node for node, target in references if read_xml(by_key[target][1]).get('extention') == 'ProgressBar']
        labels = [node.get('text') for node in nodes if node.tag in ('text', 'richtext') and node.get('name') == 'progress_text']
        if labels and (len(progress_nodes) != 1 or len(labels) != 1):
            issues.append(f'{key}：progress_text 无法唯一配对进度条，需显式核对')
        for node, target in references:
            paired = labels[0] if node in progress_nodes and len(progress_nodes) == 1 and len(labels) == 1 else None
            visit(target, node.find('ProgressBar'), paired, (*active, key))

    if not components:
        raise ValueError('必须指定包含百分比进度条的组件')
    for component in components:
        visit(component)
    if not checked:
        issues.append('所选组件未发现 ProgressBar；列表 item/defaultItem 不自动展开，请直接指定条目组件')
    if set(nine_grid_images) != reviewed:
        issues.append('九宫格例外未命中所选填充或不是有效九宫格：' + str(sorted(set(nine_grid_images) - reviewed)))
    return {'ok': not issues, 'scope': 'saved-base-xml', 'checkedProgressBars': checked, 'issues': issues,
            'reviewedNineGridImages': {key: nine_grid_images[key] for key in sorted(reviewed)},
            'editorVerified': False, 'runtimeVerified': False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--component', action='append', required=True, help='包/组件路径，可重复；仅用于百分比且要求平铺的进度条')
    parser.add_argument('--nine-grid-image', action='append', nargs=2, default=[], metavar=('PACKAGE_ID/IMAGE_ID', 'REASON'), help='人工核对素材后的精确九宫格例外，必须写明原因')
    args = parser.parse_args()
    try:
        result = check_progress(args.project, args.component, dict(args.nine_grid_image))
    except (OSError, ValueError, SyntaxError) as error:
        result = {'ok': False, 'error': str(error)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
