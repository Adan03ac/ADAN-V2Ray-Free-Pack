#!/usr/bin/env python3
"""Merge public share-link subscriptions. No connectivity or security guarantees."""
import base64, json, urllib.request
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).parent
SCHEMES=("vless://","vmess://","trojan://","ss://","hy2://","hysteria2://")
def parse(raw):
    value=raw.decode("utf-8-sig",errors="replace").strip()
    if not any(s in value for s in SCHEMES):
        try:
            value=base64.b64decode("".join(value.split())+"==",validate=True).decode("utf-8")
        except (ValueError,UnicodeError):
            return []
    return [x.strip() for x in value.splitlines() if x.strip().startswith(SCHEMES)]
def main():
    seen=set(); links=[]; statuses=[]
    for url in ROOT.joinpath("sources.txt").read_text().splitlines():
        url=url.strip()
        if not url or url.startswith("#"): continue
        if not url.startswith("https://"): continue
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"ADAN-V2Ray-Free-Pack/2"})
            with urllib.request.urlopen(req,timeout=25) as resp:
                data=resp.read(8*1024*1024+1)
            if len(data)>8*1024*1024: raise ValueError("Feed too large")
            parsed=parse(data); added=0
            for item in parsed:
                if item not in seen: seen.add(item); links.append(item); added+=1
            statuses.append({"source":url,"status":"ok","parsed":len(parsed),"added":added})
        except Exception as exc:
            statuses.append({"source":url,"status":"error","detail":str(exc)[:160]})
    if links:
        plain="\n".join(links)+"\n"
        ROOT.joinpath("subscription.txt").write_text(plain)
        ROOT.joinpath("subscription_base64.txt").write_text(base64.b64encode(plain.encode()).decode()+"\n")
    ROOT.joinpath("status.json").write_text(json.dumps({"updated_at_utc":datetime.now(timezone.utc).isoformat(),"total":len(links),"sources":statuses,"warning":"Previous bank preserved if zero configs were retrieved." if not links else None},indent=2))
    print(f"Collected {len(links)} unique configs")
if __name__=="__main__": main()
