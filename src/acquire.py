"""Download only the three public W001 files, with recorded hashes and bounded size."""

import hashlib
import json
import urllib.request

from src.official_tables import ROOT


def run():
    manifest = json.loads(
        (ROOT / "reports/geourban_w001/sources_manifest.json").read_text(encoding="utf-8")
    )
    dest = ROOT / "data/raw/geourban_w001"
    dest.mkdir(parents=True, exist_ok=True)
    for item in manifest["files"]:
        p = dest / item["file"]
        if p.exists():
            if hashlib.sha256(p.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("Cache divergente: " + p.name)
            print("CACHE VERIFIED", p.name)
            continue
        request = urllib.request.Request(
            item["url"], headers={"User-Agent": "GeoUrbanRS/0.1 (research pilot)"}
        )
        limit = 30 * 1024 * 1024
        with urllib.request.urlopen(request, timeout=90) as r:
            chunks = []
            total = 0
            while block := r.read(1024 * 1024):
                total += len(block)
                if total > limit:
                    raise ValueError("Arquivo excede limite do piloto")
                chunks.append(block)
        blob = b"".join(chunks)
        if hashlib.sha256(blob).hexdigest() != item["sha256"]:
            raise ValueError("Fonte mudou; revisar versão antes de prosseguir")
        p.write_bytes(blob)
        print("DOWNLOADED VERIFIED", p.name, len(blob))


if __name__ == "__main__":
    run()
