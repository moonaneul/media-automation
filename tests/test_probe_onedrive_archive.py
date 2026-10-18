"""No real Microsoft connection or church files in the OneDrive probe test."""
from pathlib import Path
from scripts import probe_onedrive_archive as probe


def test_onedrive_probe_defaults_to_no_remote_upload(tmp_path, monkeypatch, capsys):
    path=tmp_path/"work.db"
    path.write_bytes(b"untouched")
    before=path.read_bytes()
    actions=[]
    class Cloud:
        def __init__(self, store):
            self.store=store
        def status(self, _):
            return {"connected":True}
        def selected(self, purpose):
            assert purpose == "archive"
            return {"id":"test-folder"}
        def item(self, identifier):
            actions.append(("item",identifier))
            return {"id":"test-folder","folder":{}}
        def upload_file(self, *_):
            raise AssertionError("dry run must never upload")
    monkeypatch.setattr(probe, "OneDrive", Cloud)
    assert probe.run(path) == 0
    assert actions == [("item","test-folder")]
    assert "실제 업로드는 실행하지 않았습니다" in capsys.readouterr().out
    assert path.read_bytes() == before


def test_onedrive_probe_uploads_and_checks_two_test_files(tmp_path, monkeypatch, capsys):
    path=tmp_path/"work.db"
    path.write_bytes(b"untouched")
    files={}
    class Cloud:
        def __init__(self, store):
            self.store=store
        def status(self, _):
            return {"connected":True}
        def selected(self, purpose):
            assert purpose == "archive"
            return {"id":"test-folder"}
        def item(self, identifier):
            if identifier=="test-folder":
                return {"id":identifier,"folder":{}}
            name,data=files[identifier]
            return {"id":identifier,"name":name,"size":len(data),"file":{}}
        def upload_file(self, folder_id, name, content):
            assert folder_id == "test-folder"
            assert name.startswith("media-automation-TEST-")
            assert name not in files
            files[name] = (name,content)
            return {"id":name,"name":name,"size":len(content)}
        def _download(self, item):
            return files[item["id"]][1]
    monkeypatch.setattr(probe,"OneDrive",Cloud)
    assert probe.run(path, execute=True)==0
    assert len(files)==2
    assert sorted(len(x[1]) for x in files.values()) == [128,6*1024*1024]
    assert "재다운로드 SHA-256 일치" in capsys.readouterr().out
    assert path.read_bytes() == b"untouched"
