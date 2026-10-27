"""Static development site with durable, separate personal configuration."""
import argparse
import json
import os
import threading
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


class PersonalStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()

    def read(self):
        with self.lock:
            return json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'revision': None, 'config': None}

    def save(self, expected, config):
        if not isinstance(config, dict) or config.get('format') != 'matrix-planner-v2':
            raise ValueError('个人配置格式无效')
        if not isinstance(config.get('teams'), list) or len(config['teams']) > 2000 or not isinstance(config.get('characters'), list):
            raise ValueError('个人配置数据无效')
        with self.lock:
            old = self.read()
            if old['revision'] != expected:
                raise FileExistsError('本地配置已被其他页面更新，请刷新后重试')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                backup = self.path.with_suffix('.previous.json')
                backup.write_bytes(self.path.read_bytes())
            data = {'revision': str(uuid.uuid4()), 'config': config}
            temp = self.path.with_suffix('.tmp')
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(temp, self.path)
            return data


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'web/team_planner'), **kwargs)

    def reply(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if urlsplit(self.path).path == '/api/personal-config':
            return self.reply(200, self.server.store.read())
        return super().do_GET()

    def do_POST(self):
        if self.path != '/api/personal-config':
            return self.reply(404, {'error': '接口不存在'})
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            return self.reply(403, {'error': '只接受当前网站的保存请求'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.reply(415, {'error': '需要JSON配置'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 8_000_000:
                raise ValueError('配置大小无效')
            data = json.loads(self.rfile.read(size))
            self.reply(200, self.server.store.save(data.get('revision'), data['config']))
        except FileExistsError as exc:
            self.reply(409, {'error': str(exc)})
        except (ValueError, KeyError, TypeError) as exc:
            self.reply(400, {'error': str(exc)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/team_planner/personal_config.json')
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.store = PersonalStore(args.config)
    print(f'http://127.0.0.1:{args.port} | personal config: {args.config}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
