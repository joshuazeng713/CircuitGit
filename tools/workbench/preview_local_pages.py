#!/usr/bin/env python3
"""Serve the locally built GitHub Pages site alongside the local browser companion."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser

from platform_compat import install_sigterm_handler

ROOT = Path(__file__).resolve().parents[2]


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True

    def server_bind(self):
        # Avoid blocking reverse DNS lookups (socket.getfqdn) on loopback binds.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


def make_site_handler(site_dir):
    class SiteHandler(SimpleHTTPRequestHandler):
        extensions_map = {
            **SimpleHTTPRequestHandler.extensions_map,
            '.js': 'application/javascript; charset=utf-8',
            '.mjs': 'application/javascript; charset=utf-8',
            '.css': 'text/css; charset=utf-8',
            '.json': 'application/json; charset=utf-8',
            '.svg': 'image/svg+xml',
            '.wasm': 'application/wasm',
        }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(site_dir), **kwargs)

        def end_headers(self):
            self.send_header('Cache-Control', 'no-store')
            super().end_headers()

        def log_message(self, *args):
            pass

    return SiteHandler


def wait_for_helper(proc, host, port, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        code = proc.poll()
        if code is not None:
            return False, code
        try:
            with socket.create_connection((host, port), timeout=0.3):
                if proc.poll() is not None:
                    return False, proc.returncode
                return True, None
        except OSError:
            time.sleep(0.15)
    return False, proc.poll()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site-port', type=int, default=8769, help='Loopback port for serving local site/')
    p.add_argument('--helper-port', type=int, default=8767, help='Loopback port forwarded to connect_browser.py')
    p.add_argument('--state-dir', type=Path, help='Optional state directory forwarded to connect_browser.py')
    p.add_argument('--skip-build', action='store_true', help='Skip rebuilding site/ before serving')
    p.add_argument('--no-browser', action='store_true', help='Start servers without opening a browser window')
    args = p.parse_args()

    site_dir = ROOT / 'site'
    utf8_env = {**os.environ, 'PYTHONUTF8': '1'}

    if not args.skip_build:
        print('[CircuitGit] 正在构建本地静态预览页面 (site/)…', flush=True)
        subprocess.run(
            [sys.executable, '-X', 'utf8', '-B', str(ROOT / 'tools/dev/build_pages.py')],
            cwd=str(ROOT),
            env=utf8_env,
            check=True,
        )

    if not (site_dir / 'index.html').is_file():
        print('[CircuitGit] 未找到本地 site/index.html，请先去掉 --skip-build 运行以构建本地页面。', file=sys.stderr, flush=True)
        return 1

    try:
        static_server = PreviewServer(('127.0.0.1', args.site_port), make_site_handler(site_dir))
    except OSError as error:
        print(f'[CircuitGit] 本地预览页面端口 {args.site_port} 启动失败：{error}', file=sys.stderr, flush=True)
        return 1

    actual_site_port = static_server.server_port
    origin = f'http://127.0.0.1:{actual_site_port}'
    localhost_origin = f'http://localhost:{actual_site_port}'
    preview_url = f'{origin}/'

    static_thread = threading.Thread(target=static_server.serve_forever, daemon=True)
    static_thread.start()

    helper_cmd = [
        sys.executable, '-E', '-s', '-B',
        str(ROOT / 'tools/workbench/connect_browser.py'),
        '--no-browser',
        '--port', str(args.helper_port),
        '--allow-origin', origin,
        '--allow-origin', localhost_origin,
    ]
    if args.state_dir is not None:
        helper_cmd.extend(['--state-dir', str(args.state_dir)])

    proc = None
    try:
        proc = subprocess.Popen(helper_cmd, cwd=str(ROOT))
        ready, exit_code = wait_for_helper(proc, '127.0.0.1', args.helper_port)
        if not ready:
            if exit_code is not None:
                print(
                    f'[CircuitGit] 本机连接助手启动失败（退出码 {exit_code}）。'
                    f'请查看上方具体报错；若之前已打开 Start CircuitGit.bat 占用了端口 {args.helper_port}，请先关闭旧窗口后重试。',
                    file=sys.stderr,
                    flush=True,
                )
                return exit_code or 1
            print(f'[CircuitGit] 等待本机连接助手（端口 {args.helper_port}）超时。', file=sys.stderr, flush=True)
            return 1

        print('==========================================', flush=True)
        print(f'  本地前端预览: {preview_url}', flush=True)
        print(f'  本机连接助手: http://127.0.0.1:{args.helper_port}', flush=True)
        print('  当前模式会直接服务本地构建的 site/ 并连接到本机工作台后端。', flush=True)
        print('  按 Ctrl+C 或关闭此窗口即可同时停止两个服务。', flush=True)
        print('==========================================', flush=True)

        if not args.no_browser:
            webbrowser.open(preview_url)

        def stop(signum, frame):
            raise KeyboardInterrupt

        install_sigterm_handler(stop, signal_module=signal)
        try:
            return proc.wait()
        except KeyboardInterrupt:
            return 0
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        static_server.shutdown()
        static_server.server_close()


if __name__ == '__main__':
    try:
        if any(flag in sys.argv[1:] for flag in ('--help', '-h')):
            raise SystemExit(main())
        from bootstrap_python import run_entrypoint
        raise SystemExit(run_entrypoint(__file__, main))
    except subprocess.CalledProcessError as error:
        print(f'[CircuitGit] 本地静态页面构建失败（退出码 {error.returncode}）。', file=sys.stderr, flush=True)
        raise SystemExit(error.returncode or 1)
    except Exception as error:
        print('[CircuitGit] 本地预览启动失败：' + str(error), file=sys.stderr, flush=True)
        raise SystemExit(1)
