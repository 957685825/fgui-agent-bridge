# Agent Bridge 当前能力参考

> 这是独立 `fgui-agent-bridge` 仓库在 2026-11-10 的能力快照。功能变动时必须同步本文件，并以源码实际签名为最终依据。

## 版本与通道

- Bridge 版本：`0.9.7`
- FairyGUI 插件 ID：`com.fgui.agent-bridge`
- 代码真源：独立公开仓库；插件安装在 `~/.config/FairyGUI-Editor/plugins/agent-bridge/`，业务工程只按需安装 Skill 快照
- 队列协议：`1.0`
- FairyGUI Editor 基线：`6.1.4`
- MCP 工具数：39，其中 37 个对应 Bridge Action，`fgui_status` 和 `fgui_use_project` 为 Python 本地能力
- 传输：MCP stdio；底层为目标工程 `.agent/` 下的本地 JSON 文件队列
- 运行时目录：`.agent/requests`、`.agent/processing`、`.agent/responses`、`.agent/status.json`、`.agent/bridge.log`
- `.agent/` 是运行时数据，不纳入 Git
- 0.9.3 输入状态保护：请求成功/失败或窗口重新获得焦点后，等前台且真实按键/鼠标释放并空闲 0.5 秒，调用宿主原生接口恢复一次输入；不改文档、选择或焦点，不在心跳中反复恢复。慢响应期间心跳正常则不再额外激活编辑器。真实编辑器手工复现尚待验收，不能据此宣称漏收 KeyUp 的根因已证实。

- 0.9.5 修复布局快照锚点偏移和原生预览继承编辑器视口裁切；坐标基于显示对象变换，离屏绘制刷新后截图，成功/失败均恢复裁切状态。真实 Editor 多组件回归与自动化结果见下表。

## MCP 工具签名

以下签名以 `src/fairygui_agent/mcp_server.py` 为准；工具参数使用 Python snake_case，桥接请求内部映射为 camelCase。

| 工具 | 主要参数 | 用途 |
| --- | --- | --- |
| `fgui_status` / `fgui_ping` / `fgui_use_project` | — / — / `project_path` | 读取状态、握手或选择工程 |
| `fgui_get_project` / `fgui_list_packages` | 无 | 读取工程或包 |
| `fgui_list_items` | `package_name`, `item_type?` | 列出包内资源 |
| `fgui_open_document` | `package_name`, `item_name` | 打开已有组件文档 |
| `fgui_create_component` | 包、名称、尺寸、目录、扩展、导出、重名策略 | 新建组件资源 |
| `fgui_import_image` / `fgui_import_font` / `fgui_import_sound` | 包、绝对路径、目录、名称、冲突策略、导出 | 导入或替换本地资源 |
| `fgui_create_button` | 包、名称、尺寸、模式、状态图片、目录 | 创建 Common/Check/Radio 标准 Button |
| `fgui_create_movieclip` | 包、名称、有序 `frame_paths`、FPS、延迟、Swing、目录 | 从本地图片序列创建/替换 MovieClip |
| `fgui_get_movieclip` / `fgui_update_movieclip` / `fgui_remove_movieclip` | MovieClip 资源定位；更新可传帧、FPS、Speed、延迟、Swing | 读取、更新或显式强制删除 MovieClip |
| `fgui_get_active_document` / `fgui_get_tree` | 无 / `max_depth` | 读取活动文档或对象树 |
| `fgui_get_layout_snapshot` | `max_depth=12`, `include_image=True` | 当前根画布坐标、字体、Controller、设计图与原生 PNG；不切换或保存，详见 Skill 2.2 |
| `fgui_select_object` / `fgui_set_property` | ID、路径或唯一名称 | 选择对象或修改白名单属性 |
| `fgui_insert_object` / `fgui_remove_object` | 资源 URL、坐标 / 目标 | 插入已有资源或删除非根对象 |
| `fgui_list_transitions` / `fgui_get_transition` | 无 / `name` | 读取当前组件的 Transition |
| `fgui_upsert_transition` / `fgui_remove_transition` | 类型化 `transition` / `name` | 声明式创建、完整替换或删除 Transition |
| `fgui_add_transition_item` / `fgui_update_transition_item` / `fgui_remove_transition_item` | `name`、类型化 `item`、`item_index` | 原子增删改 Transition 关键帧 |
| `fgui_preview_animation` | `kind`, `operation`, Transition 名称或 MovieClip 目标 | 播放、暂停、停止、跳帧或查询状态，不保存 |
| `fgui_undo` / `fgui_redo` / `fgui_get_history` | 无 | Agent 事务优先的回退和历史读取 |
| `fgui_save_document` / `fgui_save_all` / `fgui_discard_document` | 无 | 保存、全部保存或放弃当前文档修改 |
| `fgui_get_publish_settings` / `fgui_publish` | 包名? / 范围、包、分支、保存策略 | 读取或执行现有发布配置；发布前自动将 1920×1080/2K 级大图设置为 FairyGUI `alone` 纹理集，避免与小图混排 |

