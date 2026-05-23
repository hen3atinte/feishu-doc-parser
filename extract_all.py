"""Fully automated feishu doc extractor using direct API fetch."""
import subprocess
import json
import sys
import re
import urllib.parse

def run_js(code):
    """Run JavaScript in playwright browser and return result."""
    # Escape for command line
    escaped = code.replace('\\', '\\\\').replace('"', '\\"')
    cmd = f'playwright-cli --raw eval "{escaped}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    out = result.stdout.strip()
    # Parse JSON from output (it's already a JSON string)
    if out.startswith('"') and out.endswith('"'):
        out = out[1:-1]
    return out

def fetch_page(token, cursor='', page_num=1):
    """Fetch one page of doc content."""
    base = 'https://ta6hb0ysuge.feishu.cn/space/api/docx/pages/client_vars'
    params = {
        'id': token,
        'mode': '7',
        'limit': '239'
    }
    if cursor:
        params['cursor'] = cursor
    url = f'{base}?{urllib.parse.urlencode(params)}'
    
    code = f"""
    (async () => {{
      const resp = await fetch('{url}', {{credentials: 'include'}});
      const data = await resp.json();
      return JSON.stringify(data);
    }})()
    """
    
    out = run_js(code)
    try:
        return json.loads(out)
    except:
        print(f"  Failed to parse page {page_num}")
        return None

def get_block_text(block_data):
    """Extract text from a block's data."""
    text_obj = block_data.get('text', {})
    attribs = text_obj.get('initialAttributedTexts', {}).get('text', {})
    if not attribs:
        return ''
    sorted_keys = sorted(attribs.keys(), key=int)
    return ''.join(attribs[k] for k in sorted_keys)

def process_block(bid, bm, seen, depth=0):
    """Recursively process a block and its children."""
    lines = []
    block = bm.get(bid)
    if not block:
        return lines
    
    bd = block.get('data', {})
    bt = bd.get('type', '')
    children = bd.get('children', [])
    
    if bt in ('text', 'heading3', 'heading4', 'bullet', 'ordered', 'callout'):
        text = get_block_text(bd)
        if text and text not in seen:
            seen.add(text)
            if bt == 'heading3':
                lines.append(f'\n### {text}')
            elif bt == 'heading4':
                lines.append(f'\n#### {text}')
            elif bt == 'bullet':
                lines.append(f'- {text}')
            elif bt == 'ordered':
                lines.append(f'1. {text}')
            elif bt == 'callout':
                lines.append(f'> {text}')
            else:
                lines.append(text)
    elif bt == 'divider':
        lines.append('\n---\n')
    
    for child_id in children:
        child_lines = process_block(child_id, bm, seen, depth + 1)
        lines.extend(child_lines)
    
    return lines

def extract_doc(token, name):
    """Extract full doc content via API."""
    print(f'\n=== Extracting {name} (token: {token}) ===')
    
    seen = set()
    all_lines = []
    cursor = ''
    page = 1
    
    while True:
        print(f'  Fetching page {page}...')
        data = fetch_page(token, cursor, page)
        if not data or data.get('code') != 0:
            break
        
        d = data['data']
        bm = d.get('block_map', {})
        seq = d.get('block_sequence', [])
        
        # Title on first page
        if page == 1:
            meta = d.get('meta_map', {})
            for _, m in meta.items():
                if 'title' in m:
                    all_lines.append(f'# {m["title"]}')
                    break
        
        # Process blocks
        for bid in seq:
            lines = process_block(bid, bm, seen)
            all_lines.extend(lines)
        
        print(f'  Page {page}: {len(bm)} blocks, {len(all_lines)} lines so far')
        
        # Check for more pages
        cursors = d.get('next_cursors', [])
        has_more = d.get('has_more', False)
        if not has_more or not cursors:
            break
        cursor = cursors[0]
        page += 1
    
    # Save output
    output = '\n'.join(all_lines)
    fn = f'doc_{name}_complete.txt'
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(output)
    
    print(f'  Done! {len(all_lines)} lines, {len(output)} chars -> {fn}')
    return output

# Document list
docs = {
    '1hao': 'Q3DRdXN4doiwJHxhcqAc1BsFnbf',
    '2hao': 'DuBjdRoQFoyrkFxBJNQc3Qh6nlu',
    '3hao': 'LedPdsmi0of2YzxuMwCcYWBXnhd',
    '4hao': 'IBYid2gp0oL997xVFzTcJAb4nDg',
    '5hao': 'Pv4rdAp0eoUsIAxXtiQc3hUHnEd',
}

doc_name = sys.argv[1] if len(sys.argv) > 1 else None

if doc_name and doc_name in docs:
    token = docs[doc_name]
    extract_doc(token, doc_name)
elif not doc_name:
    # Extract all
    for name, token in docs.items():
        extract_doc(token, name)
else:
    print(f"Unknown doc: {doc_name}. Available: {list(docs.keys())}")
