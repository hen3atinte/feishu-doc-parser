"""Improved parser for feishu doc API responses.
Supports: tables, images, nested lists, code blocks, todo items.
Fixes: duplicate content bug, excessive blank lines.
"""
import json
import os
import re

def get_text(bd):
    """Extract plain text from block data."""
    a = bd.get('text', {}).get('initialAttributedTexts', {}).get('text', {})
    return ''.join(a[str(k)] for k in sorted(a.keys(), key=int)) if a else ''

def get_text_rich(bd):
    """Extract text with link info (returns plain text for now)."""
    return get_text(bd)

def process(bid, bm, depth=0):
    """Recursively process a block and its children.
    Returns list of text lines.
    """
    lines = []
    b = bm.get(bid)
    if not b:
        return lines

    d = b.get('data', {})
    t = d.get('type', '')

    if t == 'text':
        txt = get_text(d)
        if txt:
            lines.append(txt)

    elif t == 'heading1':
        txt = get_text(d)
        if txt:
            lines.append(f'\n# {txt}\n')

    elif t == 'heading2':
        txt = get_text(d)
        if txt:
            lines.append(f'\n## {txt}\n')

    elif t == 'heading3':
        txt = get_text(d)
        if txt:
            lines.append(f'\n### {txt}\n')

    elif t == 'heading4':
        txt = get_text(d)
        if txt:
            lines.append(f'\n#### {txt}\n')

    elif t == 'bullet':
        txt = get_text(d)
        indent = '  ' * min(depth, 5)
        if txt:
            lines.append(f'{indent}- {txt}')

    elif t == 'ordered':
        txt = get_text(d)
        indent = '   ' * min(depth, 5)
        lines.append(f'{indent}1. {txt}')

    elif t == 'callout':
        txt = get_text(d)
        if txt:
            lines.append(f'\n> {txt}\n')

    elif t == 'divider':
        lines.append('\n---\n')

    elif t == 'code':
        txt = get_text(d)
        if txt:
            lines.append(f'\n```\n{txt}\n```\n')

    elif t == 'todo':
        txt = get_text(d)
        checked = d.get('todo', {}).get('checked', False)
        box = '[x]' if checked else '[ ]'
        if txt:
            lines.append(f'- {box} {txt}')

    elif t == 'table':
        # Parse table: children are table_row blocks
        rows = []
        for row_id in (d.get('children', [])):
            row_block = bm.get(row_id)
            if not row_block:
                continue
            row_data = row_block.get('data', {})
            if row_data.get('type') != 'table_row':
                continue
            cells = []
            for cell_id in row_data.get('children', []):
                cell_block = bm.get(cell_id)
                if cell_block:
                    cell_text = get_text(cell_block.get('data', {}))
                    cells.append(cell_text.strip())
                else:
                    cells.append('')
            rows.append(cells)

        if rows:
            # Build markdown table
            header = rows[0]
            sep = ['---'] * len(header)
            table_lines = []
            table_lines.append('| ' + ' | '.join(header) + ' |')
            table_lines.append('| ' + ' | '.join(sep) + ' |')
            for row in rows[1:]:
                # Pad row to match header length
                while len(row) < len(header):
                    row.append('')
                table_lines.append('| ' + ' | '.join(row) + ' |')
            lines.append('\n' + '\n'.join(table_lines) + '\n')

    elif t == 'image':
        src = d.get('image', {}).get('source_url', '')
        alt = get_text(d) or 'image'
        if src:
            lines.append(f'\n![{alt}]({src})\n')
        else:
            lines.append(f'\n![{alt}](image_placeholder)\n')

    elif t == 'link_card':
        url = d.get('link_card', {}).get('url', '')
        if url:
            lines.append(f'\n🔗 [{url}]({url})\n')

    elif t == 'file':
        fname = d.get('file', {}).get('file_name', 'file')
        src = d.get('file', {}).get('source_url', '')
        if src:
            lines.append(f'\n📎 [{fname}]({src})\n')
        else:
            lines.append(f'\n📎 {fname}\n')

    # Recurse into children (skip for table blocks — already handled above)
    if t != 'table':
        children = d.get('children', [])
        for cid in children:
            child_lines = process(cid, bm, depth + 1)
            lines.extend(child_lines)

    return lines


def parse_files(api_files):
    """Parse a list of API response files and return merged lines."""
    all_lines = []
    seen_lines = set()  # Track full lines to avoid exact duplicates

    for fn in sorted(api_files):
        if not os.path.exists(fn):
            print(f'  Warning: {fn} not found, skipping')
            continue

        with open(fn, 'r', encoding='utf-8') as f:
            raw = f.read()

        # Handle double-encoded JSON
        inner = json.loads(raw)
        if isinstance(inner, str):
            inner = json.loads(inner)

        d = inner.get('data', inner)
        bm = d.get('block_map', {})
        seq = d.get('block_sequence', [])

        for bid in seq:
            block_lines = process(bid, bm, depth=0)
            for line in block_lines:
                # Deduplicate only exact duplicate lines (not substrings)
                if line and line not in seen_lines:
                    seen_lines.add(line)
                    all_lines.append(line)

    return all_lines


def clean_output(lines):
    """Remove excessive blank lines and clean up formatting."""
    # Join, then clean up excessive blank lines
    text = '\n'.join(lines)

    # Replace 3+ newlines with 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove trailing whitespace on each line
    text = '\n'.join(line.rstrip() for line in text.split('\n'))

    # Clean up --- surrounded by blank lines
    text = re.sub(r'\n{2,}---\n{2,}', '\n\n---\n\n', text)

    return text.strip() + '\n'


# Map of doc output names to their API files
docs = {
    'doc1': ['api_page1.json', 'api_page2.json', 'api_page3.json'],
    'doc2': ['api2_p1.txt'],
    'doc3': ['api3_p1.txt', 'api3_p2.txt'],
    'doc4': ['api4_p1.txt'],
    'doc5': ['api5_p1.txt'],
}

if __name__ == '__main__':
    for name, files in docs.items():
        existing = [f for f in files if os.path.exists(f)]
        if not existing:
            print(f'{name}: No files found, skipping')
            continue

        print(f'\n=== Parsing {name} ===')
        print(f'  Files: {existing}')

        lines = parse_files(existing)
        output = clean_output(lines)

        # Extract title from first file
        title = ''
        with open(existing[0], 'r', encoding='utf-8') as f:
            raw = f.read()
        inner = json.loads(raw)
        if isinstance(inner, str):
            inner = json.loads(inner)
        meta = inner.get('data', {}).get('meta_map', {})
        for m in meta.values():
            if isinstance(m, dict) and 'title' in m:
                title = m['title']
                break

        if title:
            output = f'# {title}\n\n{output}'

        fn = f'{name}_complete.txt'
        with open(fn, 'w', encoding='utf-8') as f:
            f.write(output)

        print(f'  ✅ {len(lines)} lines, {len(output)} chars -> {fn}')
        if title:
            print(f'  Title: {title}')
