---
name: fgui-agent-bridge
description: 制作、组装和验收 FairyGUI UI（含通过 MCP/CLI 或直接生成源 XML）时使用，指导按职责拆分和复用组件；也用于使用和维护独立 FGUI Agent Bridge 的连接、文档、资源、动画、发布、协议与同步能力。不因仅查看设计图而修改示例界面。
---

# FGUI Agent Bridge

## 目标与真源

本 Skill 面向独立 `fgui-agent-bridge` 仓库。该仓库是 Bridge、MCP、CLI 和 Skill 的唯一开发真源；FairyGUI 插件是当前用户的全局安装，业务工程只保留按需同步的 Skill 快照。

- FairyGUI 插件源码：`plugin/main.ts`
- FairyGUI 运行文件：`plugin/main.js`；修改源码后必须重新编译并一起提交
- 插件包与最小宿主类型：`plugin/package.json`、`plugin/types/`
- Python/MCP/CLI 真源：`src/fairygui_agent/`
- 版本必须同步：`plugin/package.json`、`pyproject.toml`、`src/fairygui_agent/__init__.py`、`plugin/main.ts`、`plugin/main.js`
- 工程文档真源：`README.md`
- 当前能力参考：[references/current-capabilities.md](references/current-capabilities.md)
- 业务工程同步入口：`scripts/sync_to_project.py`

若实现、README 和 Skill 不一致，先以代码和实际桥接响应核对，再在同一个改动中修正 README 与 Skill；不要凭旧摘要猜测 Action 或参数。

## 何时使用

- 使用 `fgui_*` MCP 工具或 `fgui-agent` CLI 操作 FairyGUI 组件。
- 查看包、资源、活动文档、对象树、对象 ID/路径、属性或撤销状态。
- 修改组件属性、插入/删除已有 `ui://` 资源、保存、放弃、撤销或重做。
- 发布当前包、指定包或全部包，或检查发布设置。
- 检查 Bridge/插件版本一致性，或从源仓库拉取最新代码并同步到目标工程。
- 修改插件、MCP、CLI、版本、协议、白名单、队列语义、同步脚本或 README。
- 在 FairyGUI Editor 的“工具”菜单同步当前工程或全部已接入工程的 `ju_common` / `ju_common_coins` 公共包。

## 使用工作流

### 0. 检查更新与同步（按需）

- 当用户要求“检查更新”、“拉取最新 Bridge 版本”，或 `fgui_status` 返回 `versionMatch: false` / 协议不兼容提示时：
  1. 运行 `uv run python scripts/sync_to_project.py --pull --global-plugin --skill-root PATH --apply`（或 `uv run fgui-agent update --pull --apply`）；
  2. 若插件更新，提醒用户重新启动 FairyGUI Editor 生效。

### 1. 连接与定位

#### 全局插件预检

- 操作任意 `.fairy` 工程前，先解析唯一目标工程，再检查当前用户全局插件 `~/.config/FairyGUI-Editor/plugins/agent-bridge/`，不能用另一个工程的 `plugins/agent-bridge/` 代替。
- 全局插件缺失时，在独立 Bridge 根目录运行 `uv run python scripts/sync_to_project.py --global-plugin --apply`。版本不匹配时用同一命令更新，并重新启动 FairyGUI Editor。
- 全局插件一次安装后服务所有工程；不要再为每个工程复制插件。遗留的同 ID 工程级副本应在确认全局插件可用后移除，避免重复注册菜单或轮询同一队列。
- 重新启动后执行 `fgui_use_project → fgui_ping → fgui_get_project`；请求写入队列不代表编辑器已经连接成功。
- `.agent/` 仍在当前 FairyGUI 工程内生成，只是运行时队列，不是插件安装目录，也不纳入 Git。

1. 使用 `fgui_status` 查看当前会话是否已选择工程、编辑器是否在线、插件版本是否匹配以及心跳年龄；它不会唤醒编辑器。
2. 工程未选择时调用 `fgui_use_project`，参数可为 `.fairy` 文件、FairyGUI 工程目录或包含 `FairyGUI/FairyGUI.fairy` 的仓库目录。
3. 需要唤醒或验证编辑器时调用 `fgui_ping`。不要把“请求已写入队列”当作 FairyGUI 已完成。
4. 不知道包名时先 `fgui_list_packages`；不知道资源时用 `fgui_list_items`。
5. 打开组件后先确认活动文档，再读取对象树。修改优先使用稳定对象 ID，其次对象路径；只有名称唯一时才使用名称。

