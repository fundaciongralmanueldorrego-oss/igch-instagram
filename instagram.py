import argparse, hashlib, html, io, json, os, re, subprocess, time, warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
STATE = ROOT/'state.json'
BASE = CFG['portal'].rstrip('/')
NAVY, RED, WHITE, MUTED = '#101D35', '#DC2638', '#FFFFFF', '#D5DDE8'
W,H=1080,1350
Image.MAX_IMAGE_PIXELS=32_000_000
warnings.simplefilter('error',Image.DecompressionBombWarning)


def now(): return datetime.now(timezone.utc)
def stamp(): return now().isoformat()
def parse_date(s):
    try:
        d=datetime.fromisoformat(str(s).replace('Z','+00:00'))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except (ValueError,TypeError): return datetime.min.replace(tzinfo=timezone.utc)
def plain(s): return ' '.join(html.unescape(re.sub(r'<[^>]*>',' ',str(s or ''))).split())
def ident(a): return str(a.get('id') or a['slug'])
def article_url(a): return BASE+'/noticias/'+quote(a['slug'],safe='')+'/'
def font(size,bold=False):
    p=ROOT/'fonts/Montserrat.ttf'
    if p.exists():
        f=ImageFont.truetype(str(p),size)
        try: f.set_variation_by_axes([700 if bold else 500])
        except (OSError,ValueError): pass
        return f
    return ImageFont.truetype('/usr/share/fonts/truetype/lato/Lato-'+('Bold' if bold else 'Regular')+'.ttf',size)
def lines(d,text,f,width):
    result=[]; row=''
    for word in text.split():
        while d.textlength(word,font=f)>width:
            n=1
            while n<len(word) and d.textlength(word[:n+1],font=f)<=width: n+=1
            if row: result.append(row); row=''
            result.append(word[:n]); word=word[n:]
        if not word: continue
        trial=(row+' '+word).strip()
        if row and d.textlength(trial,font=f)>width: result.append(row); row=word
        else: row=trial
    if row: result.append(row)
    return result

