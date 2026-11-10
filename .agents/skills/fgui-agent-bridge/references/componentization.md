# 组件化制作与结构验收

在新建/组装 UI 时阅读。MCP、CLI 和直接生成 XML 使用同一套规则；本规范不授权重构既有界面，也不把用户举例的截图当成待修改资产。

## 制作前：确定边界

先检查已有包资源和邻近界面的组织方式。在任务说明中列简短清单：组件名、职责、内部元素、父组件、复用资源。金额区、独立状态徽章、重复奖励项通常有清晰边界；背景或装饰线可直接留在父组件。按职责决定，不按固定节点数或“使用次数大于一”决定。

父组件协调整体布局/业务，子组件拥有内部节点及自身状态/动效；不要将所有 Controller/Transition 机械下移，跨区域协调仍由父层处理。新建节点使用语义名称，尺寸和局部 xy 为整数对，pivot/scale 可为小数。现有公共组件的名字和控制契约不因本规则被改写。

正常情况自行确定结构并继续执行；有实质歧义或要修改授权范围外的内容才询问。不要在制作失败后改计划来掩盖扁平堆叠、空壳组件或重复资源。

## 制作中：先子后父

先完成子组件，再通过真实资源引用组装父组件，重复实例引用同一个资源。MCP 已有 create_component/open_document/insert_object；若某种节点不能通过现有工具创建，先说明缺口，必要时在授权的源 XML 中补充，不把 Group、目录或整块截图冒充组件。

这是新 UI 的组织规则，不是自动提取旧节点的接口。既有界面若要改层级，须另行分析代码路径、relations、Controller/gear、Transition 和手动布局，并获得对应修改授权。

## 结构计划格式

在工作区约定的临时目录保存计划 JSON，不放进业务资源目录。root 和组件标识均使用相对 assets 的路径，不含 .xml；子目录必须保留。components 列出本次新建/改造组件的全部直接 displayList 节点，以便识别多余的扁平节点。未改动的复用组件可只作为引用目标，不必把其内部也写入计划。

```json
{
  "root": "demo/PopupDemo",
  "components": {
    "demo/PopupDemo": {
      "amount": {"component": "demo/parts/AmountDisplay"},
      "decoration": "graph"
    },
    "demo/parts/AmountDisplay": {
      "background": "graph",
      "label": "text",
      "value": "text"
    }
  }
}
```

字符串表示 XML 节点类型；独立组件必须用 {"component": "包/组件路径"} 声明，不能只写 "component"。重复项在多个实例名下声明同一个目标。这是本次需求的验收清单，不是生成器配置，也不应凭生成结果反向推导。

## 只读验收

使用当前 Skill 目录中的 scripts/check_component_structure.py，仅需要 Python 3.10+ 标准库：

```bash
python /ABSOLUTE/PATH/TO/fgui-agent-bridge/scripts/check_component_structure.py \
  --project /ABSOLUTE/PATH/TO/FAIRYGUI-PROJECT \
  --plan /ABSOLUTE/PATH/TO/SCRATCH/structure-plan.json
```

脚本不写工程、不生成 .agent 队列、不启动或唤醒编辑器。成功返回 JSON ok=true 和退出码 0；失败返回 ok=false、定位信息和退出码 1。

自动检查：

- 计划根组件与所有声明组件可达，package.xml 登记及源文件存在。
- 根据 pkg/src 的真实 ID 解析静态 component 引用，不能靠 fileName 伪装；跨包组件须导出，无循环引用。
- 声明组件的直接节点名/类型/归属完全符合计划，包括重复实例确实指向同一资源；缺失、重复、多余和空壳都会按计划被发现。
- 声明组件中 xy/size 整数对、局部 ID、基本 gear Controller 名称、relation/Transition 目标有效。

边界：只检查已保存的 UTF-8 基础分支源 XML，不验证未保存的编辑器内存；不解析分支覆盖、动态 Loader、List 模板或运行时注入，也不完整验证 gear 页、关系语义、动画播放或程序取子节点路径。涉及这些情况须专项核查，不能把脚本通过写成全部验证通过。复用组件只检查静态组件依赖，不强迫旧组件改名或重新组织。

“如何拆才合理”、Controller/Transition 的职责归属和视觉效果仍需 Agent 根据需求审查。计划漏掉新组件内部时也无法检测其空壳，故每个新建/改造组件都必须列入 components。

MCP 未保存修改先核对活动文档/对象树；未经授权不得为运行脚本而保存。允许保存且允许操作隔离编辑器时，保存后重开组件，核对结构、尺寸、显示状态和动效，再跑一次脚本。用户禁止编辑器操作或环境不可用时，明确标记 Editor/视觉未验证。

## 隔离样例与回归

Bridge 仓库 tests/fixtures/componentization 是独立的最小 .fairy 工程，不含用户截图或业务素材。它包含两个独立展示组件、跨包复用两次的奖励组件，以及直接保留在父层的装饰线。只用原生 graph/text，不要求图片依赖。

在 Bridge 仓库根目录执行：

```bash
uv run python .agents/skills/fgui-agent-bridge/scripts/check_component_structure.py \
  --project tests/fixtures/componentization \
  --plan tests/fixtures/componentization/structure-plan.json
uv run python -m unittest discover -s tests -p 'test_component_structure.py' -v
```

需要 Editor 实测时先复制样例到工作区约定的临时目录，再在获授权的隔离编辑器环境中打开副本；不打开/保存业务工程，不直接覆盖当前用户文档。静态回归通过只能证明检查器能识别样例结构，不能证明 AI 在所有新任务中都会自动正确拆分。

后续行为验收可用这个请求：制作一个包含总数展示、状态徽章、两个奖励项和一条装饰线的新面板，奖励项已有可复用资源。观察是否先列组件清单、复用资源、产出真实嵌套并执行结构验收；同时检查未为装饰线增加无职责包装。
