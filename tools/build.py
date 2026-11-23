import os, json, hashlib, zipfile, struct, re, time, collections, argparse
from pathlib import Path, PurePosixPath
parser=argparse.ArgumentParser(); parser.add_argument('--source',type=Path,required=True); parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]); args=parser.parse_args()
ROOT=args.source.resolve(); OUT=args.output.resolve(); WORK=OUT/'.build'
if not ROOT.is_dir(): raise ValueError('Source must be an existing full asset directory')
if OUT.is_relative_to(ROOT) or ROOT.is_relative_to(OUT): raise ValueError('Source and output directories must be separate')
WORK.mkdir(parents=True,exist_ok=True)
OUT.mkdir(parents=True,exist_ok=True); (OUT/'assets').mkdir(exist_ok=True); (OUT/'index').mkdir(exist_ok=True)
def save(path,obj):
    tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8'); os.replace(tmp,path)
def progress(stage,**kw): save(WORK/'png_build_progress.json',dict(stage=stage,**kw))
def valid(rel):
    parts=rel.split('/')
    if not rel or rel.startswith('/') or any(not p or p in ('.','..') or re.search(r'[<>:"\\|?*\x00-\x1f]',p) or p.endswith((' ','.')) or re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)',p,re.I) for p in parts): raise ValueError('Unsafe path: '+rel)
def real(rel):
    return not any(p=='__MACOSX' or p.startswith('._') or p.lower() in ('.ds_store','thumbs.db','desktop.ini') for p in rel.split('/'))
def png_info(b,source):
    if len(b)<24 or b[:8]!=b'\x89PNG\r\n\x1a\n' or b[12:16]!=b'IHDR' or b[8:12]!=b'\x00\x00\x00\r': raise ValueError('Invalid PNG: '+source)
    w,h=struct.unpack('>II',b[16:24]);
    if not w or not h: raise ValueError('Invalid dimensions: '+source)
    return w,h
pkgs={}
for top in ['rpg','platformer','UI','塔防']:
    roots = [p for category in (ROOT/top).iterdir() if category.is_dir() for p in category.iterdir() if p.is_dir()] if top in ('rpg','platformer') else [p for p in (ROOT/top).iterdir() if p.is_dir()]
    for p in roots:
        rel=p.relative_to(ROOT).as_posix()
        if not real(rel): continue
        pkgs[rel]={'id':hashlib.sha256(rel.encode()).hexdigest()[:16], 'source':rel,'output_prefix':'assets/'+rel, 'png_count':0,'bytes':0,'format':'png','aliases':[], 'license_sources':[], 'description_sources':[]}
prefixes=sorted(pkgs,key=len,reverse=True)
plan=[]; seen={}; excluded=collections.Counter(); excluded_bytes=collections.Counter()
def add(out,src,package,size,kind):
    valid(out); key=out.casefold()
    if key in seen: raise ValueError('Output path collision: '+out+' <> '+seen[key])
    seen[key]=out; plan.append((out,src,package,size,kind))
progress('scanning')
for top in ['rpg','platformer','UI','塔防']:
    for base,dirs,files in os.walk(ROOT/top):
        dirs[:]=[d for d in dirs if real((Path(base)/d).relative_to(ROOT).as_posix())]
        for name in files:
            p=Path(base)/name; rel=p.relative_to(ROOT).as_posix()
            if not real(rel) or p.suffix.lower()!='.png': continue
            size=p.stat().st_size
            if name.lower()=='coupon.png': excluded['file']+=1; excluded_bytes['file']+=size; continue
            package=next((k for k in prefixes if rel.startswith(k+'/')),None)
            if package is None: raise ValueError('Uncatalogued package: '+rel)
            add('assets/'+rel,rel,package,size,'file')
            if name.lower() in ('license.txt','readme.txt'): pass
for z in sorted((ROOT/'game kits').rglob('*.zip')):
    zr=z.relative_to(ROOT).as_posix(); prefix='assets/game-kits/'+z.stem
    pkgs[zr]={'id':hashlib.sha256(zr.encode()).hexdigest()[:16], 'source':zr,'output_prefix':prefix,'png_count':0,'bytes':0,'format':'zip/png','aliases':[], 'license_sources':[], 'description_sources':[]}
    with zipfile.ZipFile(z) as f:
        for i in f.infolist():
            member=i.filename.replace('\\','/')
            if i.is_dir() or not real(member): continue
            name=member.rsplit('/',1)[-1]
            if name.lower() in ('license.txt','license.md','readme.txt','readme.md'):
                pkgs[zr]['license_sources' if name.lower().startswith('license') else 'description_sources'].append({'archive':zr,'member':member})
            if not name.lower().endswith('.png'): continue
            if name.lower()=='coupon.png': excluded['zip']+=1; excluded_bytes['zip']+=i.file_size; continue
            valid(member); add(prefix+'/'+member,(zr,member),zr,i.file_size,'zip')
progress('plan_complete',planned=len(plan),bytes=sum(x[3] for x in plan),excluded=dict(excluded))
# Gather adjacent descriptions, retaining source references only.
for k,p in pkgs.items():
    if p['format']!='png': continue
    for base,dirs,files in os.walk(ROOT/Path(k)):
        dirs[:]=[d for d in dirs if real((Path(base)/d).relative_to(ROOT).as_posix())]
        for n in files:
            if n.lower() in ('readme.txt','readme.md','readme.pdf','license.txt','license.md','license.pdf'):
                p['license_sources' if n.lower().startswith('license') else 'description_sources'].append((Path(base)/n).relative_to(ROOT).as_posix())
