const $=s=>document.querySelector(s),A=$('#app');let me=null,charts=[],map,routeLayer;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(u,body,method){const o={method:method||(body?'POST':'GET'),headers:{'Content-Type':'application/json'}};if(body)o.body=JSON.stringify(body);
 const r=await fetch(u,o),d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.error||'Request failed');return d}
function toast(m,bad){const t=$('#toast');t.textContent=m;t.className='show'+(bad?' bad':'');setTimeout(()=>t.className='',3200)}
const go=h=>location.hash=h,fmt=d=>d?d.replace('T',' ').slice(0,16):'',badge=s=>`<span class="badge ${s}">${s}</span>`;
const form=e=>{e.preventDefault();return Object.fromEntries(new FormData(e.target))};
const act=f=>async(...a)=>{try{await f(...a)}catch(e){toast(e.message,1)}};
const localDT=h=>{const d=new Date(Date.now()+h*36e5-new Date().getTimezoneOffset()*6e4);return d.toISOString().slice(0,16)};
const tiles=s=>[['🍱',s.donated.toLocaleString(),'Servings donated'],['♻️',s.waste_kg.toLocaleString()+' kg','Food waste prevented*'],['🏪',s.restaurants,'Restaurants registered'],['🤝',s.ngos,'NGOs connected'],['🌍',s.co2_kg.toLocaleString()+' kg','CO₂e avoided*']]
 .map(t=>`<div class=card><div class=stat>${t[0]} ${t[1]}<small>${t[2]}</small></div></div>`).join('');

function nav(){const r=location.hash.slice(2),l=(h,t)=>`<a class="${r==h?'on':''}" href="#/${h}">${t}</a>`;
 $('nav').innerHTML=`<b onclick="go('#/')">🌱 FoodBridge</b>${l('','Home')}${l('map','Map')}${l('analytics','Analytics')}${l('ai','AI Insights')}`+
 (me?l('dashboard','Dashboard')+`<a onclick="logout()">Logout (${esc(me.name.split(' ')[0])})</a>`:l('login','Login')+`<a class="btn" href="#/register">Register</a>`)}
const logout=act(async()=>{await api('/api/logout',{});me=null;go('#/');render()});

async function render(){charts.forEach(c=>c.destroy());charts=[];if(map){map.remove();map=null}
 const r=location.hash.slice(2)||'home',v={home,login,register,dashboard,map:mapView,analytics,ai}[r]||home;
 nav();try{await v()}catch(e){toast(e.message,1)}window.scrollTo(0,0)}

async function home(){const s=await api('/api/stats');A.innerHTML=`<section class=hero><h1>Turn surplus food into<br>meals, not waste.</h1>
 <p>FoodBridge connects restaurants with NGOs in real time, so good food reaches people before it expires.</p>
 <a class=btn href="#/register">Get started</a> <a class="btn o" href="#/login">Login</a> <a class="btn o" href="#/dashboard">Dashboard</a></section>
 <div class=grid>${tiles(s)}</div><p class=mu>*Estimates: 0.4 kg per serving, 2.5 kg CO₂e per kg of food.</p><h2>How it works</h2>
 <div class=grid>${[['🍽️','List surplus','Restaurants post food, quantity and expiry in seconds.'],['📍','Match nearby','NGOs filter by location and quantity; rule-based suggestions rank the closest NGOs.'],['🚚','Collect & track','Request, accept, collect — every status is tracked end to end.']].map(x=>`<div class=card><div style="font-size:32px">${x[0]}</div><h3>${x[1]}</h3><p class=mu>${x[2]}</p></div>`).join('')}</div>
 <div class=card><h3>🌍 Why it matters</h3><p class=mu>Food sent to landfill releases methane, a potent greenhouse gas, while many people go hungry. Redirecting edible surplus cuts both problems at once.</p>
 <p class=mu><b>Demo logins</b> (password <code>demo123</code>): green@demo.test (restaurant), annapurna@demo.test (NGO). Admin: admin@foodbridge.test / admin123.</p></div>`}

function login(){A.innerHTML=`<form class="card auth" onsubmit="doLogin(event)"><h2>Welcome back</h2><label>Email</label><input name=email type=email required>
 <label>Password</label><input name=password type=password required><button class=btn style="width:100%">Login</button>
 <p class=mu>No account? <a href="#/register">Register</a></p></form>`}
