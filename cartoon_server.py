#!/usr/bin/env python3
"""
Cartoon Media Server
Run: python3 cartoon_server.py
Open: http://localhost:7777
"""

import os, re, json, mimetypes, subprocess
from pathlib import Path
from flask import Flask, jsonify, send_file, abort, request, Response
import urllib.parse

app = Flask(__name__)

# ── Directory configuration ───────────────────────────────────────────────────
TV_DIRS = [
    "/mnt/E8A64F15A64EE3A2/Videos/TV Shows  (D)",
    "/media/sagan/BucketofCartoons/Videos/TV Shows  (E)",
]
MOVIE_DIRS = [
    "/mnt/E8A64F15A64EE3A2/Videos/Movies (D)",
    "/media/sagan/BucketofCartoons/Videos/Movies (E)",
]

# These dirs are expanded: each subfolder becomes its own show card,
# using that subfolder's own thumb.png (no campaign badge).
MULTI_SHOW_DIRS = [
    "/media/sagan/BucketofCartoons/Videos/TV Shows  (E)/True and the Rainbow Kingdom",
    "/media/sagan/BucketofCartoons/Videos/TV Shows  (E)/BabyTV",
    "/media/sagan/BucketofCartoons/Videos/TV Shows  (E)/JeeL",
    "/mnt/E8A64F15A64EE3A2/Videos/TV Shows  (D)/Fateen (فطين)",
]

# These dirs are listed as a flat video dump (all files recursively, no seasons).
MISC_DIRS = [
    "/mnt/E8A64F15A64EE3A2/Videos/TV Shows  (D)/Мisc",
]

# Podcast/audio directories that use cover1.png for all audio files
PODCAST_DIRS = [
    "/mnt/E8A64F15A64EE3A2/Videos/TV Shows  (D)/Zoey's Mythical Menagerie",
]

# Folders to skip entirely (by resolved absolute path).
SKIP_DIRS = [
    "/media/sagan/BucketofCartoons/Videos/TV Shows  (E)/.scripts",
    "/media/sagan/BucketofCartoons/Videos/TV Shows  (E)/Lost in Play",
]

# ── Video / subtitle extensions ───────────────────────────────────────────────
VIDEO_EXTS = {
    '.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv', '.flv',
    '.webm', '.ogv', '.ogg', '.mpg', '.mpeg', '.ts', '.m2ts',
    '.mts', '.vob', '.divx', '.xvid', '.rmvb', '.rm', '.3gp',
    '.3g2', '.f4v', '.asf', '.mxf', '.dv', '.qt', '.amv',
    '.m2v', '.mpv', '.tp', '.trp',
}
SUBTITLE_EXTS = {'.srt', '.vtt', '.ass', '.ssa', '.sub', '.idx'}

def is_video(p): return Path(p).suffix.lower() in VIDEO_EXTS
def is_subtitle(p): return Path(p).suffix.lower() in SUBTITLE_EXTS

def natural_key(s):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(s))]

def read_text(path):
    try: return Path(path).read_text(encoding='utf-8', errors='replace').strip()
    except: return None

def find_file(directory, *names):
    d = Path(directory)
    if not d.exists(): return None
    try:
        lower_map = {f.name.lower(): f for f in d.iterdir() if f.is_file()}
    except: return None
    for name in names:
        hit = lower_map.get(name.lower())
        if hit: return str(hit)
    return None

def enc(p): return urllib.parse.quote(str(p), safe='') if p else None
def dec(p): return urllib.parse.unquote(p) if p else ''

def should_skip(path):
    r = str(Path(path).resolve())
    return any(r == str(Path(s).resolve()) for s in SKIP_DIRS)

def is_multi_show(path):
    r = str(Path(path).resolve())
    return any(r == str(Path(m).resolve()) for m in MULTI_SHOW_DIRS)

def is_misc(path):
    r = str(Path(path).resolve())
    return any(r == str(Path(m).resolve()) for m in MISC_DIRS)

def is_podcast(path):
    r = str(Path(path).resolve())
    return any(r == str(Path(p).resolve()) for p in PODCAST_DIRS)

def get_disclaimers(directory):
    d = Path(directory)
    texts = []
    if not d.exists(): return texts
    try:
        for f in sorted(d.iterdir(), key=lambda x: natural_key(x.name)):
            if f.is_file() and f.name.lower().startswith('disclaimer') and f.suffix.lower() == '.txt':
                t = read_text(f)
                if t: texts.append(t)
    except: pass
    return texts