## 动画语义

### Transition

- 使用类型化 JSON；时间单位为 FairyGUI frame，`frameRate` 决定实际播放速度。
- 支持全部 FairyGUI 原生轨道：`XY`、`Size`、`Pivot`、`Scale`、`Skew`、`Alpha`、`Rotation`、`Color`、`Animation`、`Visible`、`Sound`、`Transition`、`Shake`、`ColorFilter`、`Text`、`Icon`。
- Tween 支持持续帧数、缓动、重复、Yoyo、路径和自定义缓动数据；路径读取为 `{encoded, points}`，再次写入应优先复用 `encoded`，避免丢失 Editor 自动生成的端点或控制点。
- `fgui_upsert_transition`、关键帧原子编辑和删除均为一次 Agent 动画事务，可用 `fgui_undo` / `fgui_redo` 整步回退；若文档动画已被外部操作改写，回退会拒绝覆盖。
- `Sound` 轨道只接受工程内声音类型的 `ui://` URL；可先使用 `fgui_import_sound` 导入。嵌套 `Transition` 必须已存在于同一组件。
- `playTimes` 是 Editor 运行态信息，不序列化到组件 XML；持久播放次数应使用 `autoPlayRepeat` 或轨道自身的播放次数字段。
- `fgui_preview_animation(kind="transition")` 只操作 Editor 预览。播放状态、暂停和 Timeline 跳帧不写入资源文件。

### MovieClip

- `fgui_create_movieclip` 接收有序绝对图片路径；FairyGUI 原生 `AniData.ImportImages` 将帧嵌入 `.jta`。不会为各帧额外创建包内图片 `ui://` 资源。
- 可设置 `fps` (`1..255`)、`speed`、`repeat_delay` (`0..255` 额外延迟帧)、`swing` 和每帧 `frame_delays` (`0..255`)。
- 创建/更新响应包含本次 `frameSources` 与 `resourceChanges`；重新读取 `.jta` 时只返回可持久读取的帧索引、矩形和延迟，不返回原始本地路径。
- `fgui_update_movieclip` 传入 `frame_paths` 时替换完整帧序列；所有图片必须存在且为 FairyGUI 支持的图片格式。失败时恢复原 `.jta`、尺寸和导出设置；全新创建失败会清理本次新建资源。
- 已有 MovieClip 的 `update` 与冲突策略 `replace` 记录文件快照，可用 Agent undo/redo 回退；全新创建和删除不进入可逆资源生命周期历史。
- `fgui_preview_animation(kind="movieclip")` 支持 `play`、`pause`、`stop`、`seek`、`next`、`previous`、`status`；仅改变编辑器内对象预览状态，不保存。
- MovieClip 创建/更新、图片序列处理和声音导入均可能写磁盘；它们不由 `fgui_discard_document` 自动回滚。删除 MovieClip 必须显式 `force=True`，且存在组件引用时拒绝删除。

