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


def copy_browser_launcher(bundle):
    """Both platforms enter the same page, keeping one browser storage path."""
    shutil.copyfile(ROOT / 'tools/WebsiteLauncher.html', bundle / '鸣潮矩阵配队.html')


def build_platform_bundle(destination, platform, version, notes, changelog, site_source=None):
    """Prepare one platform's files; archive creation is reserved for main()."""
    if platform not in ('Windows', 'macOS'):
        raise ValueError('Unsupported platform')
    bundle = destination / 'MatrixPlanner'
    site = bundle / 'web'
    shutil.copytree(site_source or ROOT / 'web/team_planner', site)
    if platform == 'Windows':
        compiler = Path(r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe')
        subprocess.run([str(compiler), '/nologo', '/target:winexe', '/optimize+',
                        '/reference:System.Windows.Forms.dll', '/win32icon:'+str(site/'favicon.ico'),
                        '/out:'+str(bundle/'鸣潮矩阵配队.exe'), str(ROOT/'tools/WebsiteLauncher.cs')], check=True)
        startup = '完整解压，打开 MatrixPlanner 文件夹，双击达妮娅头像的“鸣潮矩阵配队.exe”。\n'
    else:
        copy_browser_launcher(bundle)
        startup = '完整解压，打开 MatrixPlanner 文件夹，用 Chrome 打开“鸣潮矩阵配队.html”。\n'
    instructions = (
        f'矩阵配队 v{version} · {platform}\n\n' + startup +
        '网页源码、默认数据、头像和说明全部放在web子文件夹，请保持它与启动入口相邻。\n'
        '无需安装 Python 或启动后台服务。也可直接用 Chrome 打开 web/index.html。\n'
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
    (site / '使用说明.txt').write_text(instructions, encoding='utf-8-sig')
    (site / 'RELEASE_NOTES.md').write_text(notes, encoding='utf-8')
    (site / 'CHANGELOG.md').write_bytes(changelog)
    return bundle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('version', help='For example 1.0.0')
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+', args.version):
        parser.error('Version must be MAJOR.MINOR.PATCH')
    changelog_bytes = (ROOT / 'CHANGELOG.md').read_bytes()
    changelog = changelog_bytes.decode('utf-8').replace('\r\n', '\n')
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
    archives = []
    for platform in ('Windows', 'macOS'):
        destination = release / platform
        bundle = build_platform_bundle(destination, platform, args.version, notes, changelog_bytes)
        archive = Path(shutil.make_archive(str(release / f'MatrixPlanner-{platform}-v{args.version}'),
                                          'zip', destination, bundle.name))
        archives.append(archive)
    (release / 'RELEASE_NOTES.md').write_text(notes, encoding='utf-8')
    (release / 'CHANGELOG.md').write_bytes(changelog_bytes)
    (release / 'SHA256SUMS.txt').write_text(''.join(
        hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n'
        for archive in archives), encoding='utf-8')
    files = {str(p.relative_to(release)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(release.rglob('*')) if p.is_file()}
    (release / 'manifest.json').write_text(json.dumps({'version': args.version,
        'created_utc': datetime.now(timezone.utc).isoformat(), 'sha256': files}, ensure_ascii=False, indent=2), encoding='utf-8')
    for archive in archives:
        print(archive)


if __name__ == '__main__':
    main()