def parse_metadata(directory):
    """Parse metadata.txt file and return structured data."""
    meta_file = find_file(directory, 'metadata.txt')
    if not meta_file: return {}
    
    text = read_text(meta_file)
    if not text: return {}
    
    data = {}
    for line in text.split('\n'):
        if ':' not in line: continue
        key, val = line.split(':', 1)
        key = key.strip().lower()
        val = val.strip()
        if key in ['title', 'english', 'location', 'language', 'source', 'source2', 'description', 'date']:
            data[key] = val
    
    return data

def get_episodes(directory):
    """Direct video files in a single directory, sorted naturally."""
    d = Path(directory)
    if not d.exists(): return []
    try:
        videos = [f for f in d.iterdir() if f.is_file() and is_video(f)]
        return sorted(videos, key=lambda f: natural_key(f.name))
    except: return []

def get_episodes_recursive(directory):
    """All video files under a directory tree, sorted naturally."""
    d = Path(directory)
    if not d.exists(): return []
    videos = []
    try:
        for f in d.rglob('*'):
            if f.is_file() and is_video(f):
                videos.append(f)
    except: pass
    return sorted(videos, key=lambda f: natural_key(f.name))

def ep_obj(f):
    return {'path': enc(str(f)), 'name': f.name, 'stem': f.stem}

# ── Build show episode/season structure ───────────────────────────────────────
def build_show(show_path):
    d = Path(show_path)
    seasons, specials, loose, english = [], [], [], []
    if not d.exists():
        return {'seasons': seasons, 'specials': specials,
                'loose_episodes': loose, 'english_episodes': english}

    # If this is a Misc-style flat dump, return all videos recursively
    if is_misc(show_path):
        return {'seasons': [], 'specials': [], 'english_episodes': [],
                'loose_episodes': [ep_obj(f) for f in get_episodes_recursive(d)]}

    season_folders, english_folders, special_folder = [], [], None
    try:
        for sub in sorted(d.iterdir(), key=lambda x: natural_key(x.name)):
            if not sub.is_dir(): continue
            nl = sub.name.lower()
            if re.match(r'^season\s*\d+', nl):
                season_folders.append(sub)
            elif nl == 'specials':
                special_folder = sub
            elif 'english screening' in nl:
                english_folders.append(sub)
    except: pass

    if season_folders:
        for sf in sorted(season_folders, key=lambda x: natural_key(x.name)):
            m = re.search(r'(\d+)', sf.name)
            num = int(m.group(1)) if m else 0
            eps = get_episodes(sf)
            poster = find_file(show_path,
                               f'season{num:02d}-poster.jpg', f'season{num:02d}-poster.png',
                               f'season{num}-poster.jpg',     f'season{num}-poster.png')
            if not poster:
                poster = find_file(show_path, 'thumb.png', 'thumb.jpg', 'poster.png', 'poster.jpg')
            seasons.append({
                'number': num, 'name': sf.name,
                'poster': enc(poster),
                'episodes': [ep_obj(e) for e in eps],
            })
    else:
        loose = [ep_obj(e) for e in get_episodes(d)]

    if special_folder:
        specials = [ep_obj(e) for e in get_episodes(special_folder)]

    for ef in english_folders:
        for e in get_episodes(ef):
            english.append({**ep_obj(e), 'folder': ef.name})

    return {'seasons': seasons, 'specials': specials,
            'loose_episodes': loose, 'english_episodes': english}

# ── Get embedded subtitles ────────────────────────────────────────────────────
def get_embedded_subs(video_path):
    """Extract subtitle tracks from MKV/MP4 using ffprobe."""
    subs = []
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_entries',
             'stream=codec_type,codec_name,tags=title', str(video_path)],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'subtitle':
                    title = stream.get('tags', {}).get('title', f"Subtitle Track {len(subs)+1}")
                    codec = stream.get('codec_name', 'unknown')
                    subs.append({'title': title, 'codec': codec})
    except: pass
    return subs

