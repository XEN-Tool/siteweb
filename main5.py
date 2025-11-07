# ultimate_lookup_map.py
# Requirements: pip install flask requests pythonping

from flask import Flask, request, jsonify, render_template_string
import subprocess, re, requests
from pythonping import ping

app = Flask(__name__)

IPV4_RE = re.compile(r'\b(?:(?:25[0-5]|2[0-4]\d|1?\d{1,2})\.){3}(?:25[0-5]|2[0-4]\d|1?\d{1,2})\b')
IPV6_RE = re.compile(r'\b([0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}\b')

def run_nslookup(domain):
    try:
        result = subprocess.run(['nslookup', domain], capture_output=True, text=True, timeout=6)
        return result.stdout + "\n" + result.stderr
    except Exception as e:
        return f"ERROR: {e}"

def parse_ips(output):
    ips = []
    for m in IPV4_RE.finditer(output):
        ip = m.group(0)
        if ip not in [x['ip'] for x in ips]:
            ips.append({'ip': ip,'type':'IPv4'})
    for m in IPV6_RE.finditer(output):
        ip6 = m.group(0)
        if ip6 not in [x['ip'] for x in ips]:
            ips.append({'ip': ip6,'type':'IPv6'})
    return ips

def geoip_info(ip):
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,isp,lat,lon,org,query")
        data = r.json()
        if data.get('status') == 'success':
            return {
                'country': data.get('country'),
                'region': data.get('regionName'),
                'city': data.get('city'),
                'isp': data.get('isp'),
                'org': data.get('org'),
                'lat': data.get('lat'),
                'lon': data.get('lon')
            }
        else:
            return {'error': data.get('message')}
    except Exception as e:
        return {'error': str(e)}

def ping_ip(ip):
    try:
        r = ping(ip, count=1, timeout=2)
        return round(r.rtt_avg_ms,2)
    except:
        return None

