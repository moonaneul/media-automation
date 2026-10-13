from media_automation.web.deployment_check import check_deployment


def test_production_check_rejects_placeholder_and_never_exposes_password(tmp_path):
    password = tmp_path/'password'
    secret = 'private-access-value-long-enough'
    password.write_text(secret)
    password.chmod(0o600)
    env = {'MEDIA_PUBLIC_ORIGIN':'https://REPLACE_WITH_REAL_DOMAIN', 'MEDIA_ACCESS_PASSWORD_FILE':str(password)}
    report = check_deployment(tmp_path, tmp_path/'work.db', environ=env)
    checks = {c['name']:c['ok'] for c in report['checks']}
    assert checks['접속 암호']
    assert not checks['HTTPS 주소']
    assert not report['ready']
    assert secret not in str(report)
    env['MEDIA_PUBLIC_ORIGIN'] = 'https://media.example.org'
    password.chmod(0o644)
    checks = {c['name']:c['ok'] for c in check_deployment(tmp_path,tmp_path/'work.db',environ=env)['checks']}
    assert checks['HTTPS 주소']
    assert not checks['접속 암호']


def test_deployment_checks_cloud_media_and_people_dependencies(tmp_path, monkeypatch):
    from media_automation.web import deployment_check
    absent = {'msal', 'cryptography', 'requests', 'imageio_ffmpeg'}
    monkeypatch.setattr(deployment_check.importlib.util, 'find_spec',
                        lambda name: None if name in absent else object())
    checks = {c['name']: c['ok'] for c in check_deployment(tmp_path, tmp_path/'work.db', environ={})['checks']}
    assert all(not checks['Python '+name] for name in absent)
    assert not checks['이름·직분 명단']
    folder = tmp_path/'data/private'
    folder.mkdir(parents=True)
    (folder/'people.json').write_text('{}')
    assert next(c['ok'] for c in check_deployment(tmp_path,tmp_path/'work.db',environ={})['checks'] if c['name']=='이름·직분 명단')
