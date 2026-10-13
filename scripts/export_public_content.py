#!/usr/bin/env python3
"""Export only public CMS records and approved media for static publishing.

Run on the Flask host after reviewing the records to be published. This never
exports applications, contacts, admin credentials, or unpublished news.
"""
import argparse
import json
import shutil
import sqlite3
import sys
import os
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from public_content import EXPORT_CONTENT_KEYS


def export(database: Path, output: Path, static_root: Path) -> dict:
    if not database.is_file():
        raise FileNotFoundError(f'CMS database does not exist: {database}')
    snapshot = {'content': {}, 'assets': {}, 'news': [], 'faqs': []}
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('BEGIN')
        # These tables hold public CMS content. Private tables are never queried.
        for row in connection.execute('SELECT content_key, content_value FROM site_content'):
            # Raw style injection is not required in the exported public site.
            if row['content_key'] in EXPORT_CONTENT_KEYS:
                snapshot['content'][row['content_key']] = row['content_value']

        def published_media(path):
            if path.startswith('https://'):
                return path
            source = (static_root / path).resolve()
            if not source.is_relative_to(static_root.resolve()) or not source.is_file():
                raise ValueError(f'Public media is missing or outside static/: {path}')
            relative = Path('published') / Path(path)
            destination = static_root / relative
            if source != destination.resolve():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            return relative.as_posix()

        for row in connection.execute('SELECT asset_key, file_path FROM site_assets'):
            snapshot['assets'][row['asset_key']] = published_media(row['file_path'])
        for row in connection.execute('SELECT question, answer, sort_order FROM faq_items ORDER BY sort_order, id'):
            snapshot['faqs'].append(dict(row))
        for row in connection.execute('''SELECT id, title, excerpt, body, post_type, event_date, created_at
                                        FROM news_posts WHERE is_published = 1
                                        ORDER BY COALESCE(event_date, created_at) DESC, id DESC'''):
            post = dict(row)
            post['media_items'] = []
            for media in connection.execute('''SELECT file_path, media_type, caption FROM news_media
                                               WHERE post_id = ? ORDER BY sort_order, id''', (row['id'],)):
                item = dict(media)
                item['file_path'] = published_media(item['file_path'])
                post['media_items'].append(item)
            snapshot['news'].append(post)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=output.parent, prefix=output.name + '.', suffix='.tmp', encoding='utf-8', delete=False) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(snapshot, temporary, ensure_ascii=False, indent=2)
            temporary.write('\n')
        os.replace(temporary_path, output)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
    return snapshot


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'config/public_content.json')
    parser.add_argument('--static-root', type=Path, default=ROOT / 'static')
    options = parser.parse_args()
    result = export(options.database, options.output, options.static_root)
    print(f"Exported {len(result['news'])} published posts, {len(result['assets'])} assets, and {len(result['faqs'])} FAQs. No leads or contacts exported.")