### 2. 创建、修改和保存

- 新建组件使用 `fgui_create_component`，明确包、目录、名称、宽高、导出状态和冲突策略。
- 图片、字体与声音导入使用绝对本地路径（`fgui_import_image` / `fgui_import_font` / `fgui_import_sound`）；`replace` 是磁盘覆盖，不能由文档放弃回滚。
- 动画编辑先用 `fgui_list_transitions` / `fgui_get_transition` 读取，再用 `fgui_upsert_transition` 进行整段声明式更新，或用关键帧原子工具局部修改；时间单位是 frame。全部原生 Transition 轨道均使用类型化 JSON。
- MovieClip 用 `fgui_create_movieclip` 的有序绝对图片路径创建，或通过 `fgui_update_movieclip` 更新帧与播放参数；帧由 FairyGUI 嵌入 `.jta`，不会自动生成逐帧图片 `ui://` 资源。已有 MovieClip 更新/替换可 Agent undo/redo，全新创建和删除不可逆。
- 用 `fgui_preview_animation` 播放、暂停、停止、跳帧或查询 Transition/MovieClip 预览状态。预览不保存，不能把预览状态描述为资源默认属性。
- 按钮状态图顺序固定为 `up/down/over/selectedOver/disabled/selectedDisabled`，非空值必须是工程内图片 `ui://` URL。
- 属性修改（如 `text`、`icon`、`font` 等白名单属性）进入 Agent 属性事务栈；结构创建、插入和删除没有完整结构快照撤销。
- 保存使用 `fgui_save_document` 或 `fgui_save_all`；放弃全部未保存修改使用 `fgui_discard_document`。

#### 外部源文件同步（0.9.7 起）

- 插件会在文件写入稳定后自动刷新当前工程 `assets`，资源树通常等待约 2–4 秒，当前画布再等一轮，其他标签页切回后自动检查重载；随后重新读取核验，不能仅凭磁盘写入成功宣称编辑器已加载。
- 任意未保存文档、模态窗口、发布、队列任务或真实输入期间推迟刷新；不要为触发刷新擅自保存或放弃用户修改。用户处理完未保存修改后自动重试。
- 首次加载只建立基线；升级插件需要完整重启 Editor。自动刷新不等于发布或游戏加载，也不扩大业务修改授权。

### 2.1 先设计组件结构，再制作 UI

本节适用于新建/组装 UI，包括 MCP、CLI 和直接生成源 XML；仅分析截图或讨论方案不授权修改示例界面。局部改字、改位置不应顺带重构已有组件。

- 开工前先查同包和公共包中的同类资源，再列简短组件清单：名称、职责、内部元素、父子关系、复用目标。按独立展示/交互职责、整体状态或动效边界拆分；完整功能单元即使只使用一次，也可以独立维护。不要按节点数机械拆分，也不要给每张装饰图套空壳组件。
- 重复项引用同一个组件资源；已有公共组件优先复用，不复制或重画。普通装饰、背景等没有独立职责的节点可以留在父组件。
- 先制作/复用子组件，再引用它们组装父组件。父组件负责整体布局和业务协调；子组件管理内部布局及自身 Controller/Transition，跨区域协调才留在父层。内部使用局部坐标和语义名称；遵循目标工程命名约定，没有约定时组件/XML 使用 PascalCase，包使用 lowercase_snake_case。
- 独立组件必须是 package.xml 登记的组件资源，并由父组件的 component 节点实际引用。Group、目录、整块截图或只创建未使用的空组件不算完成拆分；动态金额/文案不能烘焙进截图。
- 制作前将清单中的节点归属保存为简短结构计划；完成后对照计划检查实际资源引用及子节点归属。读取 [组件化制作与验收](references/componentization.md)，使用随 Skill 分发的只读检查脚本。不要事后把计划改成扁平结构来迁就错误产物。
- 结构不符时只修正本次授权范围内的新增产物并重验；涉及既有组件、代码引用或手工布局时先说明影响，不自动提取或重构。工具能力不足时明确缺口，不降级为把所有节点堆在根组件。
- MCP 未保存修改先读取对象树验收；仅在获得保存授权后保存并检查源 XML。有编辑器验证条件且已获操作授权时，重新打开并核对显示、状态和动效。源 XML 通过不等于编辑器或视觉通过，不为跑检查擅自保存、发布、切换用户文档。
- 默认自行执行已明确的拆分，不逐个组件要求用户确认；只有需求边界不明确或需要扩大修改范围时询问。交付报告拆分/复用结果、结构检查、编辑器复查及未验证项。

