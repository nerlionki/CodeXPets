"""Publish this project's release using the existing Git credential helper.

Credentials remain in memory and are never written into reports or command lines.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request

REPO = 'nerlionki/CodeXPets'
ROOT = Path(__file__).resolve().parents[1]

def credential():
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    result = subprocess.run(['git', '-c', 'credential.interactive=never', 'credential', 'fill'],
                            input='protocol=https\nhost=github.com\n\n', text=True,
                            capture_output=True, env=env, timeout=30, cwd=ROOT)
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if result.returncode or not values.get('password'):
        raise RuntimeError('No existing GitHub credential available; no interactive login attempted')
    return values['password']

def request(token, url, method='GET', data=None, content_type='application/json'):
    if urllib.parse.urlsplit(url).hostname not in ('api.github.com', 'uploads.github.com'):
        raise RuntimeError('Unexpected GitHub API host')
    headers = {'User-Agent': 'CodeXPets-release', 'Accept': 'application/vnd.github+json',
               'Authorization': 'Bearer ' + token, 'X-GitHub-Api-Version': '2022-11-28'}
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False).encode('utf-8')
    if data is not None:
        headers['Content-Type'] = content_type
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise RuntimeError('GitHub API returned HTTP ' + str(error.code)) from None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['inspect', 'publish'])
    args = parser.parse_args()
    token = credential()
    api = 'https://api.github.com/repos/' + REPO
    repo = request(token, api)
    if not repo:
        raise RuntimeError('Repository not found or credential lacks access')
    if args.action == 'inspect':
        print(json.dumps({'repository': repo['full_name'], 'default_branch': repo['default_branch'],
                          'private': repo['private'], 'size': repo['size'], 'permissions': repo.get('permissions'),
                          'releases': [{k:r[k] for k in ['id','tag_name','draft','html_url']} for r in request(token, api+'/releases')]}, indent=2))
        return
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    notes = (ROOT/'release/1.0.0/RELEASE_NOTES.md').read_text(encoding='utf-8-sig')
    release = request(token, api+'/releases/tags/v1.0.0')
    if release and not release['draft']:
        raise RuntimeError('v1.0.0 is already published; refusing to overwrite')
    if not release:
        drafts = [r for r in request(token, api+'/releases') if r['tag_name']=='v1.0.0']
        release = drafts[0] if drafts else request(token, api+'/releases', 'POST', {
            'tag_name':'v1.0.0', 'target_commitish':sha, 'name':'CodeX Pets 1.0.0 · 小白和小鸡毛',
            'body':notes, 'draft':True, 'prerelease':False})
    release_api = api+'/releases/'+str(release['id'])
    assets = request(token, release_api+'/assets')
    published_assets = []
    for name, content_type in [('CodeXPets-1.0.0-Windows-Setup.exe','application/vnd.microsoft.portable-executable'),
                               ('maltese-retriever-1.0.0.zip','application/zip'),
                               ('SHA256SUMS.txt','text/plain'), ('INSTALL.txt','text/plain')]:
        content = (ROOT/'dist'/name).read_bytes()
        sha256 = hashlib.sha256(content).hexdigest()
        old = next((a for a in assets if a['name']==name), None)
        if old:
            if old.get('digest') != 'sha256:'+sha256:
                raise RuntimeError('Existing draft asset differs: '+name)
            asset = old
        else:
            upload = release['upload_url'].split('{',1)[0]+'?'+urllib.parse.urlencode({'name':name})
            asset = request(token, upload, 'POST', content, content_type)
        if asset['size'] != len(content) or asset.get('digest') != 'sha256:'+sha256:
            raise RuntimeError('Uploaded asset verification failed: '+name)
        published_assets.append({'name':name, 'size':len(content), 'sha256':sha256, 'url':asset['browser_download_url']})
    release = request(token, release_api, 'PATCH', {'draft':False, 'body':notes, 'make_latest':'true'})
    verified = request(token, api+'/releases/tags/v1.0.0')
    if not verified or verified['draft'] or len(verified['assets']) != 4:
        raise RuntimeError('Published release verification failed')
    report = {'ok':True, 'tag':'v1.0.0', 'commit':sha, 'release_url':verified['html_url'],
              'assets':published_assets, 'draft':verified['draft']}
    (ROOT/'release/1.0.0/github-published.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))

if __name__ == '__main__':
    main()
