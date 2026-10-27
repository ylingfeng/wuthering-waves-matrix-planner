---
name: package-release
description: 打包本项目的矩阵配队网站 ZIP、创建版本快照、更新 Windows 图标启动器并校验发布产物。用于“打个包”“发新版本”“重新打包”等本地发布请求。
---

# Package release

在独立配队仓库根目录 `E:/Program Files/wuthering-waves-matrix-planner` 执行，可用 `tools/release_static.py` 和 `CHANGELOG.md` 确认当前目录。所有下文相对路径均相对此仓库；不要在旁边的打轴仓库执行。配队不导入战斗项目的 `ww_matrix` 包。当前发布入口是 `tools/release_static.py`，不是旧版 `tools/package_planner.py` / PyInstaller 全量程序方案。

## 交付结构

每个版本分别提供 `MatrixPlanner-Windows-vVERSION.zip` 与 `MatrixPlanner-macOS-vVERSION.zip`。每个 ZIP 内只有一个英文顶层目录，网页文件再收进英文子目录：

```text
MatrixPlanner/
├─ 鸣潮矩阵配队.exe（Windows 包）或 鸣潮矩阵配队.html（macOS 包）
└─ web/
   ├─ index.html
   ├─ seed.js
   ├─ favicon.png / favicon.ico
   ├─ CHANGELOG.md / RELEASE_NOTES.md
   ├─ portraits/
   ├─ characters/ / teams/ / results/
   └─ 其他页面资源及说明
```

- 应用文件夹、网页资源文件夹名称使用英文。
- 用户完整解压后直接双击带角色头像的 EXE 打开网页，无需安装、创建快捷方式、Python或后台服务。
- EXE 是轻量网页启动器，源码 `tools/WebsiteLauncher.cs`。通过自身位置查找 `web/index.html`，不得硬编码开发机路径，不用可能随移动失效的 `.lnk` 替代。
- 两个包共用网页；macOS 包的 HTML 入口由 `tools/WebsiteLauncher.html` 复制生成，相对跳转至 `web/index.html`。Windows 包不放 HTML 入口，macOS 包不放 EXE。macOS 用 Chrome 打开 HTML，不需要 Python 或修改脚本权限。构建两包仍在 Windows 上执行。
- 图标来自 `web/team_planner/favicon.ico`，保留透明背景；PNG用于网页标签与品牌图标。用户指定新图才替换，不能每次重新生成旧头像。

## 数据边界

- 默认角色和配队数据由 `web/team_planner/seed.js` 提供，图片在 `portraits/`；发布包不需要附带 `character.csv`。
- 个人修改在纯网站包中自动保存到浏览器；导出JSON为个人配置备份。不能声称纯网站包会回写磁盘配置。
- 开发服务 `tools/planner_dev_server.py` 的磁盘同步另存于 `config/team_planner/personal_config.json`，不默认打入发布包。
- 不默认打包开发日志、浏览器个人数据、缓存或用户个人配置。用户明确要求将个人配置作为分发初始配置时另行处理，并核对内容。

## 发布步骤

只有用户明确要求打包时才生成发布产物。普通修改先累计到根目录 `CHANGELOG.md` 的“未发布”，不自动递增版本、不因单个小修复单独打包。
`CHANGELOG.md` 是发布说明的唯一来源：每个版本只记录相对上版的真实增量，不重复罗列已有功能。发布时将本批改动归入对应 `## vVERSION`，保留“未发布”区供后续累计。发布脚本从该章节生成包内和归档中的 `RELEASE_NOTES.md`；未填写版本记录时应停止打包。
每个发布包必须附带完整的 `web/CHANGELOG.md`，包含历史版本记录；不能只附当前版本的 `RELEASE_NOTES.md`。版本归档目录也保存同一份 `CHANGELOG.md`，使用说明注明两份日志的位置。

1. 查看 `dist/` 已有版本。用户指定版本优先；否则功能发布递增次版本，修复递增补丁版本。
2. 检查当前发布脚本的使用说明、发布说明、固定分特例和候选数量是否符合实际，不沿用过时数字。
3. 执行 `python -m tools.release_static VERSION`。脚本同步三页静态入口，复制网页资源，使用 Windows .NET Framework 的 `csc.exe` 编译带图标启动器，并生成 ZIP 和 SHA-256 清单。
4. 产物保存在 `dist/vVERSION/`：`Windows/MatrixPlanner/`、`macOS/MatrixPlanner/`、两个 ZIP、`SHA256SUMS.txt`、`CHANGELOG.md`、`RELEASE_NOTES.md`、`manifest.json`。dist根目录不散放应用目录或ZIP。
5. 默认不覆盖历史快照。用户明确要求改同一版本时，先将旧目录移到 `tmp/` 的唯一备份路径，再重新生成该版本；保持旧版内容可找回。Windows移动前检查解析后的源/目标路径位于本项目预期目录。

初始Windows版归档在 `dist/v1.0.0/windows-original/`，不要混入当前包或改动它。

## GitHub Release（用户要求发布时）

- 推送代码、推送 Tag、生成本地 ZIP 和发布 GitHub Release 是不同步骤；只完成前几步不能报告 Release 已发布。
- 同一版本的 Tag 必须指向实际构建版本。工作区后续未发布改动不能混进既有版本的 ZIP 或说明。
- Release 标题包含版本号；正文使用该快照的 `RELEASE_NOTES.md`，直接在页面展示真实增量，不能留空或仅让用户下载 ZIP 查看。用 `gh release create/edit --notes-file` 保留中文及换行。
- 附件上传两个平台 ZIP、`SHA256SUMS.txt`、完整 `CHANGELOG.md` 及 `RELEASE_NOTES.md`。发布后读回正文、Tag 和附件列表，核对附件大小与本地 SHA-256。
- SSH 只负责 Git 传输；GitHub API/CLI 未登录时用设备授权，不能把 Tag 当成 Release。先准备并校验所有产物，再说明需要授权的具体操作；不向用户索取密码或明文 Token。
- 普通本地打包请求不等于授权创建公开 Release；用户明确要求创建或发布 Release 时继续完成整个发布流程。

## 校验

- 两个 ZIP 的 CRC 通过；逐文件核对manifest中的SHA-256；确认ZIP顶层仅为 `MatrixPlanner/`，其直接子项仅该平台的启动入口和 `web/`。
- 验证通用 HTML 入口在含空格/中文的目录中进入同一 `web/index.html`；使用隔离浏览器存储验证自动保存与配队计算。引擎兼容测试不能冒充 macOS 真机验证。
- 解压到含空格/中文的临时目录，运行启动器 `--check`，确认无需原工程也能定位页面。该模式只验证路径，不打开浏览器。
- 用全新浏览器上下文打开解压后的 `web/index.html`：首次引导出现、资源加载正常、无脚本错误、自动保存后刷新可恢复、配队计算可完成。
- 不要在首次引导测试中预先设置“不再显示”。单独验证勾选后不再弹出、手动入口可打开。
- 修改图标时确认PNG和ICO包含真实透明像素；移动端布局或界面有变化时检查代表性窄屏。
- 检查包里没有 `personal_config.json` 等开发个人文件。
- 确认 ZIP 内 `MatrixPlanner/web/CHANGELOG.md` 与根目录完整更新日志内容一致，且归档目录也有相同副本；`RELEASE_NOTES.md` 仅含本版增量。
- 运行与当前变更有关的测试；失败先修复，再交付。

最后给用户两个 ZIP 的可点击绝对路径、版本号及各自的启动说明。不要把普通文件路径表述为网站登录地址。