### 2.2 效果图对齐与视觉复查

- 先确认效果图的原始画布尺寸、截图裁切原点/缩放、目标组件尺寸及 Controller 状态；信息不全时明确假设，不把局部截图直接当完整根画布。
- 使用 0.9.5 或更高版本插件进行布局对照；该版本修复根/子节点锚点偏移和编辑器视口裁切，预览尺寸不符时会报错。
- 获得编辑器读取/预览授权后，使用 `fgui_get_layout_snapshot(max_depth=12, include_image=True)` 获取当前组件原生 PNG、根画布坐标、字体/锚点、Controller 当前页及已有设计图偏移；此工具不切换文档、不保存、不修改 UI。只有截图/讨论不授权打开或改动既有组件。
- 优先采用宿主换算的 `rootCorners` / `rootBounds`，不要手工累加嵌套 x/y，也不要混用编辑器视口像素与组件像素。PNG 的实际尺寸见 `preview`；与 `canvas` 不一致时先查截图范围，不能直接按同尺寸叠合。设计图 `offsetX/offsetY` 也须参与参考原点换算。
- 结合预览中的可见边缘测量目标位置，记录本轮具体元素横纵偏差；图片透明留白、文字笔画/描边、字体度量和文本框须分别核对。`rootBounds` 是变换后的布局外接框，不能作为字形或非透明边缘的证明。
- 在授权范围内修改后，再读取同状态、同坐标系预览对照效果图。背景、主要锚点、文字基线和重复项间距均需复查；未做视觉检查时明确报告，不以 XML/对象树检查代替。不为对齐顺带修改业务、动态奖励资源或用户手工布局。
- 交付前逐处放大核对顶部遮盖、左右贴边、底部收边、圆角及组件拼接，特别检查背景、边框、滚动内容和末项之间的漏底、细缝、重叠与双线；检查列表首端、中间、末端及相关状态。以用户认可后的手工布局为本轮基准，只改测量确认的差异；界面专用偏移不能推广为通用补偿，通用修正需回归多个代表界面。
- 深度截断由 `childrenTruncated` 标记，必须补查涉及的子层。超大画布可 `include_image=False` 仅读布局；原生图像单边上限 4096、面积上限 4194304 像素，节点上限 10000。
- CLI `layout` 仅读元数据；`layout --output /ABSOLUTE/PATH/TO/SCRATCH/preview.png` 将原生预览写入指定本地暂存路径（不覆盖）。没有自动识图对齐或匹配分数；运行时动态内容和真实游戏仍需另外验收。

### 2.3 换皮必须核对旧皮肤位置

- 换皮开始时读取 [换皮位置复用与差异验收](references/reskin-layout.md)。用户指定参考优先；否则比较同族至少两个皮肤，固定一个主参考，先核对实际运行组件及动态布局责任。
- 默认复用结构、锚点、列表间距、动态奖励挂点和状态契约；美术差异引起的位置调整必须有测量依据。保留用户手工布局，不凭效果图整体重摆。
- 使用随 Skill 分发的 `scripts/compare_skin_layout.py` 只读比较主参考与目标的已保存 XML；未确认差异必须逐条修正或用精确值及原因记录。此工具不新增 Bridge Action，不自动对齐，不改编辑器。
- 分别检查源布局、编辑器默认列表/状态与游戏动态列表/奖励/进度/多语言。只有源检查通过时不能宣称整个换皮已验收；未保存文档、分支覆盖、图片可见边缘和游戏布局另行核对。

### 2.4 进度条、百分比与计数

- 制作或修改进度条时读取 [进度条制作与验收](references/progress-bars.md)，核对真实目标、数值来源、取整/钳制以及填充纹理的实际资源引用。条与百分比文字共用一个显示值；计数独立显示。
- FTS 客户端默认百分比范围 0–100、max=100、填充图片平铺；其他项目按本项目约定，不能把 FTS 默认扩展到原始计数条。比较多个现有 UI，不只照单个参考。
- 对适用组件运行 `scripts/check_progress_bars.py`，实例覆盖与默认文字不一致、非平铺或资源缺失均须处理。源检查不代替编辑器/游戏验收；至少覆盖 0、低于 1%、30%、100% 与超目标输入，不为检查保存或发布用户文档。

### 3. 发布