@app.route('/')
def index():
    return render_template_string("""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ultimate Domain → IP Lookup</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
body{font-family:sans-serif;background:#0f1115;color:#fff;margin:0;padding:0;}
.header{display:flex;justify-content:space-between;align-items:center;padding:20px;background:#111827}
.logo{font-weight:bold;color:#000;font-size:1.5em} /* Logo en noir */
h1{font-size:2em;background:linear-gradient(90deg,#ff5f6d,#ffc371);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0}
.container{display:flex;flex-direction:column;align-items:center;padding:20px;gap:20px}
.form{display:flex;gap:10px;width:100%;max-width:800px}
input{flex:1;padding:10px;border-radius:8px;border:none;background:#071021;color:#fff;font-size:16px}
button{padding:10px 16px;border:none;border-radius:8px;font-weight:700;color:#071021;background:linear-gradient(90deg,#ff5f6d,#ffc371);cursor:pointer;transition:0.2s}
button:hover{transform:scale(1.05)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;width:100%;max-width:900px}
.leftbox,.rightbox{background:#111827;padding:20px;border-radius:12px;min-height:200px}
.domain-display{font-size:20px;font-weight:700;background:linear-gradient(90deg,#ff5f6d,#ffc371);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px;transition:0.3s}
.meta{color:#9aa3b2;font-size:13px;margin-bottom:12px}
.cards{display:flex;flex-direction:column;gap:12px}
.card{background:#1f2937;padding:14px;border-radius:10px;transition:0.3s;cursor:pointer}
.card:hover{transform:translateY(-4px);box-shadow:0 8px 20px rgba(255,95,109,0.3)}
.card-left{display:flex;align-items:center;font-weight:700;gap:6px}
.badge{padding:3px 8px;border-radius:12px;font-size:10px;font-weight:700;background:linear-gradient(90deg,#ff5f6d,#ffc371);color:#071021}
.copy-btn{cursor:pointer;font-size:12px;color:#ff5f6d}
.details{max-height:0;overflow:hidden;transition:max-height 0.3s ease;font-size:12px;margin-top:6px;color:#ccc;line-height:1.3em}
.details.show{max-height:500px}
.loader{border:4px solid #1a1a1a;border-top:4px solid #ff5f6d;border-radius:50%;width:24px;height:24px;animation:spin 1s linear infinite;margin-left:6px}
@keyframes spin{to{transform:rotate(360deg)}}
#map{height:200px;width:100%;border-radius:10px;margin-top:6px}
@media(max-width:800px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="header">
<h1>Domain → IP Lookup</h1>
<div class="logo">LOGO</div>
</div>
<div class="container">
<div class="form">
<input id="domain" placeholder="ex: example.com" autocomplete="off">
<button id="go">Chercher</button>
<button id="refresh">Rafraîchir</button>
<button id="export">Export CSV</button>
<div id="loader" class="loader" style="display:none"></div>
</div>
<div class="grid">
<div class="leftbox">
<div class="domain-display" id="domainText">—</div>
<div class="meta" id="metaText">Entrez un domaine et clique sur Chercher</div>
</div>
<div class="rightbox">
<div id="cards" class="cards"><div>Aucune recherche effectuée</div></div>
</div>
</div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
let resultsData=[]
const go=document.getElementById('go')
const refresh=document.getElementById('refresh')
const exportBtn=document.getElementById('export')
const domainInput=document.getElementById('domain')
const domainText=document.getElementById('domainText')
const metaText=document.getElementById('metaText')
const cards=document.getElementById('cards')
const loader=document.getElementById('loader')

function showLoader(show){loader.style.display=show?'inline-block':'none'}
function copyText(text){navigator.clipboard.writeText(text)}
function renderResults(domain,results){
domainText.textContent=domain
metaText.textContent='Dernier check: '+new Date().toLocaleString()
cards.innerHTML=''
resultsData=results
if(!results.length){cards.innerHTML='<div>Aucune IP trouvée</div>';return}
results.forEach(r=>{
const div=document.createElement('div')
div.className='card'
div.innerHTML=`
<div class="card-left">${r.ip}<span class="badge">${r.type}</span><span class="copy-btn" onclick="copyText('${r.ip}')">Copier</span></div>
<div class="details">
Ville: ${r.city||'-'}<br>
Région: ${r.region||'-'}<br>
Pays: ${r.country||'-'}<br>
ISP: ${r.isp||r.org||'-'}<br>
Lat: ${r.lat||'-'}, Lon: ${r.lon||'-'}<br>
Ping: ${r.ping!==null?r.ping+' ms':'N/A'}
<div id="map"></div>
</div>
`
div.querySelector('.card-left').addEventListener('click',()=>{
const det=div.querySelector('.details')
det.classList.toggle('show')
if(det.classList.contains('show') && r.lat && r.lon){
const mapDiv=det.querySelector('#map')
mapDiv.innerHTML=''
const map=L.map(mapDiv).setView([r.lat,r.lon],5)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
attribution:'&copy; OpenStreetMap contributors'
}).addTo(map)
L.marker([r.lat,r.lon]).addTo(map)
}
})
cards.appendChild(div)
})
}

async function lookup(domain){
showLoader(true)
domainText.textContent='…'
metaText.textContent='Recherche…'
cards.innerHTML=''
try{
const res=await fetch('/api/lookup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({domain})})
const data=await res.json()
showLoader(false)
if(data.error){metaText.textContent='Erreur: '+data.error;cards.innerHTML='<div>Impossible de récupérer</div>';return}
renderResults(domain,data.results)
}catch(err){showLoader(false);metaText.textContent='Erreur réseau';cards.innerHTML='<div>Impossible de contacter le serveur</div>'}
}

go.addEventListener('click',()=>{const d=domainInput.value.trim();if(d)lookup(d)})
refresh.addEventListener('click',()=>{const d=domainInput.value.trim();if(d)lookup(d)})
domainInput.addEventListener('keyup',e=>{if(e.key==='Enter') go.click()})

exportBtn.addEventListener('click',()=>{
if(!resultsData.length){alert('Aucune donnée à exporter');return}
const csvRows=[]
const headers=['IP','Type','Ville','Région','Pays','ISP','Org','Lat','Lon','Ping']
csvRows.push(headers.join(','))
resultsData.forEach(r=>{
csvRows.push([r.ip,r.type,r.city||'',r.region||'',r.country||'',r.isp||r.org||'',r.org||'',r.lat||'',r.lon||'',r.ping!==null?r.ping:''].join(','))
})
const blob=new Blob([csvRows.join('\\n')],{type:'text/csv'})
const url=URL.createObjectURL(blob)
const a=document.createElement('a')
a.href=url
a.download=(domainInput.value||'results')+'.csv'
document.body.appendChild(a)
a.click()
document.body.removeChild(a)
})
</script>
</body>
</html>
""")

@app.route('/api/lookup', methods=['POST'])
def api_lookup():
    data = request.get_json() or {}
    domain = (data.get('domain') or '').strip()
    if not domain:
        return jsonify({'error':'Domaine manquant'}),400
    raw = run_nslookup(domain)
    if raw.startswith("ERROR:"):
        return jsonify({'error': raw}),500
    ips = parse_ips(raw)
    for ip in ips:
        info = geoip_info(ip['ip'])
        ip.update(info)
        ip['ping'] = ping_ip(ip['ip'])
    ips.sort(key=lambda x: 0 if x['type']=='IPv4' else 1)
    return jsonify({'results': ips})

if __name__=='__main__':
    print("Lancement : ouvrez http://127.0.0.1:5000")
    app.run(debug=True)
