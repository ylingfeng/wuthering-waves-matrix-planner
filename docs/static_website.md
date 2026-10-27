# 纯静态网站
所有命令在独立配队仓库根目录执行。开发目录：web/team_planner。无需 Python API，计算由浏览器 Web Worker 和本地打包的 javascript-lp-solver 完成，先最大化队数，再最大化得分，随后按定位补队。
Windows 和 macOS 均可用 Chrome 打开 index.html，Windows 也可使用 Edge；或将该目录部署到任意静态托管服务。所有资源均使用相对路径。
配置保存在当前浏览器 localStorage；不会回写 character.csv。导出配置用于备份，导入用于迁移。多个浏览器之间不自动同步。初始数据在 seed.js，头像在 portraits/。
仅在用户要求打包时发布：python -m tools.release_static 版本号。平时改动累计在 CHANGELOG.md 的“未发布”。
每次使用新的语义版本号；已存在版本会拒绝覆盖。后续版本的 `dist/v版本号/Windows/MatrixPlanner/web` 与 `dist/v版本号/macOS/MatrixPlanner/web` 均为部署目录。ZIP 分别命名为 `MatrixPlanner-Windows-v版本号.zip` 和 `MatrixPlanner-macOS-v版本号.zip`，`SHA256SUMS.txt` 包含两个 ZIP 的校验值，`manifest.json` 包含归档文件的 SHA-256。
当前发布包附带轻量 Windows 头像启动器，双击打开 web/index.html；无需安装 Python。ZIP 内同时附带完整 CHANGELOG.md 和当前版本的 RELEASE_NOTES.md。
从 v1.2.1 起分别提供两个包：Windows 包只附带 EXE，macOS 包只附带 HTML 启动入口，两者内部都保留 `web/` 资源目录。HTML 自动跳转到 `web/index.html`，避免因启动入口不同而分散个人配置。旧版 v1.2.0 在 macOS 直接打开 `web/index.html` 即可。构建两个包仍在 Windows 上执行，EXE 需要 .NET Framework 编译器；使用网页不需要安装 .NET。

固定基础分：B站矩阵视频2.5；Wiki明确配队1.5；工坊轴说明明确含矩阵/矩陣2；其他来源默认不参与。多证据取最高，不额外乘来源系数。爱达千和爱琳莫固定基础分特例为5。用户队伍权重独立保存，默认1；导入个人配置不覆盖固定库分。


## 自动保存与本地开发服务（当前行为）

使用 `python -m tools.planner_dev_server` 启动，默认地址 http://127.0.0.1:8765。
网页修改立即保存浏览器，并自动同步 `config/team_planner/personal_config.json`；前一份保存在 `personal_config.previous.json`。
个人文件包含角色拥有状态、定位、体力、链度/练度，队伍组合/属性、用户加权、参与/必选、备注、轴及所选轴，计算范围/兜底选项和筛选设置。导出v2配置是这些个人数据的JSON副本。
来源、固定分等默认资料从当前库读取，不被导入文件覆盖。爱达千和爱琳莫固定分特例为5，记录在base_score_overrides.json。
角色的固定伤害属性记录在 `character.csv` 的“属性”列；仅漂泊者使用“可选属性”。来源记录见 `config/team_planner/element_sources.json`，可用 `python -m tools.sync_character_elements --catalogue 官方Wiki目录JSON路径` 同步 CSV 和 `seed.js`，不改个人配置或队伍资料。网页启动时从默认库补齐属性，保留用户拥有、体力、链度、练度及必选队等设置。
首次本地文件不存在时自动导入当前浏览器配置；之后本地文件为共享基准，乐观锁阻止多页面静默覆盖。
纯静态发布无本地写入API时仍自动保存浏览器，导出可备份。网页编辑器的字段在点击“应用到候选列表”后提交并自动保存。