def block(d,text,x,y,width,height,start,minimum,color,bold=False,max_lines=20):
    for size in range(start,minimum-1,-1):
        f=font(size,bold); ll=lines(d,text,f,width); step=int(size*1.19)
        if len(ll)<=max_lines and len(ll)*step<=height: break
    capacity=max(1,min(max_lines,height//step))
    if len(ll)>capacity:
        ll=ll[:capacity]; last=ll[-1]
        while last and d.textlength(last+'…',font=f)>width: last=last[:-1]
        ll[-1]=last.rstrip()+'…'
    for line in ll:
        d.text((x,y),line,font=f,fill=color,anchor='lt'); y+=step
    return y


def download_photo(a):
    src=urljoin(BASE+'/',str(a.get('image') or ''))
    if not a.get('image') or urlparse(src).scheme!='https': raise ValueError('sin imagen HTTPS')
    with requests.get(src,timeout=(8,25),stream=True,headers={'User-Agent':'InfoGranChaco editorial/1.0'}) as r:
        r.raise_for_status(); buf=bytearray()
        for chunk in r.iter_content(65536):
            buf.extend(chunk)
            if len(buf)>15*1024*1024: raise ValueError('imagen superior a 15 MiB')
    with Image.open(io.BytesIO(buf)) as im:
        im=ImageOps.exif_transpose(im); im.load()
        if min(im.size)<120: raise ValueError('resolución insuficiente')
        if im.mode in ('RGBA','LA') or 'transparency' in im.info:
            rgba=im.convert('RGBA'); bg=Image.new('RGBA',rgba.size,'white'); bg.alpha_composite(rgba); return bg.convert('RGB')
        return im.convert('RGB')


def render(a,path,photo=None):
    im=Image.new('RGB',(W,H),NAVY); d=ImageDraw.Draw(im)
    d.rectangle((0,0,W,14),fill=RED)
    logo=Image.open(ROOT/'assets/logo.jpg').convert('RGB'); logo.thumbnail((105,105))
    im.paste(logo,(54,38))
    d.text((181,46),CFG['name'],font=font(49,True),fill=WHITE,anchor='lt')
    d.text((183,108),'DIARIO DIGITAL  /  '+CFG['tagline'],font=font(22),fill=MUTED,anchor='lt')
    d.line((54,164,1026,164),fill='#3C4D64',width=2)
    cat=plain(a.get('category') or 'Actualidad').upper()[:45]
    title=plain(a.get('title')); sub=plain(a.get('subtitle') or a.get('seoDescription'))
    if photo is not None:
        # Encaje completo, sin deformar ni eliminar partes de la imagen.
        panel=Image.new('RGB',(1080,540),'#091326')
        p=ImageOps.contain(photo,panel.size,Image.Resampling.LANCZOS)
        panel.paste(p,((1080-p.width)//2,(540-p.height)//2)); im.paste(panel,(0,180))
        d.rectangle((54,748,60,782),fill=RED); d.text((76,748),cat,font=font(27,True),fill=WHITE,anchor='lt')
        y=block(d,title,54,802,972,240,59,34,WHITE,True,5)
        block(d,sub,54,y+22,972,1210-y-22,31,24,MUTED,False,5)
    else:
        d.rectangle((54,215,62,254),fill=RED); d.text((80,216),cat,font=font(31,True),fill=WHITE,anchor='lt')
        y=block(d,title,54,302,972,390,80,42,WHITE,True,7)
        block(d,sub,54,y+30,972,880-y-30,39,28,MUTED,False,6)
        d.rounded_rectangle((54,930,1026,1195),radius=18,fill='#1D304A',outline='#4E6079',width=2)
        d.rectangle((54,950,64,1175),fill=RED)
        block(d,CFG['notice'],92,980,885,180,40,30,WHITE,True,4)
    d.rectangle((0,1240,W,H),fill='#0A1427'); d.rectangle((0,1240,W,1247),fill=RED)
    d.text((54,1278),'@'+CFG['instagram'],font=font(28,True),fill=WHITE,anchor='lt')
    d.text((1026,1280),'LEÉ MÁS EN EL PORTAL',font=font(24,True),fill=MUTED,anchor='rt')
    path.parent.mkdir(parents=True,exist_ok=True); im.save(path,'JPEG',quality=90,optimize=True,subsampling=0)
    assert path.stat().st_size<8*1024*1024


def choose_photo(a):
    if a['slug'] in CFG['sensitive_slugs'] or a.get('sensitive') is True: return None,'marcada como sensible'
    try: return download_photo(a),'imagen adaptada'
    except (requests.RequestException,OSError,ValueError,Image.DecompressionBombWarning,Image.DecompressionBombError) as e:
        return None,'imagen no utilizable: '+type(e).__name__
def caption(a,fallback):
    bits=[plain(a.get('title')),plain(a.get('subtitle') or a.get('seoDescription'))]
    if fallback: bits.append(CFG['notice'])
    if a.get('showSource') not in (False,'false',0,'0') and a.get('sourceName'): bits.append('Fuente: '+plain(a['sourceName']))
    bits += ['Leé la nota completa en nuestro portal. Enlace en el perfil.',article_url(a),'#InfoGranChaco #Noticias #Chaco']
    return '\n\n'.join(x for x in bits if x)[:2190]


def articles():
    r=requests.get(BASE+'/data/list.json',params={'ig_sync':int(time.time())},timeout=(10,30)); r.raise_for_status()
    data=r.json(); arr=data['articles']; assert isinstance(arr,list)
    return [a for a in arr if a.get('slug') and plain(a.get('title')) and a.get('status','published')=='published' and a['slug'] not in CFG['excluded_slugs'] and (not a.get('expiresAt') or a.get('permanent') is True or parse_date(a['expiresAt'])>now())]

def select(arr,state,limit):
    start=max(parse_date(state.get('start_at')),now()-timedelta(hours=CFG['max_age_hours']))
    recent=sum(parse_date(p.get('published_at') or p.get('attempt_at'))>now()-timedelta(hours=24) for p in state['posts'].values())
    return sorted([a for a in arr if ident(a) not in state['posts'] and parse_date(a.get('publishedAt'))>=start],key=lambda a:parse_date(a.get('publishedAt')))[:max(0,min(limit,CFG['max_per_24h']-recent))]

def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def persist(state,files=()):
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    git('add','state.json',*(str(p.relative_to(ROOT)) for p in files))
        if git('diff','--cached','--name-only'):
        git('commit','-m','IGCH: estado editorial de Instagram [skip ci]'); git('push','origin','HEAD:'+os.environ['IG_BRANCH'])
    return git('rev-parse','HEAD')

def api(method,edge,**params):
    version=os.getenv('META_GRAPH_VERSION') or 'v25.0'
    if not re.fullmatch(r'v\d+\.\d+',version) or not re.fullmatch(r'\d+(?:/[a-z_]+)?',edge): raise ValueError('ruta Graph inválida')
    r=requests.request(method,'https://graph.facebook.com/'+version+'/'+edge,headers={'Authorization':'Bearer '+os.environ['META_PAGE_TOKEN']},timeout=(10,35),**({'params':params} if method=='GET' else {'data':params}))
    try: data=r.json()
    except ValueError: raise RuntimeError('Meta devolvió respuesta no JSON (HTTP '+str(r.status_code)+')') from None
    if not r.ok or 'error' in data:
        e=data.get('error',{}); raise RuntimeError(f"Meta HTTP {r.status_code}; code={e.get('code')}; subcode={e.get('error_subcode')}")
    return data

def wait_ready(cid):
    for _ in range(12):
        status=api('GET',cid,fields='status_code').get('status_code')
        if status in ('FINISHED','PUBLISHED','ERROR','EXPIRED'): return status
        time.sleep(5)
    return 'IN_PROGRESS'

def recover(state):
    for p in state['posts'].values():
        if p.get('status') not in ('pending','publishing'): continue
        s=api('GET',p['container'],fields='status_code').get('status_code')
        if s=='PUBLISHED':
            p.update(status='published',published_at=stamp()); persist(state)
        elif p['status']=='publishing':
            # Respuesta incierta: no repetir automáticamente una publicación.
            print('Revisión manual requerida:',p['slug'],s)
        elif s in ('ERROR','EXPIRED'):
            p.update(status='failed',reason=s); persist(state)
        elif s=='FINISHED': publish_container(state,p)

def publish_container(state,p):
    p.update(status='publishing',attempt_at=stamp()); persist(state)
    # El estado previo queda guardado incluso si Meta acepta la solicitud pero falla la respuesta.
    result=api('POST',os.environ['META_IG_ID']+'/media_publish',creation_id=p['container'])
    p.update(status='published',media_id=result['id'],published_at=stamp()); persist(state)
    print('Publicado:',p['slug'])

def send(a,state):
    photo,reason=choose_photo(a); key=hashlib.sha256(ident(a).encode()).hexdigest()[:24]
    p=ROOT/'media'/f'{key}.jpg'; render(a,p,photo)
    # URL inmutable: Meta recibe exactamente la versión enviada.
    sha=persist(state,[p]); url=f'https://raw.githubusercontent.com/{os.environ["GITHUB_REPOSITORY"]}/{sha}/media/{p.name}'
    for _ in range(5):
        try:
            r=requests.get(url,timeout=(8,15),stream=True)
            with r:
                if r.ok and r.headers.get('Content-Type','').split(';')[0]=='image/jpeg': break
        except requests.RequestException: pass
        time.sleep(4)
    else: raise RuntimeError('JPEG público no disponible; revisá que el repositorio sea público')
    cid=api('POST',os.environ['META_IG_ID']+'/media',image_url=url,caption=caption(a,photo is None))['id']
    rec={'slug':a['slug'],'container':cid,'status':'pending','attempt_at':stamp(),'template':'institutional' if photo is None else 'photo'}
    state['posts'][ident(a)]=rec; persist(state)
    s=wait_ready(cid)
    if s=='FINISHED': publish_container(state,rec)
    elif s=='PUBLISHED': rec.update(status='published',published_at=stamp()); persist(state)
    elif s in ('ERROR','EXPIRED'): rec.update(status='failed',reason=s); persist(state); print('Meta rechazó el contenedor:',a['slug'])
    else: print('Contenedor pendiente:',a['slug'])


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('mode',choices=['preview','publish','demo']); ap.add_argument('--slug',default=''); args=ap.parse_args()
    if args.mode=='demo':
        a={'id':'demo','slug':'demo','title':'El Gran Chaco fortalece la integración regional y los proyectos de desarrollo','subtitle':'Una agenda de trabajo reúne a las comunidades y promueve nuevas oportunidades para la región.','category':'Actualidad'}
        # Muestra ilustrativa de diseño, no es una noticia real.
        ph=Image.new('RGB',(1200,800),'#476977'); pd=ImageDraw.Draw(ph); pd.rectangle((0,500,1200,800),fill='#6B7950'); pd.text((60,60),'IMAGEN DE EJEMPLO',font=font(48,True),fill='white'); arr=[a]
    else:
        arr=articles(); ph=None
        if args.slug: arr=[a for a in arr if a['slug']==args.slug]
    if args.mode in ('preview','demo'):
        if not arr: raise RuntimeError('No hay noticias disponibles para previsualizar')
        a=max(arr,key=lambda a:parse_date(a.get('publishedAt'))); ph=ph if args.mode=='demo' else choose_photo(a)[0]
        render(a,ROOT/'preview/placa-fallback.jpg'); render(a,ROOT/'preview/placa-adaptada.jpg',ph)
        (ROOT/'preview/caption.txt').write_text(caption(a,ph is None),encoding='utf-8'); print('Previsualización lista; no se publicó nada.'); return
    if os.getenv('IG_ENABLED')!='true': raise RuntimeError('Publicación deshabilitada: IG_ENABLED debe ser true')
    if not os.getenv('META_PAGE_TOKEN') or not re.fullmatch(r'\d+',os.getenv('META_IG_ID','')): raise RuntimeError('Faltan META_PAGE_TOKEN o META_IG_ID')
    state=json.loads(STATE.read_text(encoding='utf-8'))
    if not state['start_at']:
        state['start_at']=stamp(); persist(state); print('Activación inicial: solo se publicarán noticias nuevas desde ahora.'); return
    recover(state)
    for a in select(arr,state,CFG['max_per_run']): send(a,state)

if __name__=='__main__': main()
