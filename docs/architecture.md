# 项目边界

本仓库独立维护配队平台，可单独复制、开发、测试和发布。不需要旁边打轴项目的 `app.py`、`ww_matrix/`、战斗配置或游戏识别素材。

- 网页、默认资料、头像与浏览器求解器全部位于 `web/team_planner/`。
- 当前开发服务 `tools/planner_dev_server.py` 只使用 Python 标准库，静态文件和个人配置路径从自身文件位置解析。
- Python 算法和早期编辑器使用独立包名 `matrix_planner`，不导入战斗执行器。
- 角色 CSV、默认配队、资料维护工具、证据记录和图标素材均位于本仓库。
- 测试使用临时目录或独立浏览器存储，不修改真实账号配置。
- 发布工具从本仓库读取网页、启动器源码和更新日志，只写入本仓库的 `dist/`。

发布 skill 仅位于本仓库的 `.claude/skills/package-release/`，本仓库 `.agents/skills` 只指向自身 `.claude/skills`。打轴工作区不保留指向本仓库的 skill 链接。
