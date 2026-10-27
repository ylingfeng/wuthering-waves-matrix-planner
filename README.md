# 鸣潮矩阵配队平台

这是独立的配队 Git 仓库，目录为 `E:\Program Files\wuthering-waves-matrix-planner`。代码、数据、测试、发布产物均在本目录，不依赖旁边打轴项目的代码，也不向游戏发送按键。

## 开发启动

安装 Python 3.10+，双击本目录的 `start.cmd`，打开 <http://127.0.0.1:8765>。

也可以在本目录执行：

```powershell
python -X utf8 -m tools.planner_dev_server --port 8765
```

当前网页及开发服务使用浏览器求解器与 Python 标准库，不需要安装战斗脚本的依赖。纯静态使用可直接打开 `web/team_planner/index.html`。

## 目录

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

## 保存与备份

开发服务会把网页修改同步到 `config/team_planner/personal_config.json`，保留 `personal_config.previous.json`。这两份个人文件不提交到 Git，也不默认打进发布包。迁移项目目录不会重置配置；开发网址维持不变。

静态 ZIP 中的个人修改保存在浏览器；导出 JSON 用于备份或迁移。默认资料来自 `seed.js`，修改 CSV 后应使用对应资料维护工具更新默认库。

## 检查与发布

```powershell
python -m pip install -r requirements-dev.txt
python -X utf8 -m unittest discover -s tests -v
```

浏览器测试使用本机 Chrome，运行前应安装 Chrome。`requirements.txt` 提供旧版 Python 求解器依赖，网页本身不需要这些库。

只有明确要求打包时才执行 `python -m tools.release_static 版本号`。先维护对应的更新日志章节；发布包自动附带完整 `CHANGELOG.md` 与本版 `RELEASE_NOTES.md`。版本号与后续 Git Tag / Release 对应，未发布改动不挪入既有标签。

`tools/build_planner.cmd`、`tools/package_planner.py` 和 `tools/planner_launcher.py` 仅保留用于早期 Python 便携包维护；当前发布入口是 `tools/release_static.py`。