1. 先调用 `fgui_get_publish_settings` 确认输出目录、格式、图集、代码生成和包级覆盖。
2. 明确发布范围：`active`、`packages` 或 `all`。
3. 再调用 `fgui_publish`，按需设置保存、描述文件、分支和超时。
4. 发布前会自动扫描目标包：达到 `1920×1080` 或任一边达到 `2048` 的图片会设置 FairyGUI `alone` 纹理集，确保大图单独打图集、不与小图混排；发布响应会返回实际修正清单。
5. 读取实际输出目录、扩展名、耗时和文件变更清单；文件清单不等于 Git 内容一定变化。
6. 发布期间部分读写 Action 会被阻塞；遇到超时先检查状态和 `.agent/bridge.log`，不要并发重复发布。

### 4. 公共包同步菜单

- “工具 → 同步公共包到当前工程”从当前工程向上定位最高层 `assets/ju_common` 真源，并将 `ju_common`、`ju_common_coins` 镜像到当前工程；缺失包会自动安装。
- “工具 → 同步公共包到全部已接入工程”扫描真源目录下的 `.fairy` 工程，只处理已经存在任一公共包的工程，并为这些工程补齐两个公共包；完全没有公共包的工程保持不变。
- 镜像同步会移除目标包中真源不存在的遗留文件；插件先写临时目录再切换，失败时恢复旧目录。当前工程有未保存文档时必须先保存，不得强制覆盖。
- 完成后插件调用 FairyGUI 原生刷新。公共包真源工程本身不会复制到自己。

## CLI 约定

在独立仓库根目录使用：

```bash
uv sync --frozen
uv run fgui-agent --project /ABSOLUTE/PATH/TO/FAIRYGUI-PROJECT status
uv run fgui-agent --project /ABSOLUTE/PATH/TO/FAIRYGUI-PROJECT ping
uv run fgui-agent --project /ABSOLUTE/PATH/TO/FAIRYGUI-PROJECT packages
uv run fgui-agent --project /ABSOLUTE/PATH/TO/FAIRYGUI-PROJECT tree
uv run fgui-agent --project /ABSOLUTE/PATH/TO/FAIRYGUI-PROJECT layout
```

全局参数 `--project`、`--editor`、`--timeout` 必须位于子命令前。`call` 只用于调试原始 Action，不替代正式 MCP 工具。

## 安装位置与安装方式

面向使用者的 `README.md` 同时提供“AI 快速安装（提示词安装）”和“人类安装”。AI 安装必须实际执行并验证下述同一套安装步骤，不能只返回命令说明。

安装边界必须明确区分：

- FairyGUI Editor 插件安装到当前用户的全局目录 `~/.config/FairyGUI-Editor/plugins/agent-bridge/`，所有工程共用。
- MCP/CLI 始终从独立 Bridge 仓库或已安装的 Python 工具环境运行，不放入 FairyGUI 工程。
- Skill 可选安装到 Codex 操作的目标代码仓库 `.agents/skills/fgui-agent-bridge/`。
- `.agent/` 是目标 FairyGUI 工程生成的运行时队列，不是安装文件，也不纳入 Git。

普通使用者通过同步脚本安装全局插件：

```bash
uv run python scripts/sync_to_project.py --global-plugin --apply
```

`--project PATH` 和 `--choose-project` 仅保留给旧版 Editor 或必须隔离插件的环境；常规安装不要生成工程级副本。

在独立 Bridge 仓库准备 Python 环境：

```bash
uv sync --frozen
```

注册 Codex MCP 时同时保留 Bridge 仓库路径与目标 FairyGUI 工程路径：

```bash
codex mcp add fgui -- \
  uv run \
  --project /ABSOLUTE/PATH/TO/FGUI-AGENT-BRIDGE \
  fgui-agent-mcp \
  --project /ABSOLUTE/PATH/TO/FAIRYGUI-PROJECT/FairyGUI.fairy
```

Skill 按需复制到目标代码仓库：

```bash
mkdir -p /ABSOLUTE/PATH/TO/TARGET-REPOSITORY/.agents/skills
cp -R .agents/skills/fgui-agent-bridge \
  /ABSOLUTE/PATH/TO/TARGET-REPOSITORY/.agents/skills/
```

完成安装后先执行低风险读取：`status → ping → project → packages`，不要以创建、导入、保存或发布作为首次连接测试。

### 插件生命周期维护

