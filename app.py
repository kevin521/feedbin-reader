import os
import requests
import trafilatura
from flask import Flask, render_template, request, jsonify, redirect, url_for
from requests.auth import HTTPBasicAuth

app = Flask(__name__)

FEEDBIN_USER = os.environ.get('FEEDBIN_USER')
FEEDBIN_PASS = os.environ.get('FEEDBIN_PASS')
BASE_URL = 'https://api.feedbin.com/v2'

def get_auth():
    return HTTPBasicAuth(FEEDBIN_USER, FEEDBIN_PASS)

def api_get(endpoint, params=None):
    r = requests.get(f"{BASE_URL}{endpoint}", auth=get_auth(), params=params)
    r.raise_for_status()
    return r.json()

def api_delete(endpoint, json_data=None):
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    r = requests.delete(f"{BASE_URL}{endpoint}", auth=get_auth(), json=json_data, headers=headers)
    print(f"DELETE {endpoint} with {json_data} -> {r.status_code} {r.text[:200] if r.text else ''}")
    return r.status_code

def api_post(endpoint, json_data=None):
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    r = requests.post(f"{BASE_URL}{endpoint}", auth=get_auth(), json=json_data, headers=headers)
    print(f"POST {endpoint} with {json_data} -> {r.status_code}")
    return r.status_code

def get_subscriptions():
    """Get all subscriptions with unread counts"""
    subs = api_get('/subscriptions.json')
    return {sub['feed_id']: sub['title'] for sub in subs}

@app.route('/')
def index():
    # Get filter param
    feed_filter = request.args.get('feed', None, type=int)

    # Get subscriptions for nav
    subscriptions = get_subscriptions()

    # Get unread entry IDs (sorted newest first - higher ID = newer)
    unread_ids = api_get('/unread_entries.json')
    unread_ids = sorted(unread_ids, reverse=True)

    if not unread_ids:
        return render_template('index.html', entry=None, position=0, total=0,
                             unread_ids=[], subscriptions=subscriptions, feed_filter=feed_filter)

    # If filtering by feed, we need to fetch entries to filter
    if feed_filter:
        # Fetch entries in batches to find ones matching the feed
        filtered_ids = []
        for i in range(0, min(len(unread_ids), 500), 100):
            batch = unread_ids[i:i+100]
            entries = api_get('/entries.json', {'ids': ','.join(map(str, batch))})
            for e in entries:
                if e['feed_id'] == feed_filter:
                    filtered_ids.append(e['id'])
        unread_ids = sorted(filtered_ids, reverse=True)

    if not unread_ids:
        return render_template('index.html', entry=None, position=0, total=0,
                             unread_ids=[], subscriptions=subscriptions, feed_filter=feed_filter)

    # Get position from query param, default to 0
    position = int(request.args.get('pos', 0))
    position = max(0, min(position, len(unread_ids) - 1))

    # Fetch the current entry
    entry_id = unread_ids[position]
    entry = api_get(f'/entries/{entry_id}.json')

    # Try to get extracted content for cleaner reading
    extracted_content = None

    # First try Feedbin's parser
    if entry.get('extracted_content_url'):
        try:
            r = requests.get(entry['extracted_content_url'], timeout=10)
            if r.status_code == 200:
                extracted = r.json()
                extracted_content = extracted.get('content')
        except:
            pass

    # If Feedbin parser failed or returned empty, try trafilatura
    if not extracted_content or len(extracted_content.strip()) < 100:
        try:
            downloaded = trafilatura.fetch_url(entry.get('url'))
            if downloaded:
                fallback_content = trafilatura.extract(downloaded, include_images=True, output_format='html')
                if fallback_content and len(fallback_content) > 100:
                    extracted_content = fallback_content
        except:
            pass

    # Use extracted content if available, otherwise fall back to entry content
    if extracted_content:
        entry['display_content'] = extracted_content
    else:
        entry['display_content'] = entry.get('content', '')

    # Get feed title for display
    feed_title = subscriptions.get(entry.get('feed_id'), 'Unknown')
    entry['feed_title'] = feed_title

    return render_template('index.html',
                         entry=entry,
                         position=position,
                         total=len(unread_ids),
                         unread_ids=unread_ids,
                         subscriptions=subscriptions,
                         feed_filter=feed_filter)

@app.route('/mark_read', methods=['POST'])
def mark_read():
    entry_id = request.form.get('entry_id', type=int)
    position = request.form.get('position', 0, type=int)
    feed_filter = request.form.get('feed_filter', type=int)

    if entry_id:
        api_delete('/unread_entries.json', {'unread_entries': [entry_id]})

    # Go to next article (position stays same since list shifts)
    return redirect(url_for('index', pos=position, feed=feed_filter))