## 创建、导入、保存与发布

- 包内目录输入可写 `Folder/SubFolder`，桥接统一为 `/Folder/SubFolder/`；缺失目录可按参数创建。
- 图片、字体和声音导入支持 `error`、`auto_rename`、`replace`。`replace` 只允许相同资源类型。
- 所有本地导入路径均必须是绝对路径；导入和替换是磁盘写入。
- `fgui_save_document` / `fgui_save_all` 保存文档和包改动；`fgui_discard_document` 只放弃当前文档未保存改动。
- 发布前先用 `fgui_get_publish_settings`。发布期间桥接会阻止资源、动画及文档写操作。

## 编辑器公共包同步

- 全局插件一次安装后服务当前用户打开的所有 FairyGUI 工程；工程内不再保留同 ID 插件副本。
- “工具”菜单在每个工程中提供当前工程和全部已接入工程两个同步入口。
- 公共包真源按当前工程祖先目录中最高层的 `assets/ju_common` 定位；同步包为 `ju_common` 与存在时的 `ju_common_coins`。
- 当前工程同步会安装缺失包；全部同步只处理已存在任一公共包的 `.fairy` 工程，并为这些工程补齐两个公共包。
- 每个目标包通过同级临时目录完整复制后切换，真源不存在的目标遗留文件会被清理；切换失败时恢复原目录。
- 有未保存文档时拒绝同步；成功后执行 FairyGUI 工程刷新。该能力是 Editor 菜单能力，不新增 MCP 工具或 Bridge Action。

## 组件化制作与只读结构验收

- 新建 UI 先按职责列组件清单、查找复用资源，再先子后父组装；MCP、CLI 和直接生成 XML 均适用。仅讨论的截图和既有界面不因本规范自动进入修改范围。
- 组件化细则与计划格式见 [componentization.md](componentization.md)。Skill 附带 scripts/check_component_structure.py，只读核对已保存基础分支 XML 与制作前计划，不新增 MCP 工具或 Bridge Action。
- 检查真实组件引用、节点归属、计划可达性、重复资源复用、循环引用、局部基础引用与整数坐标；不自动决定拆分边界，不代替 Editor/视觉或运行时验收。
- 测试样例位于 Bridge 仓库 tests/fixtures/componentization；禁止用业务界面作为写操作测试目标。未实现旧节点自动提取为组件。

## 换皮布局差异检查

- Skill 附带 `scripts/compare_skin_layout.py`，使用参考工程、目标工程及同路径根组件，只读比较基础 XML 的结构、坐标、锚点、列表、排版和状态属性；递归解析组件实例、列表项及滚动条的真实 ID 引用。
- 未确认差异、失效确认或读取错误返回非零；有意差异需精确记录原值/新值及理由。图像资源替换、文案和纯颜色不作位置差异；不自动改布局、识图或推断最终状态位置。
- 完整流程、命令及范围见 [reskin-layout.md](reskin-layout.md)。源检查、Editor 默认状态与游戏动态状态分别验收；工具不连接 Editor，不增加 MCP/CLI Action，插件协议和版本不变。

## CLI 映射

正式子命令包括：

- 基础：`status`、`ping`、`project`、`packages`、`items`、`open`、`active`、`tree`、`layout`（`--output PNG` 可选）、`select`、`set`、`insert`、`remove`
- 资源：`create-component`、`create-button`、`import-image`、`import-font`、`import-sound`、`create-movieclip`、`get-movieclip`、`update-movieclip`、`remove-movieclip`
- Transition：`transitions`、`get-transition`、`upsert-transition`、`remove-transition`、`add-transition-item`、`update-transition-item`、`remove-transition-item`
- 预览：`preview-transition`、`preview-movieclip`
- 保存发布：`save`、`discard`、`save-all`、`history`、`undo`、`redo`、`publish-settings`、`publish`
- `call` 仅调试原始 Action，不替代正式命令。

