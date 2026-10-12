"""Small subprocess fixture for transport failures and conservative bindings."""
import json
import sys
import time
from pathlib import Path

mode = sys.argv[1]
opened = None
configured = False
query_count = 0


def read():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            raise SystemExit()
        if line == b'\r\n':
            break
        key, value = line.decode().split(':', 1)
        headers[key.lower()] = value.strip()
    return json.loads(sys.stdin.buffer.read(int(headers['content-length'])))


def send(message):
    body = json.dumps({'jsonrpc': '2.0', **message}, ensure_ascii=False).encode()
    sys.stdout.buffer.write(f'Content-Length: {len(body)}\r\n\r\n'.encode() + body)
    sys.stdout.buffer.flush()


while True:
    msg = read()
    method = msg.get('method')
    if method == 'initialize':
        if mode == 'exit':
            raise SystemExit(2)
        if mode == 'malformed':
            sys.stdout.buffer.write(b'Content-Length: -1\r\n\r\n')
            sys.stdout.buffer.flush()
            continue
        if mode == 'timeout':
            time.sleep(30)
        if mode == 'config':
            send({'id': 'config-1', 'method': 'workspace/configuration',
                  'params': {'items': [{'section': 'python.pythonPath'}, {'section': 'python.analysis'}]}})
            answer = read()
            configured = len(answer['result']) == 2 and bool(answer['result'][0])
        capabilities = {'definitionProvider': True}
        if mode == 'encoding':
            capabilities['positionEncoding'] = 'utf-8'
        send({'id': msg['id'], 'result': {'capabilities': capabilities,
              'serverInfo': {'name': 'fixture-lsp', 'version': '1'}}})
    elif method == 'textDocument/didOpen':
        opened = msg['params']['textDocument']
    elif method == 'textDocument/definition':
        query_count += 1
        if mode == 'config':
            assert configured
            # Hundreds of notifications must not fill the client's response queue.
            for _ in range(300):
                send({'method': 'textDocument/publishDiagnostics', 'params': {'diagnostics': []}})
        if mode == 'query_timeout' or (mode == 'partial_timeout' and query_count > 1):
            time.sleep(30)
        if mode == 'unicode':
            prefix = opened['text'].split('\n')[msg['params']['position']['line']].split('execute')[0]
            assert msg['params']['position']['character'] == len((prefix+'execut').encode('utf-16-le'))//2
        if mode == 'mutate':
            Path(sys.argv[2]).write_text('def changed(): pass\n', encoding='utf-8')
        location = {'uri': opened['uri'], 'range': {'start': {'line': 1, 'character': 8},
                                                    'end': {'line': 1, 'character': 15}}}
        if mode == 'external':
            location['uri'] = 'file:///outside-workspace/fake.py'
        if mode == 'non_callable':
            location['range'] = {'start': {'line': 5, 'character': 4}, 'end': {'line': 5, 'character': 10}}
        if mode == 'invalid_range':
            location['range']['start']['line'] = -1
        result = [] if mode == 'empty' else [location]
        if mode == 'ambiguous':
            result.append({'uri': opened['uri'], 'range': {'start': {'line': 3, 'character': 4},
                                                          'end': {'line': 3, 'character': 10}}})
        if mode == 'link':
            result = [{'targetUri': location['uri'], 'targetSelectionRange': location['range'],
                       'targetRange': {'start': {'line': 1, 'character': 4}, 'end': {'line': 1, 'character': 31}}}]
        send({'id': msg['id'], 'result': result})
    elif method == 'shutdown':
        send({'id': msg['id'], 'result': None})
    elif method == 'exit':
        raise SystemExit()
