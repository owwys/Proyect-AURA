"""Panel local autocontenido; sin dependencias ni peticiones externas."""

def _escape(value):
    return str(value).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')


def render(snapshot):
    data, status = snapshot['measurements'], snapshot['status']
    clock = status['clock']
    local = clock.get('local')
    values = {'co2':data['co2_ppm'], 'temperature':data['temperature_c'],
              'humidity':data['humidity_pct'], 'pressure':data['pressure_hpa'],
              'age':str(round(data['age_ms']/1000,1))+' s' if data['age_ms'] is not None else '--',
              'clock':local[11:16] if local else '--:--',
              'date':local[:10] if local else 'Sin ajustar',
              'zone':clock.get('timezone','UTC'),
              'source':{'manual':'Ajuste manual','ntp':'Sincronizada por NTP',
                        'retained':'Hora conservada','unset':'Sin ajustar'}.get(clock.get('source'),'Sin ajustar'),
              'version':status['firmware'], 'mode':'Datos simulados · DEMO' if data['demo'] else 'Datos del dispositivo'}
    for key in ('co2','temperature','humidity','pressure'):
        if values[key] is None: values[key] = '--'
    page = PAGE
    # Un solo recorrido: los valores nunca se reinterpretan como marcadores.
    chunks = page.split('@@')
    return ''.join(_escape(values[part]) if index%2 else part
                   for index,part in enumerate(chunks)).encode()