const doLogin=act(async e=>{me=(await api('/api/login',form(e))).user;toast('Logged in');go('#/dashboard');render()});
function register(){A.innerHTML=`<form class="card auth" onsubmit="doReg(event)"><h2>Create account</h2><label>I am a</label>
 <select name=role><option value=restaurant>Restaurant</option><option value=ngo>NGO</option></select>
 <label>Organisation name</label><input name=name required minlength=2><label>Email</label><input name=email type=email required>
 <label>Password (min 6)</label><input name=password type=password required minlength=6><label>Phone</label><input name=phone>
 <label>Address</label><input name=address required><div class=grid2><div><label>Latitude</label><input name=lat id=lat value=12.9716 required></div>
 <div><label>Longitude</label><input name=lng id=lng value=77.5946 required></div></div>
 <button type=button class="btn s" onclick="locate()">📍 Use my location</button><br><br><button class=btn style="width:100%">Register</button></form>`}
const locate=()=>navigator.geolocation?navigator.geolocation.getCurrentPosition(p=>{$('#lat').value=p.coords.latitude.toFixed(5);$('#lng').value=p.coords.longitude.toFixed(5)},()=>toast('Location blocked',1)):toast('Not supported',1);
const doReg=act(async e=>{me=(await api('/api/register',form(e))).user;toast('Welcome to FoodBridge!');go('#/dashboard');render()});

async function dashboard(){if(!me){go('#/login');return}({restaurant:restDash,ngo:ngoDash,admin:adminDash})[me.role]()}
function reqTable(rows,el){const R=me.role;$(el).innerHTML=rows.length?`<table><tr><th>Food</th><th>Qty</th><th>${R=='ngo'?'Restaurant':'NGO'}</th><th>Status</th><th></th></tr>`+rows.map(r=>`<tr><td>${esc(r.food)}</td><td>${r.qty}</td><td>${esc(R=='ngo'?r.rname:r.nname)}</td><td>${badge(r.status)}</td><td>`+
 (R=='restaurant'&&r.status=='pending'?`<button class="btn s" onclick="rAct(${r.id},'accept')">Accept</button> <button class="btn s r" onclick="rAct(${r.id},'reject')">Reject</button>`:'')+
 (r.status=='accepted'?`<button class="btn s" onclick="rAct(${r.id},'collect')">Mark collected</button>`:'')+
 (R=='ngo'&&['pending','accepted'].includes(r.status)?` <button class="btn s r" onclick="rAct(${r.id},'cancel')">Cancel</button>`:'')+`</td></tr>`).join('')+'</table>':'<p class=mu>Nothing here yet.</p>'}
const rAct=act(async(i,a)=>{await api(`/api/requests/${i}/${a}`,{});toast('Updated');render()});

async function restDash(){const [d,r]=await Promise.all([api('/api/donations'),api('/api/requests')]);
 A.innerHTML=`<h2>Restaurant dashboard</h2><div class=grid2><form class=card onsubmit="addDon(event)"><h3>List surplus food</h3>
 <label>Food name</label><input name=food required><label>Quantity (servings)</label><input name=qty type=number min=1 required>
 <label>Prepared at</label><input name=prepared type=datetime-local value="${localDT(-2)}" required><label>Expires at</label><input name=expiry type=datetime-local value="${localDT(4)}" required>
 <label>Pickup location</label><input name=address value="${esc(me.address)}" required><button class=btn>Publish donation</button></form>
 <div class=card><h3>Donation requests</h3><div id=rq class=tw></div></div></div>
 <div class=card><h3>My donations</h3><div class=tw><table><tr><th>Food</th><th>Qty</th><th>Expires</th><th>Status</th></tr>${d.map(x=>`<tr><td>${esc(x.food)}</td><td>${x.qty}</td><td>${fmt(x.expiry)}</td><td>${badge(x.status)}</td></tr>`).join('')}</table></div></div>`;reqTable(r,'#rq')}
const addDon=act(async e=>{await api('/api/donations',form(e));toast('Donation published');render()});

async function ngoDash(){A.innerHTML=`<h2>NGO dashboard</h2><div class=card><div class=grid2><div><label>Search food, area or restaurant</label><input id=fq oninput="loadFood()"></div>
 <div><label>Minimum quantity</label><input id=fm type=number min=0 oninput="loadFood()"></div></div></div><div id=food class=grid></div>
 <div class=card><h3>My requests</h3><div id=myreq class=tw></div></div>`;loadFood();reqTable(await api('/api/requests'),'#myreq')}
