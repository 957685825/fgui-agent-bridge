# 更新记录

本记录仅描述本维护分支。原始来源及 MIT 许可证见 README 和 LICENSE。

## 0.9.6 — 2026-11-10

本次整理并上传此前在本地迭代的修正：

- 导出插件 `onDestroy`，先解绑宿主事件再清理菜单，避免卸载后委托访问已销毁的 JsEnv。
- 增加根画布布局快照与原生 PNG 预览，修正锚点偏移和编辑器视口裁切，保留状态恢复与资源释放。
- 增加输入空闲后的状态恢复；心跳正常的慢请求不再次激活编辑器。
- 支持当前用户全局插件安装，保留按工程安装与默认 dry-run。
- 随 Skill 提供组件结构、进度条、换皮布局的只读检查脚本和独立回归样例。
- 补充贴边、底部收边、圆角与拼接的视觉验收要求，保留用户手工布局。
- 完整保留 TypeScript、Python、Skill、类型声明、编译配置及可读 main.js，补齐开发和维护说明。

发布检查：46 项离线自动化测试通过；插件 TypeScript 编译通过，生成 main.js 与仓库运行文件逐字节一致；CLI / MCP 帮助命令和 git diff --check 通过。真实 Editor 的历史验收范围和已知限制见 `.agents/skills/fgui-agent-bridge/references/current-capabilities.md`；本次源码上传不代表新增游戏内或 Windows 验收。