# ── TV scan ───────────────────────────────────────────────────────────────────
def scan_tv():
    shows, misc_shows, seen = [], [], set()

    for tv_dir in TV_DIRS:
        td = Path(tv_dir)
        if not td.exists(): continue
        try:
            items = sorted(td.iterdir(), key=lambda x: natural_key(x.name))
        except: continue

        for show in items:
            if not show.is_dir(): continue
            if should_skip(show): continue

            # ── Misc flat-dump folder ────────────────────────────��────────
            if is_misc(show):
                key = str(show.resolve())
                if key in seen: continue
                seen.add(key)
                meta = parse_metadata(show)
                thumb = find_file(show, 'thumb.png', 'thumb.jpg', 'poster.png', 'poster.jpg')
                fanart = find_file(show, 'fanart.jpg', 'fanart.png')
                shows_entry = {
                    'name': meta.get('title', show.name),
                    'path': enc(str(show)),
                    'thumb': enc(thumb),
                    'fanart': enc(fanart),
                    'metadata': meta.get('description'),
                    'disclaimers': get_disclaimers(show),
                    'campaign': None,
                    'english': meta.get('english'),
                    'location': meta.get('location'),
                    'source': meta.get('source'),
                    'source2': meta.get('source2'),
                    'description': meta.get('description'),
                }
                misc_shows.append(shows_entry)
                continue

            # ── Multi-show directory (campaign) ───────────────────────────
            if is_multi_show(show):
                try:
                    subs = sorted(show.iterdir(), key=lambda x: natural_key(x.name))
                except: continue
                for sub in subs:
                    if not sub.is_dir(): continue
                    if should_skip(sub): continue
                    key = str(sub.resolve())
                    if key in seen: continue
                    seen.add(key)
                    meta = parse_metadata(sub) or parse_metadata(show)
                    thumb  = find_file(sub, 'thumb.png', 'thumb.jpg', 'poster.png', 'poster.jpg')
                    fanart = find_file(sub, 'fanart.jpg', 'fanart.png') or \
                             find_file(show, 'fanart.jpg', 'fanart.png')
                    disclaimers = get_disclaimers(sub) or get_disclaimers(show)
                    shows.append({
                        'name': meta.get('title', sub.name),
                        'path': enc(str(sub)),
                        'thumb': enc(thumb),
                        'fanart': enc(fanart),
                        'metadata': meta.get('description'),
                        'disclaimers': disclaimers,
                        'campaign': None,
                        'english': meta.get('english'),
                        'location': meta.get('location'),
                        'source': meta.get('source'),
                        'source2': meta.get('source2'),
                        'description': meta.get('description'),
                    })
                continue

            # ── Normal show ───────────────────────────────────────────────
            key = str(show.resolve())
            if key in seen: continue
            seen.add(key)
            meta = parse_metadata(show)
            thumb  = find_file(show, 'thumb.png', 'thumb.jpg', 'poster.png', 'poster.jpg')
            fanart = find_file(show, 'fanart.jpg', 'fanart.png')
            shows.append({
                'name': meta.get('title', show.name),
                'path': enc(str(show)),
                'thumb': enc(thumb),
                'fanart': enc(fanart),
                'metadata': meta.get('description'),
                'disclaimers': get_disclaimers(show),
                'campaign': None,
                'english': meta.get('english'),
                'location': meta.get('location'),
                'source': meta.get('source'),
                'source2': meta.get('source2'),
                'description': meta.get('description'),
            })

    # Combine normal shows + misc at end
    return sorted(shows, key=lambda s: natural_key(s['name'])) + sorted(misc_shows, key=lambda s: natural_key(s['name']))

def find_image_by_stem(directory, stem):
    """Find any image file whose stem matches, regardless of extension."""
    d = Path(directory)
    if not d.exists(): return None
    try:
        for f in d.iterdir():
            if f.is_file() and f.stem.lower() == stem.lower() and f.suffix.lower() in {
                '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.tif', '.avif'
            }:
                return str(f)
    except: pass
    return None

# ── Movies scan ───────────────────────────────────────────────────────────────
def scan_movies():
    movies, seen = [], set()
    for movie_dir in MOVIE_DIRS:
        md = Path(movie_dir)
        if not md.exists(): continue
        try:
            items = sorted(md.iterdir(), key=lambda x: natural_key(x.name))
        except: continue
        for item in items:
            key = str(item.resolve())
            if key in seen: continue
            if item.is_file() and is_video(item):
                seen.add(key)
                cover = find_image_by_stem(item.parent, item.stem)
                movies.append({'name': item.stem, 'path': enc(str(item)), 'cover': enc(cover)})
            elif item.is_dir():
                seen.add(key)
                vids = get_episodes(item)
                if not vids: continue
                video = vids[0]
                cover = find_image_by_stem(item, item.name) or \
                        find_image_by_stem(item, video.stem) or \
                        find_image_by_stem(md, item.name)
                movies.append({'name': item.name, 'path': enc(str(video)), 'cover': enc(cover)})
    return sorted(movies, key=lambda m: natural_key(m['name']))

# ── Subtitle helpers ──────────────────────────────────────────────────────────
def get_subs_for(video_path):
    """Get both external and embedded subtitles."""
    vp = Path(video_path)
    parent = vp.parent
    stem = vp.stem
    subs = []
    
    # External subtitles
    if parent.exists():
        try:
            for f in parent.iterdir():
                if f.is_file() and is_subtitle(f):
                    if f.stem.startswith(stem) or f.stem == stem:
                        subs.append({'file': enc(str(f)), 'title': f.stem, 'embedded': False})
        except: pass
        if not subs:
            try:
                for f in parent.iterdir():
                    if f.is_file() and is_subtitle(f):
                        subs.append({'file': enc(str(f)), 'title': f.stem, 'embedded': False})
            except: pass
    
    # Embedded subtitles
    embedded = get_embedded_subs(video_path)
    for e in embedded:
        subs.append({'file': enc(str(video_path)), 'title': e['title'], 'embedded': True})
    
    return subs