hashes=collections.defaultdict(list); package_hashes=collections.defaultdict(list); total=0; maxrow=None
old_sources={}
old_index=OUT/'index/files.jsonl'
if old_index.exists():
    with old_index.open(encoding='utf8') as f:
        for line in f:
            old=json.loads(line); old_sources[old['path']]=old['source']
index_tmp=OUT/'index/files.jsonl.tmp'
with index_tmp.open('w',encoding='utf8',newline='\n') as index:
    current_zip=None; zf=None
    try:
        for n,(out,src,pkg,size,kind) in enumerate(plan,1):
            if kind=='file':
                source={'kind':'file','path':src}; data=(ROOT/Path(src)).read_bytes()
            else:
                archive,member=src; source={'kind':'zip','archive':archive,'member':member}
                if current_zip!=archive:
                    if zf: zf.close()
                    zf=zipfile.ZipFile(ROOT/Path(archive)); current_zip=archive
                data=zf.read(member)
            if len(data)!=size: raise ValueError('Source size changed: '+str(src))
            w,h=png_info(data,str(src)); digest=hashlib.sha256(data).hexdigest(); dest=OUT/Path(out); dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():
                if old_sources.get(out)!=source or not dest.is_file() or hashlib.sha256(dest.read_bytes()).hexdigest()!=digest: raise ValueError('Existing output lacks matching provenance or differs: '+out)
            else:
                with dest.open('xb') as target: target.write(data)
            row={'path':out,'source':source,'bytes':size,'sha256':digest,'width':w,'height':h}
            index.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
            hashes[digest].append(out); package_hashes[pkg].append(digest); pkgs[pkg]['png_count']+=1; pkgs[pkg]['bytes']+=size; total+=size
            if maxrow is None or size>maxrow['bytes']: maxrow={'path':out,'bytes':size}
            if n%1000==0: progress('extracting',completed=n,planned=len(plan),bytes=total)
    finally:
        if zf: zf.close()
os.replace(index_tmp,OUT/'index/files.jsonl')
# Hash mirrors and match against output. Use hash as a compact join key into files.jsonl.
mirror_total=0; mirror_excluded=0; unmatched=[]; mirror_groups=collections.defaultdict(list)
with (OUT/'index/mirrors.jsonl.tmp').open('w',encoding='utf8',newline='\n') as f:
    for base,dirs,files in os.walk(ROOT/'PNG'):
        dirs[:]=[d for d in dirs if real((Path(base)/d).relative_to(ROOT).as_posix())]
        for name in files:
            p=Path(base)/name; rel=p.relative_to(ROOT).as_posix()
            if not real(rel) or p.suffix.lower()!='.png': continue
            if name.lower()=='coupon.png': mirror_excluded+=1; continue
            data=p.read_bytes(); png_info(data,rel); digest=hashlib.sha256(data).hexdigest()
            if digest not in hashes: unmatched.append(rel)
            parts=rel.split('/'); group='/'.join(parts[:3]); mirror_groups[group].append(digest)
            f.write(json.dumps({'source':rel,'sha256':digest},ensure_ascii=False,separators=(',',':'))+'\n'); mirror_total+=1
if unmatched: raise ValueError('Unmatched mirrors: '+json.dumps(unmatched,ensure_ascii=False))
os.replace(OUT/'index/mirrors.jsonl.tmp',OUT/'index/mirrors.jsonl')
# Assign aliases only when all mirror content is present in a package.
sets={k:set(v) for k,v in package_hashes.items()}
for group,digests in mirror_groups.items():
    ds=set(digests)
    for k,s in sets.items():
        if ds and ds.issubset(s): pkgs[k]['aliases'].append(group)
# Flag full-content duplicate packages via sorted hash multisets.
groups=collections.defaultdict(list)
for k,v in package_hashes.items(): groups[hashlib.sha256(('\n'.join(sorted(v))).encode()).hexdigest()].append(k)
for g in groups.values():
    if len(g)>1:
        for k in g: pkgs[k]['content_duplicate_of']=[x for x in g if x!=k]
save(OUT/'index/packages.json',sorted(pkgs.values(),key=lambda x:x['source']))
progress('verifying',completed=0,planned=len(plan))
verified=0; verified_bytes=0
with (OUT/'index/files.jsonl').open(encoding='utf8') as f:
    for line in f:
        row=json.loads(line); data=(OUT/Path(row['path'])).read_bytes()
        if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256'] or png_info(data,row['path'])!=(row['width'],row['height']): raise ValueError('Output verification failed: '+row['path'])
        verified+=1; verified_bytes+=len(data)
        if verified%2000==0: progress('verifying',completed=verified,planned=len(plan))
if verified!=len(plan) or verified_bytes!=sum(x[3] for x in plan): raise ValueError('Verification totals mismatch')
sizes_by_path={x[0]:x[3] for x in plan}; unique_bytes=sum(sizes_by_path[paths[0]] for paths in hashes.values())
summary={'scope':['rpg','platformer','UI','塔防','game kits ZIP PNGs'], 'png_count':verified,'bytes':verified_bytes,'unique_sha256_count':len(hashes),'unique_content_bytes':unique_bytes,'excluded_coupon':{'count':sum(excluded.values()),'bytes':sum(excluded_bytes.values()),'by_source':dict(excluded),'bytes_by_source':dict(excluded_bytes),'mirror_count':mirror_excluded},'mirror_count':mirror_total,'mirror_match_count':mirror_total-len(unmatched),'mirror_join':'Join mirrors.sha256 to files.sha256 for all matching paths','max_png':maxrow,'verification':{'planned_count_matches':True,'planned_bytes_match':True,'output_sha256_and_dimensions_verified':True,'mirror_hashes_matched':True}}
save(OUT/'index/summary.json',summary); save(WORK/'png_build_report.json',summary); progress('complete',**summary)

