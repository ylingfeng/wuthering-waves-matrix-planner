"""Assemble the web-only portable distribution after the PyInstaller build."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / "dist/MatrixPlanner"
    if not (target / "MatrixPlanner.exe").is_file():
        raise SystemExit("Build tools/planner_launcher.py with PyInstaller first")
    for folder in ("web/team_planner", "assets/characters"):
        shutil.copytree(ROOT / folder, target / folder, dirs_exist_ok=True)
    shutil.copy2(ROOT / "assets/planner.ico", target / "assets/planner.ico")
    shutil.copy2(ROOT / "character.csv", target / "character.csv")
    config = target / "config/team_planner"
    config.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "config/team_planner/teams.json", config / "teams.json")
    # Seed matches the shipped editable library, including user-added teams.
    shutil.copy2(config / "teams.json", config / "catalogue.json")
    (target / "使用说明.txt").write_text(
        "矩阵配队工具（Windows 64位便携版）\n\n"
        "1. 将整个压缩包解压到可写入的文件夹，不要在压缩包内运行。\n"
        "2. 双击 MatrixPlanner.exe（秧秧头像图标）。无需安装 Python。\n"
        "3. 程序自动打开浏览器。未打开时点击启动窗口中的“打开配队网页”。\n"
        "4. 按需修改拥有状态、体力、链度、用户练度、角色定位与队伍权重。\n"
        "5. 点击“保存修改”保存，点击“计算配队”生成方案。\n"
        "6. 关闭启动窗口即可退出服务；只关闭浏览器不会停止服务。\n\n"
        "本包包含当前角色及配队配置；给其他人使用时，请自行调整拥有状态和链度。\n"
        "数据存放在 character.csv 与 config/team_planner/teams.json，可复制备份。\n"
        "请保留整个文件夹，不能只发送 exe；_internal 是程序运行依赖。\n"
        "本工具只在当前电脑提供网页配队，不需要服务器、不操作游戏。\n"
        "首次及后续启动均可离线使用，只有打开外部资料链接时需要网络。\n"
        "固定地址：http://127.0.0.1:18765。同一时间只需启动一份工具。\n"
        "首次打开网页会显示使用介绍，可勾选“下次不再显示”；也可点击页面的“使用说明”重新查看。\n"
        "错误记录见 logs/planner.log。\n",
        encoding="utf-8-sig")
    archive = shutil.make_archive(str(ROOT / "dist/MatrixPlanner-Web-Windows"), "zip",
                                  target.parent, target.name)
    print(archive)


if __name__ == "__main__":
    main()