# ── Subtitle converters ───────────────────────────────────────────────────────
def srt_to_vtt(text):
    out = ['WEBVTT', '']
    for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        out.append(re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})', r'\1.\2', line))
    return '\n'.join(out)

def ass_time(t):
    try:
        parts = t.strip().split(':')
        h, m = parts[0].zfill(2), parts[1].zfill(2)
        s_cs = parts[2].split('.')
        s  = s_cs[0].zfill(2)
        cs = (s_cs[1] if len(s_cs) > 1 else '00').ljust(3, '0')[:3]
        return f'{h}:{m}:{s}.{cs}'
    except: return '00:00:00.000'

def ass_to_vtt(text):
    lines = ['WEBVTT', '']
    in_ev, fmt = False, []
    for line in text.replace('\r\n', '\n').split('\n'):
        if line.strip().lower() == '[events]': in_ev = True; continue
        if in_ev:
            if line.startswith('Format:'):
                fmt = [f.strip() for f in line[7:].split(',')]
            elif line.startswith('Dialogue:') and fmt:
                parts = line[9:].split(',', len(fmt) - 1)
                if len(parts) >= len(fmt):
                    d = dict(zip(fmt, parts))
                    start = ass_time(d.get('Start', '0:00:00.00'))
                    end   = ass_time(d.get('End',   '0:00:00.00'))
                    txt   = re.sub(r'\{[^}]*\}', '',
                                   d.get('Text', '').replace('\\N', '\n').replace('\\n', '\n'))
                    lines += [f'{start} --> {end}', txt, '']
    return '\n'.join(lines)

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/api/tv')
def api_tv(): return jsonify(scan_tv())

@app.route('/api/movies')
def api_movies(): return jsonify(scan_movies())

@app.route('/api/show')
def api_show():
    path = dec(request.args.get('path', ''))
    if not path or not Path(path).exists():
        return jsonify({'error': 'not found'}), 404
    return jsonify(build_show(path))

@app.route('/api/subtitles')
def api_subs():
    path = dec(request.args.get('path', ''))
    return jsonify(get_subs_for(path))

@app.route('/file')
def serve_file():
    path = dec(request.args.get('path', ''))
    if not path: abort(400)
    p = Path(path)
    if not p.exists() or not p.is_file(): abort(404)

    resolved = str(p.resolve())
    roots = ['/mnt/E8A64F15A64EE3A2', '/media/sagan/BucketofCartoons']
    if not any(resolved.startswith(r) for r in roots): abort(403)

    mime, _ = mimetypes.guess_type(str(p))
    if not mime: mime = 'application/octet-stream'

    suf = p.suffix.lower()
    if suf == '.srt':
        return Response(srt_to_vtt(read_text(p) or ''), mimetype='text/vtt')
    if suf in ('.ass', '.ssa'):
        return Response(ass_to_vtt(read_text(p) or ''), mimetype='text/vtt')
    if suf == '.vtt':
        return send_file(str(p), mimetype='text/vtt')

    rng = request.headers.get('Range', '')
    if rng and mime and mime.startswith('video'):
        size = p.stat().st_size
        m = re.match(r'bytes=(\d+)-(\d*)', rng)
        if m:
            start  = int(m.group(1))
            end    = int(m.group(2)) if m.group(2) else size - 1
            end    = min(end, size - 1)
            length = end - start + 1
            def gen():
                with open(str(p), 'rb') as f:
                    f.seek(start)
                    rem = length
                    while rem > 0:
                        chunk = f.read(min(65536, rem))
                        if not chunk: break
                        rem -= len(chunk)
                        yield chunk
            resp = Response(gen(), status=206, mimetype=mime)
            resp.headers['Content-Range']  = f'bytes {start}-{end}/{size}'
            resp.headers['Accept-Ranges']  = 'bytes'
            resp.headers['Content-Length'] = str(length)
            return resp

    return send_file(str(p), mimetype=mime)

@app.route('/')
def index():
    here = Path(__file__).parent
    return send_file(str(here / 'cartoon_client.html'))

if __name__ == '__main__':
    print("\n🎬  Cartoon Media Server")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("📺  Open: http://localhost:7777")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    app.run(host='0.0.0.0', port=7777, debug=False, threaded=True)