全局参数 `--project`、`--editor`、`--timeout` 必须置于子命令前。

## 关键限制

- 兼容基线是 FairyGUI Editor `6.1.4`；其他 6.x 尚未完成真实环境矩阵验证。
- 本版本不包含 Spine、DragonBones、Loader3D、SWF 或运行时游戏代码层动画控制。
- 通用包资源的删除、移动、重命名仍未开放；只提供带 `force` 和引用检查的 MovieClip 删除。
- Windows 尚未完成真实环境端到端验证。

## 文件变动同步矩阵与对照检查

| 变动文件/区域 | 需要同步 |
| --- | --- |
| `scripts/sync_to_project.py` 插件安装目标 | README、本 Skill、CLI `update` 与安装回归测试 |
| Skill 组件化规则、references/componentization.md、scripts/check_component_structure.py | MCP instructions、README、本能力参考、结构回归样例与测试；同步 Skill 时包含 references/scripts |
| Skill 换皮规则、references/reskin-layout.md、scripts/compare_skin_layout.py | MCP instructions、README、本能力参考、隔离回归；同步 Skill 包含脚本与参考文档 |
| `plugin/main.ts` Action、参数、返回值、动画序列化、阻塞策略、协议或版本 | `plugin/main.js`、三处版本、README、本 Skill 与本文件 |
| `src/fairygui_agent/mcp_server.py` MCP 工具或参数 | `src/fairygui_agent/bridge_client.py` capability、README、CLI/Skill 映射、本文件 |
| `src/fairygui_agent/cli.py` 子命令、参数或退出码 | README CLI、本 Skill、本文件 |
| `src/fairygui_agent/bridge_client.py` 队列、能力校验、超时或响应语义 | README 安装/协议、本 Skill、本文件 |

1. `plugin/package.json`、`pyproject.toml`、`src/fairygui_agent/__init__.py`、`plugin/main.ts` 和 `plugin/main.js` 版本一致。
2. 插件 capability、Action 分发、Python 动画 capability 检查、MCP 工具、CLI parser 和文档清单一致。
3. `plugin/main.ts` 与重新编译的 `plugin/main.js` 一致。
4. 创建/导入/预览变更应在 FairyGUI Editor `6.1.4` 隔离工程副本中验证，避免污染正式工程。


## 0.9.5 布局快照回归（2026-11-09）

在业务工程隔离副本中使用实际编译插件执行 7 种组件 × 50% / 100% / 150% 画布缩放，共 21 次原生快照；未保存或发布业务 UI。

| 组件 | 检查内容 | 结果 |
| --- | --- | --- |
| `ju_spin_stash/PopupSpinStash` | 居中锚点、1590×960 全画布、背景 `(103,104)` | 通过，右侧不再受视口截断 |
| `ju_spin_stash_exchange/PopupSpinStashExchange` | 居中锚点、独立兑换弹窗 | 通过 |
| `ju_spin_stash_task/PopupSpinStashTask` | 滚动列表、嵌套内部裁切 | 通过，各缩放下保留右侧奖励 |
| `ju_spin_stash_task/task_item_default` | 非锚点根、1108×132 任务行 | 通过 |
| `ju_spin_stash_exchange/ExchangeButton` | 341×98 小组件、锚点 | 通过 |
| `ju_common/green_btn` | 公共按钮、Controller 默认页 | 通过 |
| 临时 `LayoutProbe` | 画布四角、远端遮罩、旋转 30°、镜像及非等比缩放 | 通过，四角/遮罩像素断言及独立四角数学预期一致 |

各次快照前后文档 URL、修改标记、保存版本、选择数量及画布缩放一致。跨缩放坐标最大浮点差小于 0.0004 组件像素；带图片/字体的边缘存在宿主栅格化差异，未声称逐像素相同。42 项自动化检查覆盖独立绘制上下文、纹理释放、成功/失败恢复、PNG 行方向/透明度、MCP 图片内容及 CLI 导出。上述结果只证明编辑器快照路径，不包含游戏运行时验收。

