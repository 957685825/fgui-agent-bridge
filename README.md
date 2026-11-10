# FairyGUI Agent Bridge

通过 MCP (Model Context Protocol) 或 CLI，让 AI 编程 Agent（如 Cursor、Claude、Codex、VS Code 等）以结构化指令直接操作 FairyGUI Editor，实现自动拼 UI 界面、动效制作与一键发布。

- **版本**：`0.9.6`
- **队列协议**：`1.0`
- **已验证 FairyGUI Editor**：`6.1.4`
- **通信方式**：本地 JSON 队列 + MCP stdio

本仓库是由 `957685825` 持续维护的独立版本，基于 [Wilson520403 的原始工程](https://github.com/Wilson520403/fgui-agent-bridge)，保留原始 Git 历史和 MIT 许可证。这里的版本号只表示本维护分支，不代表已合并原仓库的全部后续功能。完整源码不压缩、不混淆，可直接修改和二次开发。

### 插件卸载清理（0.9.6）

通过入口导出的 `onDestroy` 解绑更新、工程和焦点事件，并恢复后台运行设置；不再直接赋值给加载阶段的 `PluginInfo.onDestroy`，该值会被宿主加载流程覆盖。事件解绑先于菜单清理，避免旧回调访问已销毁的 JsEnv。更新文件不会清除旧实例已经残留的委托，需要完全退出并重新打开 FairyGUI Editor。布局与游戏验收范围保持各自记录。

### 效果图对齐检查（0.9.5）

新增 `fgui_get_layout_snapshot(max_depth=12, include_image=True)` / CLI `layout`：读取当前组件的根画布四角与外接矩形、锚点、缩放/旋转/斜切、字体排版、Controller 当前页及设计图偏移。坐标通过宿主原生变换换算，消除画布平移/缩放与嵌套坐标混用；不切换、选择、保存或发布文档。

默认从组件显示对象获取原生预览（不是桌面截图），MCP 直接返回 PNG 图片内容。CLI `layout` 默认只读布局；`layout --output /ABSOLUTE/PATH/TO/SCRATCH/preview.png` 导出 PNG，父目录须存在且拒绝覆盖。原生 RGBA 仅转换为 PNG，不重画、裁切或替换美术素材；临时纹理在成功/失败后均释放，不增加图像依赖。

对照流程：先明确效果图原始画布尺寸、裁切原点、当前状态及参考图偏移，再用同一坐标系比较当前预览；记录具体元素的横纵偏差，修改后再次读取预览复查。文字框与图片布局框不等于可见字形或非透明边缘，不能仅靠 `x/y/width/height` 宣称视觉一致。设计图字段只报告编辑器已有绑定，不擅自导入或设置参考图。

限制：仅反映编辑器当前状态，不含游戏动态加载的图标、文本或逻辑；不自动识别设计图元素或生成匹配分数，也不自动移动组件。预览尺寸与根画布不一致时明确报错，不能默认为同尺寸直接套坐标。默认遍历深度 12，超过深度明确标记 `childrenTruncated`；节点上限 10000。图像要求整数尺寸、单边不超过 4096、面积不超过 4194304 像素，超限可 `include_image=False` 仅读布局。旧插件只在调用新工具时提示升级，不影响已有工具。

0.9.5 修复锚点造成的半画布坐标偏移，以及原生截图继承编辑器视口裁切的问题。坐标使用显示对象四角变换；截图先刷新离屏绘制状态，结束后恢复。多组件真实 Editor 验收记录见当前能力参考。更新全局插件后需重启 Editor，新增 MCP 工具需重启 MCP 服务。

### 编辑器输入状态保护（0.9.3）

Bridge 请求成功、失败或编辑器重新获得焦点后，等待窗口在前台且真实按键/鼠标均松开并连续空闲 0.5 秒，再通过宿主原生接口恢复一次指针和方向键输入状态。恢复不保存文档、不切换文档、不修改组件或当前选择；按住修饰键、多选及拖动期间会等待。定时心跳不会触发恢复。客户端等待较慢响应时，心跳正常则不再额外激活编辑器。

这是针对“检查后输入失常、按两次 Shift 可恢复”的输入状态保护，尚未证明编辑器漏收 KeyUp 的具体原因；自动化宿主替身验证不等于真实编辑器手工回归。更新全局插件后需重启编辑器，客户端更新需重启 MCP 服务。

> **说明**：Bridge 仓库与业务 FairyGUI 工程分开存放。轻量插件按当前用户全局安装一次，所有 FairyGUI 工程共用；在宿主 IDE 中可按需安装 Skill 提高 AI 操作准确率。

---

## 🏗️ 工作原理

```mermaid
graph LR
    Agent["AI Agent / IDE<br>(Cursor / Claude / Codex / VSCode)"] 
    -->|MCP stdio| Bridge["FairyGUI Agent Bridge<br>(Python CLI / MCP Server)"]
    Bridge -->|读写 .agent/ 队列| Plugin["Editor 全局插件<br>(~/.config/FairyGUI-Editor/plugins/agent-bridge)"]
    Plugin -->|FairyGUI API| Editor["FairyGUI Editor<br>(运行中的 UI 工程)"]
```

---

## 💡 AI 使用示例

安装完成后，在支持 MCP / Skill 的 AI 对话框中直接输入类似以下指令：

- `帮我制作一个登录界面，包含账号输入框、密码输入框和登录按钮`
- `根据蓝湖 MCP 导出的切图帮我拼出这个背包界面`
- `帮我给 MainMenu 界面的 StartBtn 添加一个弹出的缩放动画效果`
- `帮我检查当前界面的大图图集设置，保存并发布 Lobby 包`

> 若安装了 Skill，也可以通过 `/fgui-agent-bridge 帮我制作一个登录界面` 精准触发。

---

## 依赖要求

- Python `3.10+`
- [uv](https://docs.astral.sh/uv/) 包管理器
- FairyGUI Editor（推荐 `6.1.4`）

---

## 🚀 安装指南

### 方式一：AI 智能安装（推荐）

将下面的提示词发送给能够操作本地终端和文件的 AI 编程 Agent（如 Cursor、Claude Code、Codex 等）：

```text
请帮我在这台电脑上完整安装 FairyGUI Agent Bridge。你可以执行终端命令和编辑本地文件，请实际完成安装，不要只给操作说明。

源仓库：https://github.com/957685825/fgui-agent-bridge.git
插件安装范围：当前用户的 FairyGUI Editor 全局插件目录；
目标 FairyGUI 工程：仅用于 MCP 连接，优先从当前工作区自动查找 .fairy 文件；找不到或找到多个时停下来询问我。
目标代码仓库：当前工作区；
```

---

### 方式二：手动安装

#### 1. 克隆 Bridge 仓库并准备环境

```bash
git clone https://github.com/957685825/fgui-agent-bridge.git
cd fgui-agent-bridge
uv sync --frozen
```

#### 2. 安装 FairyGUI Editor 插件

运行同步脚本，将插件安装到当前用户的 FairyGUI Editor 全局插件目录：

```bash
uv run python scripts/sync_to_project.py --global-plugin --apply
```

仅在旧版 Editor 或隔离环境不允许全局插件时，才按单个工程安装：

```bash
uv run python scripts/sync_to_project.py \
  --project /ABSOLUTE/PATH/TO/FAIRYGUI-PROJECT \
  --apply
```

> **注意**：
> - 全局插件安装到 `~/.config/FairyGUI-Editor/plugins/agent-bridge/`，所有 `.fairy` 工程共用。
> - 安装完成后，**请重新启动 FairyGUI Editor**以加载插件。
> - 不要同时保留同 ID 的工程级插件副本，避免重复注册菜单和重复轮询队列。
> - 插件运行时目录 `.agent/` 会在工程内自动创建，请将其加入 `.gitignore`，不要提交到 Git。

#### 3. 配置 MCP Server

你可以根据所使用的 AI 客户端添加 MCP 配置。通用配置格式如下（可参考 [.mcp.example.json](.mcp.example.json)）：

```json
{
  "mcpServers": {
    "fgui": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/ABSOLUTE/PATH/TO/fgui-agent-bridge",
        "fgui-agent-mcp"
      ],
      "env": {
        "FGUI_PROJECT_PATH": "/ABSOLUTE/PATH/TO/FAIRYGUI-PROJECT"
      }
    }
  }
}
```

**常见客户端配置入口**：

- **Cursor**：在 `~/.cursor/mcp.json` 或项目根目录 `.cursor/mcp.json` 中粘贴上述配置。
- **Claude Desktop**：编辑 `claude_desktop_config.json`（macOS: `~/Library/Application Support/Claude/`，Windows: `%APPDATA%\Claude\`）。
- **Codex CLI**：
  ```bash
  codex mcp add fgui \
    --env FGUI_PROJECT_PATH=/ABSOLUTE/PATH/TO/FAIRYGUI-PROJECT \
    -- uv run --project /ABSOLUTE/PATH/TO/fgui-agent-bridge fgui-agent-mcp
  ```
- **VS Code (Cline / Roo Code)**：在扩展的 MCP Settings 中添加名为 `fgui` 的 stdio 服务。

#### 4. 验证连接

启动 FairyGUI Editor 并打开目标工程，然后执行：

```bash
uv run --project /ABSOLUTE/PATH/TO/fgui-agent-bridge \
  fgui-agent --project /ABSOLUTE/PATH/TO/FAIRYGUI-PROJECT ping
```

若返回 `{"status": "ok", ...}` 则表明连接成功。

---

### 可选：安装 Agent Skill

Skill 可以让 AI 更好地遵循 FairyGUI 的属性规范与动画约定。使用同步脚本可一键将 Skill 同步至目标业务代码仓库：

```bash
uv run python scripts/sync_to_project.py \
  --global-plugin \
  --skill-root /ABSOLUTE/PATH/TO/YOUR-CODE-REPOSITORY \
  --apply
```

或手动将 `.agents/skills/fgui-agent-bridge/` 目录复制到目标代码仓库的 `.agents/skills/` 目录下。

---

## 🔄 检查与拉取更新

当 Bridge 源仓库有功能更新或 Bug 修复时，可通过一条命令自动从源仓库安全拉取最新代码（`git pull --ff-only`）、同步 Python 环境（`uv sync`），并刷新全局插件与 Skill：

```bash
# 从源仓库拉取最新代码并同步全局插件与业务代码仓库 Skill
uv run python scripts/sync_to_project.py \
  --pull \
  --global-plugin \
  --skill-root /ABSOLUTE/PATH/TO/YOUR-CODE-REPOSITORY \
  --apply

# 或通过 CLI update 子命令执行
uv run fgui-agent update --pull --apply
```

> **提示**：
> - `fgui_status` 会自动比对当前 Bridge 服务端与 FairyGUI 编辑器内运行的插件版本，若版本不一致会在状态中返回 `updateWarning` 提示。
> - 若插件文件被更新，请**重新启动 FairyGUI Editor**以加载新版插件。

---

## 🛠️ 常用 CLI 指令

在 `fgui-agent-bridge` 仓库根目录下执行（也可以通过 `--project PATH` 指定工程）：

```bash
# 状态与连接检查
uv run fgui-agent status
uv run fgui-agent ping

# 查看工程与资源结构
uv run fgui-agent project
uv run fgui-agent packages
uv run fgui-agent items ViewHub
uv run fgui-agent open ViewHub ViewHubBtnItem
uv run fgui-agent active
uv run fgui-agent tree
uv run fgui-agent layout
uv run fgui-agent layout --output /ABSOLUTE/PATH/TO/SCRATCH/preview.png

# 历史与保存
uv run fgui-agent save
uv run fgui-agent undo
uv run fgui-agent redo

# 发布资源
uv run fgui-agent publish --scope active
```

**创建与导入资源**：

```bash
uv run fgui-agent create-component ViewHub NewPanel --width 1920 --height 1080
uv run fgui-agent import-image ViewHub /absolute/path/button.png
uv run fgui-agent import-font ViewHub /absolute/path/font.ttf
uv run fgui-agent import-sound ViewHub /absolute/path/click.mp3
uv run fgui-agent create-movieclip ViewHub Loading --frame /path/01.png --frame /path/02.png --fps 12
uv run fgui-agent create-button ViewHub NewButton --mode common
uv run fgui-agent upsert-transition '{"name":"fadeIn","frameRate":60,"items":[{"type":"Alpha","frame":0,"tween":{"duration":12,"start":0,"end":1}}]}'
uv run fgui-agent preview-transition play fadeIn
```

---

## 🧩 MCP 工具一览

| 类别 | 工具名称 | 功能描述 |
| :--- | :--- | :--- |
| **连接与定位** | `fgui_status`、`fgui_ping`、`fgui_use_project`、`fgui_get_project`、`fgui_list_packages`、`fgui_list_items` | 检查连接状态、动态切换工程、查看包列表与包内资源 |
| **文档与对象** | `fgui_open_document`、`fgui_get_active_document`、`fgui_get_tree`、`fgui_get_layout_snapshot`、`fgui_select_object`、`fgui_insert_object`、`fgui_set_property`、`fgui_remove_object` | 打开组件、查看对象树、选中元件、修改属性及增删显示对象 |
| **资源创建/导入** | `fgui_create_component`、`fgui_create_button`、`fgui_import_image`、`fgui_import_font`、`fgui_import_sound` | 新建组件/按钮，从本地绝对路径导入图片、字体与声音 |
| **MovieClip 序列帧** | `fgui_create_movieclip`、`fgui_get_movieclip`、`fgui_update_movieclip`、`fgui_remove_movieclip` | 从本地图片序列创建/更新序列帧动画（直接嵌入 `.jta`） |
| **Transition 动效** | `fgui_list_transitions`、`fgui_get_transition`、`fgui_upsert_transition`、`fgui_remove_transition`、`fgui_add_transition_item`、`fgui_update_transition_item`、`fgui_remove_transition_item` | 声明式增改整段过渡动效，或原子化修改特定轨道关键帧 |
| **动画预览** | `fgui_preview_animation` | 在编辑器中实时播放、暂停、停止、跳帧预览 Transition 或 MovieClip |
| **保存与事务** | `fgui_get_history`、`fgui_undo`、`fgui_redo`、`fgui_save_document`、`fgui_save_all`、`fgui_discard_document` | 属性与操作撤销/重做、保存文档或放弃全部未保存修改 |
| **发布** | `fgui_get_publish_settings`、`fgui_publish` | 查询发布设置、执行资源发布（支持活动包/指定包/全部包） |

---

## ⚙️ 关键机制与规范

### 换皮位置核对

换皮先固定主参考，复用旧皮肤结构、锚点、列表间距及动态奖励挂点。随 Skill 分发的只读脚本递归核对已保存基础 XML；任何未确认差异返回非零，有意变化需按精确值逐条写明原因。

```bash
python3 .agents/skills/fgui-agent-bridge/scripts/compare_skin_layout.py \
  --reference PATH/TO/OLD/FairyGUI.fairy --target PATH/TO/NEW/FairyGUI.fairy \
  --component ju_example/PopupExample
```

流程与确认格式见 [换皮位置复用与差异验收](.agents/skills/fgui-agent-bridge/references/reskin-layout.md)。工具不移动节点、不连接编辑器、不新增 Bridge Action；源检查不代替编辑器默认状态或游戏动态状态验收，插件无需因此重启。

### 百分比进度条验收

FTS 百分比条使用同一 0–100 显示值更新条与文字，默认平铺填充纹理。随 Skill 分发的 `scripts/check_progress_bars.py --project <FGUI_PROJECT> --component <PACKAGE/COMPONENT>` 只读检查有效实例值、数字百分比与填充资源；可重复指定组件。完整适用范围及边界见 [进度条制作与验收](.agents/skills/fgui-agent-bridge/references/progress-bars.md)。此项为 Skill 检查，不新增 Bridge Action，不替代原生预览或游戏验收。

### 组件化制作与结构验收（0.9.1）

新 UI 先按职责确定组件清单，查找已有资源，先制作子组件再组装父组件；独立功能区和重复项使用真实组件引用，普通装饰不强制包装。MCP instructions 提供入口约束，Skill 同时覆盖 MCP/CLI 和直接生成 XML；Group、未引用的空组件或一整张截图不算完成组件化。

制作前保存结构计划，完成后用随 Skill 分发的只读脚本检查已保存 XML。完整规则、计划格式和边界见 [组件化制作与验收](.agents/skills/fgui-agent-bridge/references/componentization.md)。

```bash
# 独立样例：功能区拆分、跨包重复复用，以及直接保留的普通装饰
uv run python .agents/skills/fgui-agent-bridge/scripts/check_component_structure.py \
  --project tests/fixtures/componentization \
  --plan tests/fixtures/componentization/structure-plan.json
uv run python -m unittest discover -s tests -p 'test_component_structure.py' -v
```

脚本只读、不连接或唤醒编辑器，检查引用/归属/循环依赖等结构；它不判断业务边界，也不能替代编辑器重开、视觉、动态资源或运行时验证。当前未增加“提取旧节点为组件”工具，不自动修改已有界面。

MCP instructions 需要重启对应 MCP 服务后重新加载；Skill 更新时需同步 references 和 scripts。测试代码只写临时副本，Editor 实测应使用样例副本且不得切换用户工作中的业务文档。组件化能力自 0.9.1 提供，无需为使用只读脚本改动业务工程。

### 1. Transition 动效规范
- **全轨道支持**：覆盖 `XY`、`Size`、`Pivot`、`Scale`、`Skew`、`Alpha`、`Rotation`、`Color`、`Animation`、`Visible`、`Sound`、`Transition`、`Shake`、`ColorFilter`、`Text`、`Icon` 全部原生轨道。
- **时间单位**：统一使用 FairyGUI frame 帧单位。
- **事务性**：整段声明式更新或关键帧原子操作均进入事务栈，支持 `fgui_undo` / `fgui_redo`。

### 2. MovieClip 序列帧机制
- 接收有序本地图片列表，通过 FairyGUI `AniData.ImportImages` 嵌入 `.jta` 文件，不会在包内产生多余的散图 `ui://`。
- FPS 范围 `1..255`，支持 Repeat Delay、每帧 Delay、Speed 与 Swing。
- 已有 MovieClip 的更新支持文件快照回退；全新创建/删除属于磁盘级操作，删除时需显式提供 `force=true` 且无外部引用。

### 3. 大图自动独立图集规则
- **规则触发**：图片分辨率达到 `1920×1080`，或任意一边达到 `2048`（2K）时，会自动标记为 FairyGUI `alone` 单独纹理集。
- **自动补齐**：通过 `fgui_import_image` 导入时即时生效；执行 `fgui_publish` 发布时还会自动扫描目标包并纠正历史大图配置，防止大图与小图碎图混排导致图集膨胀。

### 4. 编辑器内公共包同步
- FairyGUI 的“工具”菜单提供“同步公共包到当前工程”和“同步公共包到全部已接入工程”。
- 插件从当前工程向上定位最高层的 `assets/ju_common` 作为真源，同时支持 `ju_common_coins`。
- “同步当前工程”会安装或镜像更新公共包；“同步全部”只处理已经存在任一公共包的 `.fairy` 工程，并为这些工程补齐两个公共包，不会把公共包强行安装到无关工程。
- 同步采用临时目录切换，目标包会与真源完全一致并清除遗留文件；存在未保存文档时拒绝执行，完成后自动刷新当前工程。

---

## ❓ 常见问题与排错 (FAQ)

| 异常现象 | 可能原因 | 解决办法 |
| :--- | :--- | :--- |
| `ping` 提示超时或未连接 | 1. FairyGUI Editor 未启动<br>2. 目标工程未打开<br>3. 全局插件未安装或未生效 | 1. 打开 FairyGUI Editor 并加载目标工程；<br>2. 检查 `~/.config/FairyGUI-Editor/plugins/agent-bridge/main.js` 是否存在；<br>3. 重新启动 FairyGUI Editor；<br>4. 查看工程根目录 `.agent/bridge.log`。 |
| MCP 客户端找不到工具 | 1. MCP 配置中的绝对路径填写错误<br>2. 客户端未重启会话 | 1. 检查 MCP 配置文件中的 `fgui-agent-bridge` 和工程绝对路径；<br>2. 新建 Agent 对话或重启 IDE 重新加载 MCP。 |
| 导入资源失败 | 传入了相对路径或文件不存在 | 确保传入的图片/音频路径为**本地绝对路径**。 |
| 发布操作阻塞超时 | 发布正在进行中或发生了并发请求 | 发布期间部分读写操作会被锁定，请勿并发调用发布；等待完成后检查发布日志。 |

---

## ⚠️ 当前限制

- **兼容基线**：以 FairyGUI Editor `6.1.4` 为主要验证版本。
- **动画类型**：专注于 FairyGUI 原生 Transition 与 MovieClip，不支持 Spine、DragonBones、Loader3D、SWF 等第三方动画格式。
- **资源管理边界**：暂不支持通用包内资源的任意重命名与跨包移动；MovieClip 删除需带引用校验与 `force=true`。
- **平台环境**：macOS 已有部分真实 Editor 验收记录，具体范围见 [当前能力参考](.agents/skills/fgui-agent-bridge/references/current-capabilities.md)；Windows 及其他 Editor 版本尚未完整验证。

---

## 🔄 升级与同步

```bash
git pull
uv sync --frozen
uv run python scripts/sync_to_project.py --global-plugin --apply
```

> **提示**：也可以直接对你的 Agent 说 `“/fgui-agent-bridge 帮我更新”`。更新插件后重新启动 FairyGUI Editor 即可。只有当 Bridge 仓库路径或启动命令变更时才需更新 MCP 配置。

---

## 🛠️ 开发与维护

- **插件 TypeScript 源码**：`plugin/main.ts`
- **插件运行时编译文件**：`plugin/main.js`
- **Python MCP & CLI**：`src/fairygui_agent/`
- **Agent Skill**：`.agents/skills/fgui-agent-bridge/`
- **同步脚本**：`scripts/sync_to_project.py`

开发需要 Node.js / npm（编译插件和运行宿主回归），Python 依赖由 `uv.lock` 固定。`main.ts` 是插件源码，`main.js` 是随仓库交付的可读运行文件，必须由源码生成，不手工修改。Python、Skill 和检查脚本均以原始文本源码交付。

```bash
uv sync --frozen
npx -y -p typescript@5.4.5 tsc -p plugin/tsconfig.json --pretty false
uv run python -m unittest discover -s tests -v
git diff --check
```

每次维护先修改源码，再同步受影响的 MCP / CLI、测试、Skill、README 和 [更新记录](CHANGELOG.md)。插件行为变化时同步版本与编译文件；检查生成文件未漂移、回归通过后提交并推送本仓库。编辑器实测使用隔离工程，报告已验证和未验证范围；单个界面通过不代表全部皮肤通用。不要上传业务工程、美术资源、运行队列、日志、凭据、缓存或个人路径。欢迎通过本仓库的 Issue / Pull Request 参与修改。

> **维护注意**：修改 `plugin/main.ts` 后必须重新生成并提交 `plugin/main.js`；版本升级需同步修改 `plugin/package.json`、`pyproject.toml`、Python `__version__` 以及插件源码版本号。

---

## 🔗 相关生态推荐

- [蓝湖 MCP (lanhu-mcp)](https://github.com/dsphper/lanhu-mcp)：配合本工具，可以让 AI 编程 Agent 自动从蓝湖设计稿下载切图、导出标注，并直接在 FairyGUI 中拼装好 UI 界面并发布。

---

## 📄 许可证

[MIT License](LICENSE)
