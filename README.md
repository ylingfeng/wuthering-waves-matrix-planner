<p align="center">
  <img src="assets/branding/denia-icon.png" width="128" height="128" alt="鸣潮矩阵配队图标，与 Windows 启动器一致">
</p>

# 鸣潮矩阵配队

用于规划鸣潮矩阵模式队伍的工具。设置角色拥有状态、体力、链度和练度，调整候选队伍后计算配队；优先增加队伍数量，再比较队伍得分。

**[下载最新版本](https://github.com/ylingfeng/wuthering-waves-matrix-planner/releases/latest)** · [所有版本与更新说明](https://github.com/ylingfeng/wuthering-waves-matrix-planner/releases) · [反馈问题](https://github.com/ylingfeng/wuthering-waves-matrix-planner/issues)

## 下载与启动（Windows）

无需安装 Python，也无需运行命令。

1. 打开上方的 **「下载最新版本」**。
2. 在版本页面底部的 **Assets（附件）** 中，下载 `MatrixPlanner-Web-v版本号.zip`，例如 `MatrixPlanner-Web-v1.2.0.zip`。
3. 右键 ZIP，选择 **「全部解压缩」**。
4. 打开解压后的 `MatrixPlanner` 文件夹，双击带上方头像图标的 **`鸣潮矩阵配队.exe`**，浏览器会自动打开配队网页。

解压后的文件结构：

```text
MatrixPlanner/
├─ 鸣潮矩阵配队.exe    ← 双击这个头像入口
└─ web/               ← 网页、默认资料与头像，和 EXE 一起保留
```

请完整解压后再启动，并保持 EXE 与 `web` 文件夹相邻。Release 中的 `Source code (zip)` / `Source code (tar.gz)` 是开发源码；日常使用下载 `MatrixPlanner-Web-…zip` 即可。

EXE 用于打开随包附带的网页，无需后台服务。也可以直接用 Chrome 或 Edge 打开 `web/index.html`。

## 第一次使用

首次打开会出现操作引导；之后可点击右上角 **「使用说明」** 再次查看。

1. **角色库**：设置已拥有角色、本周体力、角色定位、链度和用户练度。
2. **候选队伍**：选择参与计算的队伍，调整用户权重；需要固定使用的队伍开启「必须选入」。也可以新建队伍。
3. 点击 **「计算配队」**，在配队结果中查看方案。可切换「全角色计算」，预览包含未拥有角色的配队。

修改会自动保存。编辑队伍弹窗中的内容需点击 **「应用到候选列表」** 后生效。它是配队规划工具，体力不会实际扣除。

## 配置保存与升级

发布包将个人配置保存在当前浏览器中，包括拥有状态、体力、链度、练度、配队组合、用户权重和必选设置等。

**升级版本、移动文件夹、更换浏览器或清理浏览器数据前，请先通过「配置管理 → 导出个人配置」备份 JSON。** 在新版本中通过「导入个人配置」恢复即可。EXE 本身不保存个人配置，网页也不会回写包内的默认资料文件。

默认资料位于 `web/seed.js`，头像位于 `web/portraits/`。发布包已包含所需资料，无需另外下载 CSV。

## 更新说明

每个 [Release](https://github.com/ylingfeng/wuthering-waves-matrix-planner/releases) 页面直接展示该版本的改动。下载包内也附带：

- `web/RELEASE_NOTES.md`：当前版本更新说明。
- `web/CHANGELOG.md`：完整历史更新日志。

仓库的 [CHANGELOG.md](CHANGELOG.md) 中，「未发布」表示开发中的改动，以 Release 页面和所下载版本的说明为准。

## 开发者说明

本仓库独立维护网页、数据、测试及发布工具。

### 本地开发

安装 Python 3.10+，双击本目录的 `start.cmd`，打开 <http://127.0.0.1:8765>。

也可以在本目录执行：

```powershell
python -X utf8 -m tools.planner_dev_server --port 8765
```

当前网页及开发服务使用浏览器求解器与 Python 标准库，不需要安装战斗脚本的依赖。纯静态使用可直接打开 `web/team_planner/index.html`。

### 源码结构

| 路径 | 内容 |
| --- | --- |
| `web/team_planner/` | 网页、浏览器配队算法、默认数据 `seed.js`、角色头像 |
| `matrix_planner/` | 独立的 Python 配队算法与旧版 HTTP 编辑器 |
| `tools/` | 开发服务、默认资料维护、来源核查、头像同步和发布工具 |
| `character.csv` | 角色资料源文件 |
| `config/team_planner/` | 默认配队资料与开发环境个人配置 |
| `assets/` | 头像和图标源素材 |
| `tests/` | 配队、来源、配置保存及浏览器回归测试 |
| `docs/` | 平台说明 |
| `reference_analysis/` | 来源研究记录和缓存 |
| `dist/v版本号/` | 发布快照与 ZIP，不自动重新打包 |
| `CHANGELOG.md` | 完整更新日志，日常改动先记入“未发布” |

### 开发环境保存与备份

开发服务会把网页修改同步到 `config/team_planner/personal_config.json`，保留 `personal_config.previous.json`。这两份个人文件不提交到 Git，也不默认打进发布包。迁移项目目录不会重置配置；开发网址维持不变。

静态 ZIP 中的个人修改保存在浏览器；导出 JSON 用于备份或迁移。默认资料来自 `seed.js`，修改 CSV 后应使用对应资料维护工具更新默认库。

### 检查与发布

```powershell
python -m pip install -r requirements-dev.txt
python -X utf8 -m unittest discover -s tests -v
```

浏览器测试使用本机 Chrome，运行前应安装 Chrome。`requirements.txt` 提供旧版 Python 求解器依赖，网页本身不需要这些库。

只有明确要求打包时才执行 `python -m tools.release_static 版本号`。先维护对应的更新日志章节；发布包自动附带完整 `CHANGELOG.md` 与本版 `RELEASE_NOTES.md`。版本号与后续 Git Tag / Release 对应，未发布改动不挪入既有标签。

`tools/build_planner.cmd`、`tools/package_planner.py` 和 `tools/planner_launcher.py` 仅保留用于早期 Python 便携包维护；当前发布入口是 `tools/release_static.py`。
