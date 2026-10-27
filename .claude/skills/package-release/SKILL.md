---
name: package-release
description: 打包本项目的矩阵配队网站 ZIP、创建版本快照、更新 Windows 图标启动器并校验发布产物。用于“打个包”“发新版本”“重新打包”等本地发布请求。
---

# Package release

在独立配队仓库根目录 `E:/Program Files/wuthering-waves-matrix-planner` 执行，可用 `tools/release_static.py` 和 `CHANGELOG.md` 确认当前目录。所有下文相对路径均相对此仓库；不要在旁边的打轴仓库执行。配队不导入战斗项目的 `ww_matrix` 包。当前发布入口是 `tools/release_static.py`，不是旧版 `tools/package_planner.py` / PyInstaller 全量程序方案。

## 交付结构

ZIP 内只有一个英文顶层目录，网页文件再收进英文子目录：

```text
MatrixPlanner/
├─ 鸣潮矩阵配队.exe
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
4. 产物保存在 `dist/vVERSION/`：应用目录、ZIP、说明、`RELEASE_NOTES.md`、`manifest.json`。dist根目录不散放应用目录或ZIP。
5. 默认不覆盖历史快照。用户明确要求改同一版本时，先将旧目录移到 `tmp/` 的唯一备份路径，再重新生成该版本；保持旧版内容可找回。Windows移动前检查解析后的源/目标路径位于本项目预期目录。

初始Windows版归档在 `dist/v1.0.0/windows-original/`，不要混入当前包或改动它。

## 校验

- ZIP CRC通过；逐文件核对manifest中的SHA-256；确认ZIP顶层仅为 `MatrixPlanner/`，其直接子项仅启动器和 `web/`。
- 解压到含空格/中文的临时目录，运行启动器 `--check`，确认无需原工程也能定位页面。该模式只验证路径，不打开浏览器。
- 用全新浏览器上下文打开解压后的 `web/index.html`：首次引导出现、资源加载正常、无脚本错误、自动保存后刷新可恢复、配队计算可完成。
- 不要在首次引导测试中预先设置“不再显示”。单独验证勾选后不再弹出、手动入口可打开。
- 修改图标时确认PNG和ICO包含真实透明像素；移动端布局或界面有变化时检查代表性窄屏。
- 检查包里没有 `personal_config.json` 等开发个人文件。
- 确认 ZIP 内 `MatrixPlanner/web/CHANGELOG.md` 与根目录完整更新日志内容一致，且归档目录也有相同副本；`RELEASE_NOTES.md` 仅含本版增量。
- 运行与当前变更有关的测试；失败先修复，再交付。

最后给用户ZIP的可点击绝对路径、版本号和“完整解压后双击头像入口”的简短说明。不要把普通文件路径表述为网站登录地址。