PAGE = '''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0c181b"><link rel="icon" href="data:,">
<title>AURA · Ambiente interior</title><style>
:root{color-scheme:dark;--bg:#0c181b;--panel:#15272b;--ink:#edf5f2;--muted:#a6bfbd;--accent:#7de3cc}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-variant-numeric:tabular-nums}
a{color:inherit;text-underline-offset:5px}button{font:inherit;cursor:pointer}a:focus-visible,button:focus-visible{outline:3px solid var(--accent);outline-offset:5px}
.wrap{max-width:1140px;margin:auto;padding:30px 40px}header{display:flex;align-items:center;justify-content:space-between;gap:20px}.brand{font-size:30px;font-weight:750;letter-spacing:-1.5px}.brand span{font-size:14px;font-weight:400;letter-spacing:0;margin-left:16px;color:var(--muted)}
.connection{display:flex;align-items:center;gap:9px;color:var(--accent);font-size:14px}.dot{height:8px;width:8px;background:currentColor;border-radius:50%;flex-shrink:0}.stale{color:#f4c898}
.intro{margin:64px 0 32px;display:flex;justify-content:space-between;align-items:flex-end;gap:24px}h1{font-size:clamp(32px,5vw,52px);line-height:1.06;letter-spacing:-2px;font-weight:550;margin:0 0 14px}.intro p{margin:0;color:var(--muted)}.mode{font-size:14px;color:var(--accent);white-space:nowrap}
.dashboard{display:grid;grid-template-columns:1.15fr 1fr;gap:16px}.hero{background:var(--accent);color:#102e2a;padding:32px;display:flex;flex-direction:column;justify-content:space-between;min-height:380px;border-radius:4px}.metric-title{font-weight:500;font-size:18px;margin:0}.hero-value{font-size:clamp(90px,11vw,144px);line-height:1;letter-spacing:-8px;font-weight:550;margin:28px 0 10px}.unit{font-size:22px;letter-spacing:0;font-weight:400;margin-left:10px}.hero-bottom{display:flex;justify-content:space-between;align-items:flex-end;gap:24px}.hero-bottom p{max-width:230px;font-size:14px;margin:0}.symbol{width:55px;height:55px;flex-shrink:0}
.side{display:grid;grid-template-columns:1fr 1fr;gap:16px}.metric{background:var(--panel);padding:26px;border-radius:4px;min-width:0;display:flex;flex-direction:column;justify-content:space-between}.metric p{margin:0;color:var(--muted);font-size:15px}.value{font-size:43px;letter-spacing:-1.5px;font-weight:500;line-height:1.2;margin-top:22px}.value small{font-size:18px;letter-spacing:0;color:var(--muted);margin-left:6px}.pressure{grid-column:1/-1;flex-direction:row;align-items:center;gap:12px}.pressure .value{margin:0}.pressure .value small{font-size:16px}
.details{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}.detail{padding:26px 30px;background:var(--panel);border-radius:4px}.detail-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:22px}.detail h2{font-size:17px;font-weight:500;margin:0}.detail-head span{color:var(--muted);font-size:13px}.clock{font-size:38px;letter-spacing:-1px;line-height:1.2}.clock-info{margin:8px 0 0;color:var(--muted);font-size:14px}.fresh{font-size:24px;line-height:1.5;margin:0}.note{font-size:14px;color:var(--muted);margin:9px 0 0}button{background:var(--ink);color:var(--bg);padding:9px 16px;border:0;border-radius:3px;font-size:14px;font-weight:600;transition:background .18s,transform .18s}button:hover{background:var(--accent)}button:active{transform:translateY(1px)}button:disabled{opacity:.6;cursor:wait}
footer{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;padding:28px 0 14px;font-size:13px;color:var(--muted)}footer nav{display:flex;gap:22px}noscript p{padding:16px;background:var(--panel)}.dashboard,.details{animation:arrive .4s ease-out}@keyframes arrive{from{opacity:.5;transform:translateY(8px)}to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
@media(max-width:760px){.wrap{padding:22px}.brand span{display:none}.intro{margin-top:44px;display:block}.mode{margin-top:18px}.dashboard{grid-template-columns:1fr}.hero{min-height:320px}.hero-value{font-size:116px}.details{grid-template-columns:1fr}.metric{min-height:150px}.pressure{min-height:120px}.intro p{max-width:32ch}.value{font-size:38px}footer{font-size:12px}}
@media(max-width:400px){.pressure{display:block}.pressure .value{margin-top:16px}.detail-head{align-items:flex-start}}
@media(max-width:360px){.wrap{padding:16px}.hero{padding:24px}.hero-value{font-size:96px}.metric{padding:18px}.unit{font-size:18px}.hero-bottom{gap:14px}}
</style></head><body><div class="wrap">
<header><div class="brand">AURA<span>One / Panel local</span></div><div id="connection" class="connection"><span class="dot" aria-hidden="true"></span><span id="connection-text">Conexión por comprobar</span></div></header>
<main><section class="intro"><div><h1>Tu ambiente, de un vistazo.</h1><p>Las últimas mediciones de tu AURA One.</p></div><div class="mode" id="mode">@@mode@@</div></section>
<div class="dashboard"><section class="hero" aria-labelledby="co2-title"><h2 class="metric-title" id="co2-title">Dióxido de carbono</h2><div class="hero-value"><span id="co2">@@co2@@</span><span class="unit">ppm</span></div><div class="hero-bottom"><p>Concentración de CO₂.<br>Una mirada al aire interior.</p><svg class="symbol" viewBox="0 0 60 60" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M3 18h34c14 0 14-16 4-16-6 0-8 4-8 7M3 29h47M3 40h30c16 0 16 17 5 17-5 0-8-3-8-7"/></svg></div></section>
<div class="side"><section class="metric"><h2 class="metric-title">Temperatura</h2><div class="value"><span id="temperature">@@temperature@@</span><small>°C</small></div><p>Ambiente interior</p></section><section class="metric"><h2 class="metric-title">Humedad</h2><div class="value"><span id="humidity">@@humidity@@</span><small>%</small></div><p>Humedad relativa</p></section><section class="metric pressure"><div><h2 class="metric-title">Presión atmosférica</h2><p>Última muestra</p></div><div class="value"><span id="pressure">@@pressure@@</span><small>hPa</small></div></section></div></div>
<div class="details"><section class="detail"><div class="detail-head"><h2>Hora del dispositivo</h2><span id="source">@@source@@</span></div><div class="clock" id="clock">@@clock@@</div><p class="clock-info"><span id="date">@@date@@</span> · <span id="zone">@@zone@@</span></p></section>
<section class="detail"><div class="detail-head"><h2>Actualización</h2><button id="refresh" type="button">Actualizar</button></div><p class="fresh">Muestra hace <span id="age">@@age@@</span></p><p class="note" id="notice" role="status" aria-live="polite">Vista inicial. Comprobando conexión…</p></section></div>
<noscript><p>JavaScript está desactivado. Estos datos corresponden a la carga de la página. Recarga para actualizarlos.</p></noscript></main>
<footer><span>AURA One · <span id="version">@@version@@</span> · Local-first</span><nav aria-label="Datos de la API"><a href="/api/measurements">Mediciones JSON</a><a href="/api/status">Estado JSON</a></nav></footer></div>
<script>
(()=>{'use strict';
const $=id=>document.getElementById(id),text=(id,v)=>{$(id).textContent=v},number=v=>typeof v==='number'&&Number.isFinite(v)?new Intl.NumberFormat('es-ES',{maximumFractionDigits:1}).format(v):'—';
let busy=false,timer=null,received=0,age=null;
const sources={manual:'Ajuste manual',ntp:'Sincronizada por NTP',retained:'Hora conservada',unset:'Sin ajustar'};
async function get(path){const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),4000);try{const r=await fetch(path,{cache:'no-store',signal:controller.signal});if(!r.ok)throw Error('HTTP');return await r.json()}finally{clearTimeout(timeout)}}
async function update(){if(busy||document.hidden)return;busy=true;$('refresh').disabled=true;clearTimeout(timer);
try{const m=await get('/api/measurements'),s=await get('/api/status');if(!['co2_ppm','temperature_c','humidity_pct','pressure_hpa','age_ms'].every(k=>(m[k]===null||(typeof m[k]==='number'&&Number.isFinite(m[k]))))||!s.clock)throw Error('Datos');
text('co2',m.co2_ppm===null?'--':number(m.co2_ppm));text('temperature',m.temperature_c===null?'--':number(m.temperature_c));text('humidity',m.humidity_pct===null?'--':number(m.humidity_pct));text('pressure',m.pressure_hpa===null?'--':number(m.pressure_hpa));
text('mode',m.demo?'Datos simulados · DEMO':'Datos del dispositivo');const c=s.clock; text('clock',c.local?c.local.slice(11,16):'--:--');text('date',c.local?c.local.slice(0,10):'Sin ajustar');text('zone',c.timezone||'UTC');text('source',sources[c.source]||'Sin ajustar');text('version',s.firmware);
received=performance.now();age=m.age_ms===null?null:Math.max(0,m.age_ms);text('age',age===null?'--':number(age/1000)+' s');$('connection').classList.remove('stale');text('connection-text','Conectado a AURA');text('notice','Actualización automática cada 5 s.');
}catch(e){$('connection').classList.add('stale');text('connection-text','Sin respuesta de AURA');text('notice','No se pudo actualizar. Se conservan los últimos datos; reintentando…');
}finally{busy=false;$('refresh').disabled=false;if(!document.hidden)timer=setTimeout(update,5000)}}
$('refresh').addEventListener('click',update);document.addEventListener('visibilitychange',()=>{clearTimeout(timer);if(!document.hidden)update()});
setInterval(()=>{if(age!==null)text('age',number((age+performance.now()-received)/1000)+' s')},1000);update();
})();
</script></body></html>'''