全局安装后另启隔离 Editor，通过实际 JSON 队列完成 `ping`、打开主弹窗和带图快照：插件回报 `0.9.5`，1590×960 预览完整，背景坐标约 `(103,104)`，快照前后文档状态相同。安装源码、编译产物、宿主类型及版本文件哈希一致；原有用户 Editor 实例保留，需重启以加载新版。

## Skill 百分比进度检查

`check_progress_bars.py` 针对明确选择的百分比/平铺条目检查已保存基础 XML：默认与实例值、0–100 范围、唯一配对百分比、实际填充资源及文件存在性。支持嵌套填充组件；特殊端点图片仅可按精确资源 ID 和非空原因记录九宫格例外，未命中或缺失资源仍失败。错误返回非零；不连接编辑器，不验证游戏计算或图像解码。FTS 规范及独立验收边界见 [progress-bars.md](progress-bars.md)。脚本、参考文档和测试随 Skill 源仓库维护，并通过既有同步入口安装，无插件协议或版本变化。

## 0.9.6 卸载生命周期修复（2026-11-10）

旧版在入口执行期间给 `PluginInfo.onDestroy` 赋值；真实 Editor 加载完成后该字段为空，而隔离测试插件导出的同名函数能被宿主绑定并在退出时执行。修复改为入口导出 `onDestroy`，并先解绑事件、恢复后台设置，再清理菜单。旧实例残留委托需完全退出后重新加载；不据此扩大布局、进度条或游戏验收结论。

验证：25 项相关自动化检查通过，覆盖卸载入口、输入空闲边界、卸载后焦点、重复加载及菜单清理失败时事件已释放。真实 Editor 在两个空工程中各正常启动/退出两次；四次均绑定 0.9.6 卸载入口，记录 `bridge destroyed`，无 `JsEnv has been disposed`。从 JS 回调直接调用 `App.OpenProject` 会造成宿主 JsEnv 销毁重入并使隔离实例崩溃，该路径不计入正常验收；批处理脚本另受专业版许可限制。用户原实例及其实际工程切换/焦点回归待完整退出重开后验收。

## 0.9.7 外部资源自动刷新（2026-11-10）

主线程每 2 秒扫描 `assets` 路径、大小和修改时间，连续两次稳定后调用 `App.RefreshProject()`，覆盖新包、增删/重命名和 XML/图片修改。任意未保存文档、模态窗口、发布、请求队列或真实键鼠输入均推迟刷新；不会自动保存、放弃或发布。项目初始化/切换重建基线，卸载停止回调。忽略点号文件及 `.tmp/.temp/.swp`。不新增 Action，协议和 MCP 工具数不变；首次扫描前的变化随工程打开加载，大型项目扫描成本与文件数相关。

验证：编译产物宿主回归覆盖连续写入防抖、新包、文件修改、删除全部资源、临时文件、扫描失败重试、未保存文档、模态窗口、发布、请求/处理中队列、按键及三个鼠标键，以及重置/卸载。真实 Editor 6.1.4 隔离工程验收通过：新增包约 3.9 秒、当前 XML 画布约 5.7 秒更新；未保存文本保留且阻止新包刷新，用户处理后约 4.5 秒恢复；删除包约 3.9 秒消失。嵌套 XML 在父画布中自动更新，非活动页切回后自动重载，无需刷新。只重载当前已保存文档，避免原生 DiscardChanges 访问非活动画布；未改写无关组件源文件。隔离实例正常退出。实际 Album 工程 1,945 个文件的一次只读元数据扫描约 36 毫秒；用户原 Album 实例经菜单正常退出后重新打开，心跳回报 0.9.7，当前帮助页和独立信息包已加载。其他规模、平台和游戏加载未验收。
