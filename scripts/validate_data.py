"""Validate notices before replacing production data."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def validate_document(data):
    if not isinstance(data, dict) or not isinstance(data.get('meta'), dict) or not isinstance(data.get('notices'), list):
        raise ValueError('Invalid bid document')
    meta = data['meta']
    if meta.get('source') != 'KONEPS OpenAPI' or meta.get('count') != len(data['notices']):
        raise ValueError('Invalid source or count')
    datetime.fromisoformat(meta['generatedAt'])
    ids = set()
    for n in data['notices']:
        if not isinstance(n, dict) or not n.get('id') or not n.get('title') or not n.get('noticeNo'):
            raise ValueError('Missing notice identifiers/title')
        if n['id'] in ids:
            raise ValueError('Duplicate notice')
        ids.add(n['id'])
        for key in ('publishedAt', 'closedAt'):
            if n.get(key):
                datetime.fromisoformat(n[key])
        if not isinstance(n.get('matches', {}).get('groupIds'), list):
            raise ValueError('Missing institution classification')


def main():
    if len(sys.argv) != 3:
        return 2
    source, destination = map(Path, sys.argv[1:])
    data = json.loads(source.read_text(encoding='utf-8'))
    validate_document(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, destination)
    print(f"Validated and installed {len(data['notices'])} notices")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
