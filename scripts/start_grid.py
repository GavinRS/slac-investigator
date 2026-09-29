"""Supervise an isolated loopback SuperLink and three instrument SuperNodes."""
import argparse
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from start_flower import ROOT, flower_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18000)
    parser.add_argument('--fleet-port', type=int, default=19093)
    parser.add_argument('--node-port', type=int, default=19094)
    args = parser.parse_args()
    ports = [args.port, args.fleet_port, *range(args.node_port, args.node_port + 3)]
    if len(set(ports)) != 5 or any(not 1024 <= port <= 65535 for port in ports):
        parser.error('Use five distinct, unprivileged ports.')
    for port in ports:
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
            except OSError:
                raise SystemExit(f'Port {port} is occupied. Existing services are unchanged.') from None
    try:
        env = flower_environment(os.environ, ROOT / '.env.flower.json')
    except (OSError, ValueError):
        raise SystemExit('Run .venv/bin/python scripts/configure_flower.py in your terminal first.') from None
    os.chdir(ROOT)
    subprocess.run([sys.executable, 'scripts/split_nodes.py'], env={**env, 'PYTHONPATH': str(ROOT)}, check=True)
    home = ROOT / '.flower-grid'
    home.mkdir(exist_ok=True)
    logs = ROOT / 'artifacts/grid-logs'
    logs.mkdir(parents=True, exist_ok=True)
    processes = []

    def launch(name, command, child_env):
        fd = os.open(logs / f'{name}.log', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, 'a') as output:
            proc = subprocess.Popen(command, env=child_env, stdin=subprocess.DEVNULL,
                                    stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(proc)

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        launch('superlink', [str(ROOT / '.venv/bin/flower-superlink'), '--insecure',
               '--host', '127.0.0.1', '--port', str(args.port),
               '--fleet-api-address', f'127.0.0.1:{args.fleet_port}',
               '--database', str(home / 'grid.sqlite'), '--disable-runtime-dependency-installation'],
               {**env, 'FLWR_HOME': str(home / 'superlink')})
        from flwr.proto.control_pb2 import ListRunsRequest, ListNodesRequest
        from flwr.supercore.control.control_http_client import ControlHttpClient
        client = ControlHttpClient(f'http://127.0.0.1:{args.port}', timeout=3)
        for _ in range(60):
            if processes[0].poll() is not None:
                raise RuntimeError('SuperLink exited; inspect local grid logs.')
            try:
                client.ListRuns(ListRunsRequest())
                break
            except Exception:
                time.sleep(.5)
        else:
            raise RuntimeError('SuperLink did not become ready.')
        for i, instrument in enumerate(('rf', 'ltu', 'dump')):
            data_dir = str(ROOT / 'nodes' / instrument)
            launch(instrument, [str(ROOT / '.venv/bin/flower-supernode'), '--insecure',
                   '--superlink', f'127.0.0.1:{args.fleet_port}', '--host', '127.0.0.1',
                   '--port', str(args.node_port + i), '--node-config', f'instrument="{instrument}"'],
                   {**env, 'FLWR_HOME': str(home / instrument), 'SLAC_NODE_DATA_DIR': data_dir,
                    'FLWR_FILESYSTEM_ALLOWED_DIRS': data_dir})
        for _ in range(60):
            if any(p.poll() is not None for p in processes):
                raise RuntimeError('A Grid service exited; inspect local grid logs.')
            nodes = client.ListNodes(ListNodesRequest())
            if sum(node.online_until > time.time() for node in nodes.nodes_info) >= 3:
                print(f'Three-node Grid ready at http://127.0.0.1:{args.port}. Ctrl+C stops these four services.', flush=True)
                break
            time.sleep(.5)
        else:
            raise RuntimeError('Three nodes did not register before the startup timeout.')
        client.close()
        while all(p.poll() is None for p in processes):
            time.sleep(1)
        raise RuntimeError('A Grid service exited; inspect local grid logs.')
    except KeyboardInterrupt:
        print('Stopping the isolated Grid services.', flush=True)
    finally:
        for proc in reversed(processes):
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for proc in processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()


if __name__ == '__main__':
    main()