const loadFood=act(async()=>{const d=await api(`/api/donations?q=${encodeURIComponent($('#fq').value)}&min_qty=${$('#fm').value||0}`);
 $('#food').innerHTML=d.length?d.map(x=>`<div class=card><h3>🍲 ${esc(x.food)}</h3><p class=mu>${esc(x.rname)} · ${esc(x.address)}</p><p><b>${x.qty}</b> servings · <b>${x.distance_km} km</b> away</p>
 <p class=mu>Expires ${fmt(x.expiry)}</p><button class=btn onclick="reqFood(${x.id})">Request food</button></div>`).join(''):'<p class=mu>No matching food right now.</p>'});
const reqFood=act(async i=>{await api(`/api/donations/${i}/request`,{});toast('Request sent');render()});

async function adminDash(){const [s,u,d]=await Promise.all([api('/api/stats'),api('/api/users'),api('/api/donations')]);
 A.innerHTML=`<h2>Admin dashboard</h2><div class=grid>${tiles(s)}</div><div class=card><h3>Accounts</h3><div class=tw><table><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th></th></tr>`+
 u.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.email)}</td><td>${x.role}</td><td>${badge(x.active?'active':'cancelled')}</td><td>${x.role=='admin'?'':`<button class="btn s ${x.active?'r':''}" onclick="tog(${x.id})">${x.active?'Suspend':'Activate'}</button>`}</td></tr>`).join('')+
 `</table></div></div><div class=card><h3>Latest donations</h3><div class=tw><table><tr><th>Food</th><th>Restaurant</th><th>Qty</th><th>Status</th></tr>`+
 d.slice(0,30).map(x=>`<tr><td>${esc(x.food)}</td><td>${esc(x.rname)}</td><td>${x.qty}</td><td>${badge(x.status)}</td></tr>`).join('')+'</table></div></div>'}
const tog=act(async i=>{await api(`/api/users/${i}/toggle`,{});render()});

async function mapView(){A.innerHTML=`<h2>Live map</h2><p class=mu>🟢 Restaurants · 🔵 NGOs · 🟠 Available food. Click a food marker to get a driving route.</p><div id=map></div><div id=rt class=note style="display:none;margin-top:12px"></div>`;
 const d=await api('/api/map');window.NG=d.ngos;map=L.map('map').setView([12.9716,77.5946],12);
 L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors'}).addTo(map);
 const ic=c=>L.divIcon({className:'',html:`<div style="background:${c};width:18px;height:18px;border-radius:50%;border:3px solid #fff;box-shadow:0 1px 6px #0006"></div>`,iconSize:[18,18]});
 d.restaurants.forEach(x=>L.marker([x.lat,x.lng],{icon:ic('#16a34a')}).addTo(map).bindPopup(`<b>${esc(x.name)}</b><br>Restaurant · ${esc(x.address)}`));
 d.ngos.forEach(x=>L.marker([x.lat,x.lng],{icon:ic('#2563eb')}).addTo(map).bindPopup(`<b>${esc(x.name)}</b><br>NGO · ${esc(x.address)}`));
 d.donations.forEach(x=>L.marker([x.lat+.0006,x.lng+.0006],{icon:ic('#f97316')}).addTo(map).bindPopup(`<b>${esc(x.food)}</b><br>${x.qty} servings · ${esc(x.rname)}<br>Expires ${fmt(x.expiry)}<br><button class="btn s" onclick="routeTo(${x.lat},${x.lng})">Route from ${me&&me.role=='ngo'?'my NGO':'nearest NGO'}</button>`))}
const routeTo=act(async(la,lo)=>{const n=me&&me.role=='ngo'?me:[...NG].sort((a,b)=>((a.lat-la)**2+(a.lng-lo)**2)-((b.lat-la)**2+(b.lng-lo)**2))[0];if(!n)return;
 if(routeLayer)routeLayer.remove();let pts,info='';
 try{const r=await(await fetch(`https://router.project-osrm.org/route/v1/driving/${n.lng},${n.lat};${lo},${la}?overview=full&geometries=geojson`)).json(),x=r.routes[0];
  pts=x.geometry.coordinates.map(c=>[c[1],c[0]]);info=`${(x.distance/1000).toFixed(1)} km · ~${Math.round(x.duration/60)} min drive`}
 catch{pts=[[n.lat,n.lng],[la,lo]];info='straight-line (routing service unreachable)'}
 routeLayer=L.polyline(pts,{color:'#0f3d26',weight:5}).addTo(map);map.fitBounds(routeLayer.getBounds(),{padding:[40,40]});
 const el=$('#rt');el.style.display='block';el.textContent=`Route from ${n.name}: ${info}`});

