"""Create a new immutable version directory containing a static-only website."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('version', help='For example 1.0.0')
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+', args.version):
        parser.error('Version must be MAJOR.MINOR.PATCH')
    changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    section = re.search(r'^## v' + re.escape(args.version) + r'\s*\n(.*?)(?=^## |\Z)', changelog, re.M | re.S)
    if not section or not section.group(1).strip():
        parser.error('Add release changes to CHANGELOG.md under ## v' + args.version + ' before packaging')
    notes = '# v' + args.version + '\n\n' + section.group(1).strip() + '\n'
    release = ROOT / 'dist' / ('v' + args.version)
    release.mkdir(parents=True, exist_ok=False)
    if __package__:
        from .build_web_routes import build_routes
    else:
        from build_web_routes import build_routes
    build_routes()
    bundle = release / 'MatrixPlanner'
    site = bundle / 'web'
    shutil.copytree(ROOT / 'web/team_planner', site)
    compiler = Path(r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe')
    subprocess.run([str(compiler), '/nologo', '/target:winexe', '/optimize+',
                    '/reference:System.Windows.Forms.dll', '/win32icon:'+str(site/'favicon.ico'),
                    '/out:'+str(bundle/'鸣潮矩阵配队.exe'), str(ROOT/'tools/WebsiteLauncher.cs')], check=True)
    instructions = (
        f'矩阵配队网站 v{args.version}\n\n'
        '本地使用：完整解压，打开 MatrixPlanner 文件夹，双击达妮娅头像的“鸣潮矩阵配队.exe”，自动打开网页。\n'
        '网页源码、默认数据、头像和说明全部放在web子文件夹，请保持它与启动器相邻。\n'
        '不需要安装、创建快捷方式、Python或后台服务。也可直接用Chrome或Edge打开index.html。\n'
        '线上使用：把web内的全部文件上传到静态网站托管平台，入口为 index.html。\n'
        '修改自动保存在当前浏览器；队伍编辑窗口点“应用”后自动保存，无须手动导出。\n'
        '纯网站包不会写入本地配置文件；开发环境的本地文件同步需要另行启动开发服务。\n'
        '更换浏览器、路径或网址前，请导出个人配置备份，再导入恢复（兼容v1/v2配置）。\n'
        '部分浏览器限制本地文件存储；这时请使用静态托管网址。\n'
        '附带当前默认角色及队伍资料，不打入开发环境的个人配置文件，请按自己的账号调整。\n'
        '固定基础分：B站矩阵2.5、工坊矩阵2、Wiki明确配队1.5；再乘用户配队加权（默认1）及角色权重。角色权重=(链度+1)×基础分×用户练度。\n'
        '指定特例：爱达千、爱琳莫固定基础分5。导出的用户配置不会覆盖资料库基础分。\n'
        '完整更新日志：web/CHANGELOG.md；当前版本说明：web/RELEASE_NOTES.md。\n'
        '第三方求解器许可证：web/vendor/LICENSE-solver.txt。\n')
    (release / '使用说明.txt').write_text(instructions, encoding='utf-8-sig')
    (site / '使用说明.txt').write_text(instructions, encoding='utf-8-sig')
    (release / 'RELEASE_NOTES.md').write_text(notes, encoding='utf-8')
    (site / 'RELEASE_NOTES.md').write_text(notes, encoding='utf-8')
    shutil.copyfile(ROOT / 'CHANGELOG.md', release / 'CHANGELOG.md')
    shutil.copyfile(ROOT / 'CHANGELOG.md', site / 'CHANGELOG.md')
    archive = Path(shutil.make_archive(str(release / f'MatrixPlanner-Web-v{args.version}'), 'zip', release, bundle.name))
    files = {str(p.relative_to(release)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(release.rglob('*')) if p.is_file()}
    (release / 'manifest.json').write_text(json.dumps({'version': args.version,
        'created_utc': datetime.now(timezone.utc).isoformat(), 'sha256': files}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(archive)


if __name__ == '__main__':
    main()