- 更新/工程/焦点等 C# 事件必须在入口导出的 `onDestroy` 中用原函数解绑；不要遍历 `allPlugins` 后直接写 `PluginInfo.onDestroy`，宿主会在入口执行后用模块导出覆盖生命周期字段。
- 先解绑事件和恢复运行设置，再清理菜单。回归应覆盖加载阶段列表中尚无自身、卸载后焦点变化及重复加载；宿主替身通过不替代真实 Editor 生命周期检查。
- 0.9.6 修复卸载钩子未导出的问题。旧实例中的残留委托需要完全退出 Editor 才能清除，不把文件同步成功当作当前实例已生效。

### 同步与更新脚本

`scripts/sync_to_project.py` 默认 dry-run，必须传入 `--apply` 才写入；支持 `--pull` 自动从源仓库拉取最新代码并同步 Python 环境：

```bash
# 安装或更新当前用户的全局插件
uv run python scripts/sync_to_project.py --global-plugin --apply

# 从源仓库拉取更新，并同步全局插件与 Skill
uv run python scripts/sync_to_project.py \
  --pull \
  --global-plugin \
  --skill-root /ABSOLUTE/PATH/TO/TARGET-REPOSITORY \
  --apply

# 或通过 CLI update 命令执行
uv run fgui-agent update --pull --apply
```

`--global-plugin`、`--project` 与 `--choose-project` 互斥。脚本不创建 Git 元数据、不复制缓存、不删除目标目录中的其他文件。若更新了插件文件，需重新启动 FairyGUI Editor 加载。

## 开发与变更同步

Bridge 运行功能变动必须在同一变更中完成以下事项。仅更新 Skill 规范或离线检查脚本时，同步其文档、测试与安装副本即可，不改插件协议版本或要求用户重启：

1. 更新实现；修改 `plugin/main.ts` 后重新编译 `plugin/main.js`。
2. 同步 `plugin/package.json`、`pyproject.toml`、`__init__.py` 和 Bridge 常量版本。
3. 更新 README、当前能力参考和本 Skill。
4. 核对插件 capability、Action 分发、Python MCP 装饰器、CLI parser 与文档。
5. 检查同步脚本仍只写入受管理文件，默认保持 dry-run。
6. 确认没有提交 `.agent/`、`.venv/`、`__pycache__/`、`node_modules/`、`main.js.map` 或个人绝对路径。

推荐静态检查：

```bash
uv lock
uv sync --frozen
uv run python -m compileall -q src scripts
uv run fgui-agent --help
uv run fgui-agent-mcp --help
npx -y -p typescript@5.4.5 tsc -p plugin/tsconfig.json --pretty false
git diff --check
```

若 FairyGUI Editor 在线，再使用隔离工程副本验证 `fgui_status → fgui_ping → fgui_get_project`。创建、导入或发布 API 变更应在隔离副本中验证写操作；未做真实 Windows 验证时必须明确标注。

## 安全边界

- 0.9.3 在请求完成（含失败）或窗口重新获得焦点后安排一次输入状态恢复；仅在前台、真实按键和鼠标均松开且连续空闲 0.5 秒后调用宿主原生接口。不得改为每帧/每次心跳重置，也不得在用户拖动或按住修饰键时强制松键。心跳正常的慢请求不额外激活编辑器。该保护尚不等于已确认漏收 KeyUp 的根因，交付时区分宿主替身检查与真实编辑器验收。

- `.agent/` 是目标 FairyGUI 工程的运行时队列与日志，不纳入 Git。
- 同一请求不要重复写入；响应必须按请求 ID 匹配。
- 图片、声音、MovieClip 图片序列导入和发布是磁盘写入，执行前确认目标和冲突策略。Transition 声明式/关键帧修改与已有 MovieClip 更新/替换可由 Agent undo/redo 回退；全新资源创建、声音/图片导入和删除不能。
- MovieClip 删除即使传 `force=true` 也会执行引用检查；仍被组件使用时必须先移除引用。
- 不允许删除根组件；不要把 `discard`、`undo` 和 `save` 混为同一语义。
- 根组件点击穿透使用可序列化的 `opaque=false`；不要把无法持久化的根 `touchable` 宣称成功。
- 不在代码、配置、文档或示例中提交个人绝对路径、密钥或真实 MCP 配置。

## 输出要求

完成操作或维护任务时报告：

- 涉及的包、文档、对象或文件；
- 是否保存、发布、放弃或同步，以及作用范围；
- 执行了哪些静态检查、MCP 握手和编辑器验证；
- 哪些真实平台或环境仍未验证。