async function analytics(){const s=await api('/api/stats'),m=s.monthly;A.innerHTML=`<h2>Analytics</h2><div class=grid>${tiles(s)}</div><div class=grid2>
 <div class=card><h3>Monthly donations (servings)</h3><canvas id=c1></canvas></div><div class=card><h3>Donations by status</h3><canvas id=c2></canvas></div></div>
 <p class=mu>*Estimates: 0.4 kg per serving, 2.5 kg CO₂e per kg of food.</p>`;
 charts.push(new Chart($('#c1'),{type:'bar',data:{labels:m.map(x=>x.m),datasets:[{label:'Listed',data:m.map(x=>x.listed),backgroundColor:'#bbf7d0'},{label:'Donated',data:m.map(x=>x.donated),backgroundColor:'#16a34a'}]}}),
 new Chart($('#c2'),{type:'doughnut',data:{labels:s.status.map(x=>x.status),datasets:[{data:s.status.map(x=>x.n),backgroundColor:['#16a34a','#0f3d26','#f59e0b','#ef4444','#94a3b8','#86efac']}]}}))}

async function ai(){const m=await api('/api/ml');A.innerHTML=`<h2>AI Insights</h2><div class=note><b>⚠️ ${m.label}.</b> ${esc(m.method)}</div>`;
 if(m.insufficient){A.innerHTML+='<p class=mu>Not enough historical data yet (need 14+ days).</p>';return}
 A.innerHTML+=`<div class=grid><div class=card><div class=stat>${m.forecast.reduce((a,x)=>a+x.qty,0)}<small>Predicted surplus servings, next 7 days</small></div></div>
 <div class=card><div class=stat>${m.demand_per_day}<small>Avg servings collected / day (30d demand)</small></div></div>
 <div class=card><div class=stat>${m.sell_through}%<small>Listed food collected (30d)</small></div></div></div>
 <div class=card><h3>Surplus forecast</h3><canvas id=c1 height=110></canvas></div><div class=card id=rec><h3>Recommend NGOs for a donation</h3></div>`;
 const h=m.history,f=m.forecast,nl=Array(h.length).fill(null);
 charts.push(new Chart($('#c1'),{type:'line',data:{labels:[...h,...f].map(x=>x.date.slice(5)),datasets:[{label:'Actual',data:[...h.map(x=>x.qty),...Array(f.length).fill(null)],borderColor:'#16a34a',tension:.3},
  {label:'Predicted (demo)',data:[...nl,...f.map(x=>x.qty)],borderColor:'#f59e0b',borderDash:[6,4],tension:.3}]}}));
 if(me&&['restaurant','admin'].includes(me.role)){const d=(await api('/api/donations')).filter(x=>x.status=='available');
  $('#rec').innerHTML+=d.length?`<select id=rs onchange="recNgo()"><option value="">Select an available donation…</option>${d.map(x=>`<option value=${x.id}>${esc(x.food)} – ${x.qty} servings (${esc(x.rname)})</option>`).join('')}</select><div id=ro></div>`:'<p class=mu>No available donations to match.</p>'}
 else $('#rec').innerHTML+='<p class=mu>Login as a restaurant or admin to get NGO recommendations.</p>'}
const recNgo=act(async()=>{const i=$('#rs').value;if(!i)return;const r=await api('/api/recommend/'+i);
 $('#ro').innerHTML=`<p class=mu>${esc(r.label)}: ${esc(r.method)}</p><table><tr><th>NGO</th><th>Distance</th><th>Open requests</th><th>Score</th></tr>${r.ngos.map(n=>`<tr><td>${esc(n.name)}</td><td>${n.distance_km} km</td><td>${n.open_requests}</td><td>${badge(n.score+'/100')}</td></tr>`).join('')}</table>`});

window.addEventListener('hashchange',render);
(async()=>{try{me=(await api('/api/me')).user}catch{}render()})();