@app.route('/mark_read_next', methods=['POST'])
def mark_read_next():
    """Mark current as read and go to next"""
    entry_id = request.form.get('entry_id', type=int)
    position = request.form.get('position', 0, type=int)
    feed_filter = request.form.get('feed_filter', type=int)

    if entry_id:
        api_delete('/unread_entries.json', {'unread_entries': [entry_id]})

    return redirect(url_for('index', pos=position, feed=feed_filter))

@app.route('/star', methods=['POST'])
def star():
    entry_id = request.form.get('entry_id', type=int)
    position = request.form.get('position', 0, type=int)
    feed_filter = request.form.get('feed_filter', type=int)

    if entry_id:
        api_post('/starred_entries.json', {'starred_entries': [entry_id]})

    return redirect(url_for('index', pos=position, feed=feed_filter))

@app.route('/skip', methods=['POST'])
def skip():
    """Go to next without marking read"""
    position = request.form.get('position', 0, type=int)
    feed_filter = request.form.get('feed_filter', type=int)
    return redirect(url_for('index', pos=position + 1, feed=feed_filter))

@app.route('/prev', methods=['POST'])
def prev():
    position = request.form.get('position', 0, type=int)
    feed_filter = request.form.get('feed_filter', type=int)
    return redirect(url_for('index', pos=max(0, position - 1), feed=feed_filter))

@app.route('/api/article')
def api_article():
    """JSON API for e-ink readers"""
    feed_filter = request.args.get('feed', None, type=int)
    position = request.args.get('pos', 0, type=int)

    # Get subscriptions
    subscriptions = get_subscriptions()

    # Get unread entry IDs
    unread_ids = api_get('/unread_entries.json')
    unread_ids = sorted(unread_ids, reverse=True)

    if not unread_ids:
        return jsonify({
            'total': 0,
            'position': 0,
            'article': None,
            'feeds': [{'id': k, 'title': v} for k, v in subscriptions.items()]
        })

    # Filter by feed if specified
    if feed_filter:
        filtered_ids = []
        for i in range(0, min(len(unread_ids), 500), 100):
            batch = unread_ids[i:i+100]
            entries = api_get('/entries.json', {'ids': ','.join(map(str, batch))})
            for e in entries:
                if e['feed_id'] == feed_filter:
                    filtered_ids.append(e['id'])
        unread_ids = sorted(filtered_ids, reverse=True)

    if not unread_ids:
        return jsonify({
            'total': 0,
            'position': 0,
            'article': None,
            'feed_filter': feed_filter,
            'feeds': [{'id': k, 'title': v} for k, v in subscriptions.items()]
        })

    # Clamp position
    position = max(0, min(position, len(unread_ids) - 1))

    # Fetch entry
    entry_id = unread_ids[position]
    entry = api_get(f'/entries/{entry_id}.json')

    # Get content (try extracted, then trafilatura, then raw)
    content = None
    if entry.get('extracted_content_url'):
        try:
            r = requests.get(entry['extracted_content_url'], timeout=10)
            if r.status_code == 200:
                extracted = r.json()
                content = extracted.get('content')
        except:
            pass

    if not content or len(content.strip()) < 100:
        try:
            downloaded = trafilatura.fetch_url(entry.get('url'))
            if downloaded:
                content = trafilatura.extract(downloaded, include_images=False, output_format='txt')
        except:
            pass

    if not content:
        # Strip HTML tags from raw content
        import re
        raw = entry.get('content', '')
        content = re.sub(r'<[^>]+>', '', raw)

    feed_title = subscriptions.get(entry.get('feed_id'), 'Unknown')

    return jsonify({
        'total': len(unread_ids),
        'position': position,
        'feed_filter': feed_filter,
        'article': {
            'id': entry['id'],
            'title': entry.get('title', 'Untitled'),
            'feed_id': entry.get('feed_id'),
            'feed': feed_title,
            'date': entry.get('published', '')[:10] if entry.get('published') else '',
            'url': entry.get('url', ''),
            'content': content
        },
        'feeds': [{'id': k, 'title': v} for k, v in subscriptions.items()]
    })

@app.route('/api/mark_read', methods=['POST'])
def api_mark_read():
    """Mark article as read via API"""
    data = request.get_json() or {}
    entry_id = data.get('id')

    if entry_id:
        api_delete('/unread_entries.json', {'unread_entries': [entry_id]})
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'Missing id'}), 400

@app.route('/api/star', methods=['POST'])
def api_star():
    """Star article via API"""
    data = request.get_json() or {}
    entry_id = data.get('id')

    if entry_id:
        api_post('/starred_entries.json', {'starred_entries': [entry_id]})
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'Missing id'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
