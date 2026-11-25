import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, NavLink, useNavigate, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Activity, AlertTriangle, Building2, CalendarDays, ChevronRight, CircleGauge, Download, Eye, EyeOff,
  FileBarChart, LayoutDashboard, Network, Search, Settings as SettingsIcon, ShieldCheck, Users, Zap, Bus, FlaskConical,
  LogOut, Menu, X, RotateCcw, CheckCircle2, WifiOff, Cpu, GraduationCap } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, ComposedChart, Line, XAxis, YAxis, Tooltip, PieChart, Pie, Cell } from "recharts";
import "./styles.css";
import "./campus-visuals.css";

const API = import.meta.env.VITE_API_URL || "";
async function request(path,options={}){
  const token=localStorage.getItem("omnisx_token");
  const headers={...(options.body?{"Content-Type":"application/json"}:{}),...(token?{Authorization:`Bearer ${token}`}:{})};
  const response=await fetch(API+path,{...options,headers:{...headers,...options.headers}});
  const data=await response.json().catch(()=>({detail:"Unexpected response from OMNIS-X"}));
  if(!response.ok)throw new Error(data.detail||`Request failed (${response.status})`);
  return data;
}
const get=path=>request(path);
const post=(path,body)=>request(path,{method:"POST",body:JSON.stringify(body)});
function saveLogin(data){localStorage.setItem("omnisx_token",data.token);localStorage.setItem("omnisx_user",JSON.stringify(data.user))}
function storedUser(){try{return JSON.parse(localStorage.getItem("omnisx_user")||"null")}catch{return null}}
function ApiError({message,onRetry}){return <div className="api-error"><AlertTriangle size={18}/><span>{message}</span>{onRetry&&<button className="secondary-btn" onClick={onRetry}>Retry</button>}</div>}
function Status({value}){const normalized=(value||"unknown").toLowerCase().replaceAll("_"," ");const tone=["operational","restored"].includes(normalized)?"green":["failed","degraded","under maintenance"].includes(normalized)?"red":"orange";return <span className={`status-badge ${tone}`}>{normalized}</span>}

function Login(){
  const nav=useNavigate(),[email,setEmail]=useState(""),[password,setPassword]=useState(""),[show,setShow]=useState(false),[error,setError]=useState("");
  const submit=async(e)=>{e?.preventDefault();try{saveLogin(await post("/api/auth/login",{email,password}));nav("/dashboard")}catch(err){setError(err.message)}};
  const demo=async()=>{setEmail("admin@omnisx.com");setPassword("Omnis@123");try{saveLogin(await post("/api/auth/login",{email:"admin@omnisx.com",password:"Omnis@123"}));nav("/dashboard")}catch(err){setError(err.message)}};
  return <main className="login-shell">
    <section className="campus-panel"><img className="campus-photo" src="/college-campus.jpeg" alt="Aerial view of the college campus"/>
      <div className="campus-copy"><div className="brand-mark"><span>OX</span></div><h1>OMNIS-X</h1><p className="tagline">One Campus. One Intelligence. Zero Blind Spots.</p><p>Constraint-aware institutional intelligence for a resilient engineering campus.</p></div></section>
    <section className="login-panel"><motion.div initial={{opacity:0,y:18}} animate={{opacity:1,y:0}} className="login-card">
      <div className="login-logo"><span>OX</span></div><h2>Welcome back</h2><p>Sign in to the Institutional Command Centre</p>
      <form onSubmit={submit}>
        <label>Email address<input type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="admin@omnisx.com" required /></label>
        <label>Password<div className="password-wrap"><input type={show?"text":"password"} value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter your password" required /><button type="button" onClick={()=>setShow(!show)}>{show?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></label>
        <div className="form-row"><label className="check"><input type="checkbox"/> <span>Remember me</span></label><button type="button" className="link" onClick={()=>setError("Contact your system administrator to reset your password.")}>Forgot password?</button></div>
        {error&&<div className="error-banner">{error}</div>}<button className="primary-btn" type="submit">Sign in <ChevronRight size={17}/></button>
      </form><div className="divider"><span>or use hackathon demo</span></div><button className="demo-btn" onClick={demo}>Enter Demo Workspace</button>
      <small><strong>Demo:</strong> admin@omnisx.com / Omnis@123</small>
    </motion.div></section>
  </main>
}

const navItems=[
  {path:"/dashboard",label:"Command Centre",icon:LayoutDashboard},
  {path:"/twin",label:"Digital Twin",icon:Building2},
  {path:"/dependency",label:"Dependency Network",icon:Network},
  {path:"/conflicts",label:"Conflict Detection",icon:AlertTriangle},
  {path:"/assignments",label:"Scheduling & Transport",icon:GraduationCap},
  {path:"/simulation",label:"Failure Simulation",icon:Zap},
  {path:"/impact",label:"Impact Analysis",icon:Activity},
  {path:"/recovery",label:"Recovery Centre",icon:ShieldCheck},
  {path:"/optimization",label:"Resource Optimization",icon:CircleGauge},
  {path:"/risk",label:"Risk Analytics",icon:FileBarChart},
  {path:"/incidents",label:"Incident History",icon:CalendarDays},
  {path:"/settings",label:"Administration",icon:SettingsIcon},
];

function Shell(){
  const [open,setOpen]=useState(false),nav=useNavigate(),location=useLocation();
  useEffect(()=>{if(!localStorage.getItem("omnisx_token"))nav("/")},[nav]);
  const visibleNavItems=navItems.filter(item=>item.path!=="/assignments"||storedUser()?.role==="administrator");
  const active=visibleNavItems.find(n=>n.path===location.pathname)?.label||"OMNIS-X";
  return <div className="app-shell"><aside className={open?"sidebar open":"sidebar"}>
    <div className="side-brand"><div className="brand-mark small"><span>OX</span></div><div><strong>OMNIS-X</strong><small>Digital Twin</small></div><button className="close-side" onClick={()=>setOpen(false)}><X/></button></div>
    <nav>{visibleNavItems.map(item=>{const Icon=item.icon;return <NavLink key={item.path} to={item.path} onClick={()=>setOpen(false)}><Icon size={18}/><span>{item.label}</span></NavLink>})}</nav>
    <button className="logout" onClick={()=>{localStorage.removeItem("omnisx_user");localStorage.removeItem("omnisx_token");nav("/")}}><LogOut size={18}/>Sign out</button>
  </aside><div className="main-area"><header className="topbar"><button className="menu-btn" onClick={()=>setOpen(true)}><Menu/></button><div><span className="eyebrow">Institutional Command Centre</span><h1>{active}</h1></div><div className="top-actions"><div className="live"><i></i> Live</div><div className="avatar">CA</div></div></header><main className="page">{location.pathname!=="/dashboard"&&<div className="breadcrumb">OMNIS-X <ChevronRight size={14}/> {active}</div>}<Routes>
    <Route path="/dashboard" element={<Dashboard/>}/><Route path="/twin" element={<Twin/>}/><Route path="/dependency" element={<Dependency/>}/><Route path="/conflicts" element={<Conflicts/>}/><Route path="/assignments" element={<Assignments/>}/><Route path="/simulation" element={<Simulation/>}/><Route path="/impact" element={<Impact/>}/><Route path="/recovery" element={<Recovery/>}/><Route path="/optimization" element={<Optimization/>}/><Route path="/risk" element={<Risk/>}/><Route path="/incidents" element={<Incidents/>}/><Route path="/settings" element={<Settings/>}/>
  </Routes></main></div></div>
}

function PageTitle({title,subtitle,action}){return <div className="page-title"><div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div>{action}</div>}
function Stat({label,value,icon:Icon,tone="blue",note}){return <motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} className="stat-card"><div className={`stat-icon ${tone}`}><Icon size={20}/></div><div><span>{label}</span><strong>{value}</strong>{note&&<small>{note}</small>}</div></motion.div>}

function Dashboard(){
  const [data,setData]=useState(null),[error,setError]=useState("");
  const load=()=>get("/api/dashboard").then(setData).catch(e=>setError(e.message));
  useEffect(()=>{load()},[]);
  if(error)return <ApiError message={error} onRetry={load}/>;
  if(!data)return <Loading/>;
  const s=data.stats;
  const health=data.department_status;
  const friendlyActivityTitle=title=>{
    const resourceNames={"SVC-LAB-AIML":"AIML Practical Labs","PWR-GRID-A":"Grid feeder A","ISP-PRIMARY":"Primary ISP fibre","WATER-MUNI":"Municipal water inlet"};
    return String(title||"").replace(/^Simulated campus failure:\s*/i,"Failure simulation at ")
      .replace(/\b(SVC-LAB-AIML|PWR-GRID-A|ISP-PRIMARY|WATER-MUNI)\b/g,resource=>resourceNames[resource]);
  };
  return <>
    <div className="welcome-row"><div><h2>Good morning, Campus Administrator</h2><p>Wednesday, 25 November · Institutional systems are being monitored.</p></div><div className="health-pill"><ShieldCheck size={18}/><div><span>Operational Health</span><strong>{s.health}%</strong></div></div></div>
    <div className="stats-grid">
      <Stat label="Departments" value={s.departments} icon={Building2} note="All departments visible"/>
      <Stat label="Students" value={s.students} icon={GraduationCap} tone="green" note="Active enrolments"/>
      <Stat label="Faculty" value={s.faculty} icon={Users} tone="violet" note="Teaching & research"/>
      <Stat label="Classrooms" value={s.rooms-s.laboratories} icon={Building2} tone="orange" note={`${s.laboratories} laboratories`}/>
      <Stat label="Active Incidents" value={s.active_incidents} icon={AlertTriangle} tone="red" note="Needs attention"/>
      <Stat label="Critical Alerts" value={s.critical_alerts} icon={Zap} tone="orange" note="Monitored resources"/>
    </div>
    <div className="dashboard-grid">
      <section className="panel chart-panel"><div className="panel-head"><div><h3>Department health</h3><p>Free weekly room capacity after scheduled bookings</p></div><span className="status-badge green">{s.health}% campus-wide</span></div><div className="chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={health}><XAxis dataKey="name" axisLine={false} tickLine={false}/><YAxis yAxisId="capacity" domain={["dataMin - 2","dataMax + 2"]} tickFormatter={value=>`${value}%`} axisLine={false} tickLine={false}/><YAxis yAxisId="hours" orientation="right" domain={[0,"dataMax + 2"]} tickFormatter={value=>`${value}h`} axisLine={false} tickLine={false}/><Tooltip formatter={(value,name)=>[name==="Scheduled room hours"?`${value} hrs`:`${value}%`,name]}/><Line yAxisId="capacity" type="monotone" dataKey="capacity_percent" name="Free room capacity" stroke="#315efb" strokeWidth={3} dot={{r:4}} activeDot={{r:6}}/><Line yAxisId="hours" type="monotone" dataKey="scheduled_hours" name="Scheduled room hours" stroke="#38a467" strokeWidth={2} dot={{r:4}}/></ComposedChart></ResponsiveContainer></div><div className="department-chart-legend"><span><i className="capacity-legend"/>Free weekly room capacity</span><span><i className="schedule-legend"/>Scheduled room hours</span></div></section>
      <section className="panel"><div className="panel-head"><div><h3>Department status</h3><p>Available rooms and active enrolments</p></div></div><div className="department-list">{data.department_status.map(d=><div className="department-row" key={d.name}><div><strong>{d.name}</strong><span>{d.available_rooms!=null?`${d.available_rooms}/${d.total_rooms} rooms · `:""}{d.scheduled_hours!=null?`${d.scheduled_hours} booked hrs · `:""}{d.students} students</span></div><div className="progress"><i style={{width:`${d.value}%`}}/></div><b>{d.value}%</b></div>)}</div></section>
      <section className="panel"><div className="panel-head"><div><h3>Resource availability</h3><p>Room availability, recorded backup coverage, and transport spare seats</p></div></div><div className="chart small"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.resource_status} layout="vertical"><XAxis type="number" domain={[0,100]} hide/><YAxis type="category" dataKey="name" width={136} axisLine={false} tickLine={false}/><Tooltip formatter={(value,name)=>[`${value}%`,name]}/><Bar dataKey="value" radius={[0,6,6,0]} barSize={12}>{data.resource_status.map(item=><Cell key={item.name} fill={item.value<40?"#df6b64":item.value<75?"#df9a3a":"#38a467"}/>)}</Bar></BarChart></ResponsiveContainer></div></section>
      <section className="panel"><div className="panel-head"><div><h3>Recent campus activity</h3><p>Updates from simulations and incident tracking</p></div></div><div className="timeline">{data.activity.map((a,i)=><div key={`${a.time}-${a.title}-${i}`}><time>{a.time}</time><i className={a.kind}/><p><strong>{friendlyActivityTitle(a.title)}</strong><span className={`activity-status ${a.kind}`}>{a.status||(a.kind==="success"?"Resolved":"Needs attention")}</span></p></div>)}</div></section>
    </div>
  </>
}

function Loading(){return <div className="loading-grid">{[1,2,3,4].map(i=> <div className="skeleton" key={i}/>)}</div>}

function Twin(){
 const [data,setData]=useState(null),[selectedSite,setSelectedSite]=useState(""),[error,setError]=useState("");
 const load=async()=>{setError("");try{setData(await get("/api/twin"))}catch(e){setError(e.message)}};
 useEffect(()=>{load()},[]);
 if(error)return <><PageTitle title="Institutional Digital Twin" subtitle="Illustrated campus map with live department and facility data."/><ApiError message={error} onRetry={load}/></>;
 if(!data)return <Loading/>;
 const facilities=data.facilities||{};
 const departmentStats=data.departments.map(department=>{
  const departmentRooms=data.rooms.filter(room=>room.department===department.id);
  const totalRooms=department.total_rooms??departmentRooms.length;
  const availableRooms=department.available_rooms??departmentRooms.filter(room=>["operational","restored"].includes(String(room.status).toLowerCase())).length;
  return {...department,total_rooms:totalRooms,available_rooms:availableRooms,health:department.health??(totalRooms?Math.round(100*availableRooms/totalRooms):null)};
 });
 const sites=[
  ...departmentStats.map(d=>({id:`department-${d.id}`,code:d.id,title:d.name||d.id,kind:"academic",icon:Building2,detail:`${d.health==null?"Room status unavailable":`${d.health}% room availability`} · ${d.students} students · ${d.faculty} faculty`})),
  {id:"transport",code:"TRANSPORT",title:"Transport",kind:"service",icon:Bus,detail:Number.isFinite(facilities.transport_routes)?`${facilities.transport_routes} campus routes`:"Campus transport services"},
  {id:"hostel",code:"HOSTEL",title:"Hostels",kind:"service",icon:Users,detail:Number.isFinite(facilities.hostels)?`${facilities.hostels} residences · ${facilities.hostel_beds} beds`:"Student accommodation"},
  {id:"admin",code:"ADMIN",title:"Administration",kind:"service",icon:SettingsIcon,detail:"Administration office and campus services"},
  {id:"examination",code:"EXAM",title:"Examination Centre",kind:"service",icon:CalendarDays,detail:Number.isFinite(facilities.examination_halls)?`${facilities.examination_halls} examination halls`:"Examination facilities"},
 ];
  const mapHotspots=[
   ...(departmentStats.length?[{siteId:`department-${departmentStats[0].id}`,label:"Departments",left:"20.5%",top:"49%",width:"16%",height:"18%"}]:[]),
   {siteId:"hostel",label:"Hostel",left:"29%",top:"20%",width:"14%",height:"17%"},
   {siteId:"hostel",label:"Hostel",left:"67%",top:"20%",width:"14%",height:"17%"},
   {siteId:"admin",label:"Administration",left:"47%",top:"49%",width:"17%",height:"18%"},
   {siteId:"examination",label:"Examination Centre",left:"71.5%",top:"49%",width:"18%",height:"18%"},
   {siteId:"transport",label:"Transportation",left:"63.5%",top:"73%",width:"18%",height:"18%"},
  ];
 const selected=sites.find(site=>site.id===selectedSite)||sites[0];
  return <><PageTitle title="Institutional Digital Twin" subtitle="Illustrated campus map with live department and facility data; layout is not to scale."/>
  <section className="panel campus-map-panel"><div className="panel-head"><div><h3>Campus map</h3><p>Select a map location or department to view its details.</p></div><span className="count">{sites.length} locations</span></div><div className="campus-map" role="group" aria-label="Campus map with selectable locations">
  <div className="campus-map-image-wrap"><img className="campus-map-image" src="/digital-twin-campus-map.jpeg" alt="Illustrated campus map showing hostels, departments, administration, examination centre, transportation, roads, and the main gate"/>{mapHotspots.map((hotspot,index)=><button key={`${hotspot.siteId}-${index}`} type="button" className={`campus-map-hotspot ${selected.id===hotspot.siteId?"selected":""}`} style={{left:hotspot.left,top:hotspot.top,width:hotspot.width,height:hotspot.height}} aria-label={`Select ${hotspot.label}`} aria-pressed={selected.id===hotspot.siteId} title={hotspot.label} onClick={()=>setSelectedSite(hotspot.siteId)}><span>{hotspot.label}</span></button>)}</div>
  <div className="campus-map-departments" aria-label="Select a department"><strong>Departments</strong>{departmentStats.map(department=><button key={department.id} type="button" className={selected.id===`department-${department.id}`?"selected":""} aria-pressed={selected.id===`department-${department.id}`} onClick={()=>setSelectedSite(`department-${department.id}`)}>{department.name||department.id}</button>)}</div>
  </div>{!data.facilities&&<p className="campus-data-note">Facility counts are not available from the current backend response.</p>}<div className="selected-campus-site"><div><strong>{selected.title}</strong><span>{selected.detail}</span></div><span className="map-selection-hint">Selected location</span></div></section>
 <div className="section-grid"><section className="panel"><div className="panel-head"><h3>Departments</h3><span className="count">{departmentStats.length}</span></div><div className="resource-list">{departmentStats.map(d=><div key={d.id}><div className="resource-icon"><Building2 size={18}/></div><div><strong>{d.name||d.id}</strong><span>{d.total_rooms?`${d.available_rooms}/${d.total_rooms} rooms operational · `:""}{d.students} students · {d.faculty} faculty</span></div><b className={d.health===100?"green-text":"health-warning"}>{d.health==null?"—":`${d.health}%`}</b></div>)}</div></section>
 <section className="panel"><div className="panel-head"><h3>Rooms & laboratories</h3><span className="count">{data.rooms.length}</span></div><div className="resource-list">{data.rooms.slice(0,8).map(r=><div key={r.id}><div className="resource-icon"><FlaskConical size={18}/></div><div><strong>{r.name}</strong><span>{r.kind} · Capacity {r.capacity}</span></div><Status value={r.status}/></div>)}</div></section></div></>
}

function Dependency(){
 const [data,setData]=useState(null),[error,setError]=useState("");
 const load=async()=>{setError("");try{setData(await get("/api/dependency"))}catch(e){setError(e.message)}};
 useEffect(()=>{load()},[]);
 if(error)return <><PageTitle title="Dependency Network" subtitle="Provider-to-dependent relationships across institutional systems."/><ApiError message={error} onRetry={load}/></>;
 if(!data)return <Loading/>;
 const layers=[...new Set(data.nodes.map(node=>node.layer))].sort((a,b)=>a-b);
 const grouped=layers.map(layer=>data.nodes.filter(node=>node.layer===layer).sort((a,b)=>a.name.localeCompare(b.name)));
 const width=1120,nodeWidth=176,nodeHeight=54,height=Math.max(580,Math.max(...grouped.map(group=>group.length),0)*62+130);
 const xStep=(width-180)/Math.max(layers.length-1,1),positions={};
 grouped.forEach((group,layerIndex)=>group.forEach((node,nodeIndex)=>{positions[node.id]={x:90+layerIndex*xStep,y:70+(height-100)*(nodeIndex+1)/(group.length+1)}}));
 const singlePoints=new Set(data.single_points_of_failure);
 const criticalNodes=data.nodes.filter(node=>node.criticality_label==="critical").length;
 const coveredEdges=data.edges.filter(edge=>edge.mitigation_resource_id).length;
 return <><PageTitle title="Dependency Network" subtitle="Live provider-to-dependent links across campus systems and services."/><div className="dependency-layout"><section className="network-panel"><div className="network-panel-heading"><strong>Campus service flow</strong><span>{data.nodes.length} nodes · {data.edges.length} connections</span></div><div className="dependency-viewport"><svg className="dependency-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Live campus dependency network">
 <defs><marker id="dependency-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#9aabc5"/></marker></defs>
 {layers.map((layer,index)=><text key={layer} className="dependency-layer-label" x={90+index*xStep} y="28" textAnchor="middle">LAYER {index+1}</text>)}
 {data.edges.map(edge=>{const source=positions[edge.source],target=positions[edge.target];if(!source||!target)return null;const startX=source.x+nodeWidth/2,endX=target.x-nodeWidth/2,controlX=(startX+endX)/2;return <path key={edge.id} className={`dependency-edge ${edge.kind}`} d={`M ${startX} ${source.y} C ${controlX} ${source.y}, ${controlX} ${target.y}, ${endX} ${target.y}`} markerEnd="url(#dependency-arrow)"><title>{edge.kind} dependency</title></path>})}
 {data.nodes.map(node=>{const point=positions[node.id];const isSinglePoint=singlePoints.has(node.id);return <g key={node.id} className={`dependency-node ${isSinglePoint?"single-point":""} ${node.status!=="operational"?"degraded":""}`} transform={`translate(${point.x-nodeWidth/2},${point.y-nodeHeight/2})`}><title>{node.name} · {node.status}{isSinglePoint?" · single point of failure":""}</title><rect width={nodeWidth} height={nodeHeight} rx="9"/><text className="dependency-node-name" x="12" y="22">{node.name.length>22?`${node.name.slice(0,21)}…`:node.name}</text><text className="dependency-node-meta" x="12" y="40">{node.type} · {node.status.replaceAll("_"," ")}</text></g>})}
 </svg></div><div className="network-legend"><span><i className="legend-line hard"/>Required dependency</span><span><i className="legend-line soft"/>Optional dependency</span><span><i className="legend-node-risk"/>Single point of failure</span></div></section>
 <section className="panel details-panel"><div className="panel-head"><h3>Network insights</h3></div><div className="insight"><span>Critical nodes</span><strong>{criticalNodes}</strong></div><div className="insight"><span>Required dependencies</span><strong>{data.edges.filter(edge=>edge.kind==="hard").length}</strong></div><div className="insight"><span>Backed-up links</span><strong>{coveredEdges}</strong></div><div className="insight"><span>Single points of failure</span><strong>{singlePoints.size}</strong></div></section></div></>
}

function Conflicts(){
 const [data,setData]=useState(null),[campus,setCampus]=useState(null),[query,setQuery]=useState(""),[severity,setSeverity]=useState("All"),[type,setType]=useState("All"),[loading,setLoading]=useState(false),[error,setError]=useState(""),[campusError,setCampusError]=useState(""),[bookingError,setBookingError]=useState(""),[bookingResult,setBookingResult]=useState(null),[checking,setChecking]=useState(false),[applying,setApplying]=useState(""),[actionMessage,setActionMessage]=useState("");
 const [booking,setBooking]=useState(()=>{const now=new Date();return {name:"Department event",event_date:new Date(now.getTime()-now.getTimezoneOffset()*60000).toISOString().slice(0,10),start_time:"10:00",duration_hours:1,venue_id:"",organizing_department_id:""}});
 const load=async()=>{setLoading(true);setError("");try{setData(await get("/api/conflicts"))}catch(e){setError(e.message)}finally{setLoading(false)}};
 useEffect(()=>{load();get("/api/twin").then(d=>{setCampus(d);setBooking(current=>({...current,venue_id:current.venue_id||(d.rooms.find(room=>["operational","restored"].includes(String(room.status).toLowerCase()))||d.rooms[0])?.id||"",organizing_department_id:current.organizing_department_id||d.departments[0]?.id||""}))}).catch(e=>setCampusError(e.message))},[]);
 const checkBooking=async event=>{event.preventDefault();setChecking(true);setBookingError("");setBookingResult(null);try{setBookingResult(await post("/api/events/check",{...booking,duration_hours:Number(booking.duration_hours),organizing_department_id:booking.organizing_department_id||null}))}catch(e){setBookingError(e.message)}finally{setChecking(false)}};
 const applyFix=async conflict=>{setApplying(conflict.id);setActionMessage("");setError("");try{await post(`/api/conflicts/${encodeURIComponent(conflict.id)}/auto-fix`,{});setActionMessage(`Applied the validated fix for ${conflict.title}.`);await load()}catch(e){setError(e.message)}finally{setApplying("")}};
 const updateBooking=(key,value)=>setBooking(current=>({...current,[key]:value}));
 if(error&&!data)return <><PageTitle title="Conflict Detection Centre" subtitle="Timetable constraints and critical-resource resilience checks."/><ApiError message={error} onRetry={load}/></>;
 if(!data)return <Loading/>;
 const normalize=value=>String(value??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
 const terms=normalize(query).trim().split(/\s+/).filter(Boolean);
 const categories=[...new Set(data.conflicts.map(conflict=>conflict.type))];
 const categoryLabel=value=>({
  faculty_expertise:"Faculty expertise",
  invigilator_overlap:"Invigilator overlap",
  resource_backup_gap:"Critical-resource backup gaps",
 }[value]||value.replaceAll("_"," "));
 const filtered=data.conflicts.filter(conflict=>{
  const fields=[conflict.id,conflict.type,conflict.severity,conflict.title,conflict.description,conflict.suggestion,conflict.status,...(Array.isArray(conflict.affected_entities)?conflict.affected_entities:[])];
  const searchable=normalize(fields.join(" "));
  return terms.every(term=>searchable.includes(term))&&(severity==="All"||conflict.severity===severity)&&(type==="All"||conflict.type===type);
 });
 return <><PageTitle title="Conflict Detection Centre" subtitle={`${data.count} findings from timetable checks and resource resilience · showing ${filtered.length}.`}/>
 {error&&<ApiError message={error}/>}
 <section className="panel">
  <div className="panel-head"><div><h3>Check an event before booking</h3><p>Check the venue and time against events, examinations, and scheduled classes.</p></div></div>
  {campusError?<ApiError message={campusError}/>:!campus?<Loading/>:
   <form className="form-grid" onSubmit={checkBooking}>
    <label>Event name<input value={booking.name} onChange={e=>updateBooking("name",e.target.value)} required maxLength={160}/></label>
    <label>Organizing department<select value={booking.organizing_department_id} onChange={e=>updateBooking("organizing_department_id",e.target.value)}><option value="">Not specified</option>{campus.departments.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <label>Date<input type="date" value={booking.event_date} onChange={e=>updateBooking("event_date",e.target.value)} required/></label>
    <label>Start time<input type="time" value={booking.start_time} onChange={e=>updateBooking("start_time",e.target.value)} required/></label>
    <label>Duration (hours)<input type="number" min="0.25" max="24" step="0.25" value={booking.duration_hours} onChange={e=>updateBooking("duration_hours",e.target.value)} required/></label>
    <label>Venue<select value={booking.venue_id} onChange={e=>updateBooking("venue_id",e.target.value)} required><option value="">Select a venue</option>{campus.rooms.map(room=><option key={room.id} value={room.id}>{room.id} · {room.kind} · {room.status}</option>)}</select></label>
    <div className="form-actions"><button className="primary-btn" type="submit" disabled={checking||!booking.venue_id}>{checking?"Checking…":"Check availability"}<ChevronRight size={17}/></button></div>
   </form>}
  {bookingError&&<ApiError message={bookingError}></ApiError>}
  {bookingResult&&<div className="event-check-result"><strong className={bookingResult.can_schedule?"green-text":"health-warning"}>{bookingResult.can_schedule?"No booking conflicts found":"Review these conflicts before booking"}</strong>{bookingResult.conflicts.map(item=><p key={item.id}><b>{item.title}:</b> {item.description} {item.suggestion}</p>)}</div>}
 </section>
 {actionMessage&&<p className="method-copy">{actionMessage}</p>}
 <div className="filter-row"><div className="search-box"><Search size={17}/><input aria-label="Search conflicts" type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search by issue, room, exam, faculty, or resource"/></div><select aria-label="Filter by severity" value={severity} onChange={e=>setSeverity(e.target.value)}><option value="All">All severities</option><option value="CRITICAL">Critical</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></select><button className="secondary-btn" onClick={load} disabled={loading}><RotateCcw size={16}/>{loading?"Detecting…":"Re-run detection"}</button></div>
 <div className="conflict-categories" aria-label="Filter by conflict category"><button type="button" className={type==="All"?"active":""} aria-pressed={type==="All"} onClick={()=>setType("All")}>All types <b>{data.count}</b></button>{categories.map(category=><button type="button" key={category} className={type===category?"active":""} aria-pressed={type===category} onClick={()=>setType(category)}>{categoryLabel(category)} <b>{data.conflicts.filter(conflict=>conflict.type===category).length}</b></button>)}</div>
 <div className="table-panel"><table><thead><tr><th>Conflict</th><th>Severity</th><th>Impact</th><th>Recommendation</th><th>Status</th></tr></thead><tbody>{filtered.map(c=><tr key={c.id}><td><strong>{c.title}</strong><small>{c.id}</small></td><td><span className={`severity ${c.severity.toLowerCase()}`}>{c.severity}</span></td><td>{c.description}</td><td>{c.suggestion}{c.auto_fix&&<div><button className="secondary-btn" onClick={()=>applyFix(c)} disabled={!!applying}>{applying===c.id?"Applying…":"Apply validated fix"}</button></div>}</td><td><span className="status-badge orange">{c.status}</span></td></tr>)}</tbody></table>{!filtered.length&&<div className="empty-table"><p>No findings match this search and filter.</p><button className="secondary-btn" onClick={()=>{setQuery("");setSeverity("All");setType("All")}}>Clear filters</button></div>}</div></>
}

function Assignments(){
 const [data,setData]=useState(null),[sessionId,setSessionId]=useState(""),[options,setOptions]=useState(null),[roomId,setRoomId]=useState(""),[facultyId,setFacultyId]=useState(""),[sourceRouteId,setSourceRouteId]=useState(""),[targetRouteId,setTargetRouteId]=useState(""),[riderCount,setRiderCount]=useState(1),[loading,setLoading]=useState(false),[saving,setSaving]=useState(false),[error,setError]=useState(""),[success,setSuccess]=useState("");
 const load=async()=>{setLoading(true);setError("");try{const result=await get("/api/assignments");setData(result);setSessionId(current=>current||result.sessions[0]?.id||"");setSourceRouteId(current=>current||result.routes[0]?.id||"");setTargetRouteId(current=>current||result.routes.find(route=>route.id!==result.routes[0]?.id)?.id||"")}catch(e){setError(e.message)}finally{setLoading(false)}};
 useEffect(()=>{load()},[]);
 useEffect(()=>{if(!sessionId)return;setOptions(null);setRoomId("");setFacultyId("");get(`/api/assignments/sessions/${encodeURIComponent(sessionId)}/options`).then(setOptions).catch(e=>setError(e.message))},[sessionId]);
 const session=data?.sessions.find(item=>item.id===sessionId);
 const sourceRoute=data?.routes.find(item=>item.id===sourceRouteId);
 const weekdayOrder=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
 const sessionOptions=[...(data?.sessions||[])].sort((left,right)=>{
  const leftDay=weekdayOrder.indexOf(left.weekday.slice(0,3));
  const rightDay=weekdayOrder.indexOf(right.weekday.slice(0,3));
  return (leftDay<0?7:leftDay)-(rightDay<0?7:rightDay)
   ||left.start_time.localeCompare(right.start_time)
   ||left.id.localeCompare(right.id);
 });
 const targetOptions=(data?.routes||[]).filter(route=>route.id!==sourceRouteId&&route.spare_seats>=Number(riderCount));
 const assignSession=async event=>{
  event.preventDefault();
  if(!roomId&&!facultyId)return;
  setSaving(true);setError("");setSuccess("");
  const payload={};if(roomId)payload.room_id=roomId;if(facultyId)payload.faculty_id=facultyId;
  try{
   await post(`/api/assignments/sessions/${encodeURIComponent(sessionId)}`,payload);
   setSuccess(`Assignments saved for ${sessionId}.`);setRoomId("");setFacultyId("");
   await load();setOptions(await get(`/api/assignments/sessions/${encodeURIComponent(sessionId)}/options`));
  }catch(e){setError(e.message)}finally{setSaving(false)}
 };
 const transferRiders=async event=>{event.preventDefault();setSaving(true);setError("");setSuccess("");try{const result=await post(`/api/transport-routes/${encodeURIComponent(sourceRouteId)}/transfer`,{target_route_id:targetRouteId,rider_count:Number(riderCount)});setSuccess(`${result.transferred_riders} riders moved to ${targetRouteId}.`);await load()}catch(e){setError(e.message)}finally{setSaving(false)}};
 if(!storedUser()||storedUser().role!=="administrator")return <><PageTitle title="Scheduling & Transport" subtitle="Administrator-only assignment controls."/><ApiError message="Administrator role required."/></>;
 if(error&&!data)return <><PageTitle title="Scheduling & Transport" subtitle="Assign available rooms, qualified faculty, and transport capacity."/><ApiError message={error} onRetry={load}/></>;
 if(!data)return <Loading/>;
 return <><PageTitle title="Scheduling & Transport" subtitle="Assign classes and labs to free compatible rooms, qualified faculty, and routes with verified spare seats."/>
 {error&&<ApiError message={error}></ApiError>}{success&&<p className="method-copy">{success}</p>}
 <section className="panel"><div className="panel-head"><div><h3>Classroom, lab & faculty assignments</h3><p>Available choices are checked against capacity, room type, equipment, timetable clashes, and faculty qualifications.</p></div><button className="secondary-btn" onClick={load} disabled={loading}><RotateCcw size={16}/>{loading?"Refreshing…":"Refresh availability"}</button></div>
 {data.sessions.length?<form className="form-grid" onSubmit={assignSession}>
  <label>Scheduled class or lab<select value={sessionId} onChange={event=>setSessionId(event.target.value)}>{sessionOptions.map(item=><option key={item.id} value={item.id}>{item.id} · {item.course_code} · {item.weekday} {item.start_time}</option>)}</select></label>
  {session&&<p className="method-copy">Current: {session.session_type} · {session.expected_students} students · room {session.room_id} · faculty {session.faculty_id}</p>}
  <label>Available room<select value={roomId} onChange={event=>setRoomId(event.target.value)}><option value="">Keep current room</option>{options?.rooms.map(room=><option key={room.id} value={room.id}>{room.id} · {room.capacity} seats · {room.building}</option>)}</select></label>
  <label>Available qualified faculty<select value={facultyId} onChange={event=>setFacultyId(event.target.value)}><option value="">Keep current faculty</option>{options?.faculty.map(person=><option key={person.id} value={person.id}>{person.id} · {person.department_id} · {person.weekly_hours} booked hours</option>)}</select></label>
  {options&&options.rooms.length===0&&<p className="method-copy">No compatible free room is available for this time.</p>}
  {options&&options.faculty.length===0&&<p className="method-copy">No available qualified faculty member is free for this time.</p>}
  <div className="form-actions"><button className="primary-btn" type="submit" disabled={saving||(!roomId&&!facultyId)||!options}>{saving?"Saving…":"Save class assignment"}<ChevronRight size={17}/></button></div>
 </form>:<p className="method-copy">No scheduled classes or labs are available to assign.</p>}</section>
 <section className="panel"><div className="panel-head"><div><h3>Transport route capacity</h3><p>Transfer a rider count to another route only when that route has enough recorded spare seats.</p></div></div>
 {data.routes.length>1?<form className="form-grid" onSubmit={transferRiders}>
  <label>Move riders from<select value={sourceRouteId} onChange={event=>setSourceRouteId(event.target.value)}>{data.routes.map(route=><option key={route.id} value={route.id}>{route.route_name} · {route.bus_id} · {route.assigned_students}/{route.daily_capacity} seats</option>)}</select></label>
  <label>Move riders (count)<input type="number" min="1" max={sourceRoute?.assigned_students||1} value={riderCount} onChange={event=>setRiderCount(Math.max(1,Number(event.target.value)||1))} required/></label>
  <label>Move to route<select value={targetRouteId} onChange={event=>setTargetRouteId(event.target.value)} required><option value="">Select a route with sufficient space</option>{targetOptions.map(route=><option key={route.id} value={route.id}>{route.route_name} · {route.bus_id} · {route.spare_seats} spare seats</option>)}</select></label>
  {!targetOptions.length&&<p className="method-copy">No other route currently has enough spare seats for this rider count.</p>}
  <div className="form-actions"><button className="primary-btn" type="submit" disabled={saving||!sourceRouteId||!targetRouteId}>{saving?"Transferring…":"Transfer riders"}<ChevronRight size={17}/></button></div>
 </form>:<p className="method-copy">At least two routes are required to transfer riders.</p>}
 <div className="resource-list">{data.routes.map(route=><div key={route.id}><div className="resource-icon"><Bus size={18}/></div><div><strong>{route.route_name} · {route.bus_id}</strong><span>{route.assigned_students} assigned / {route.daily_capacity} seats</span></div><b>{route.spare_seats} spare</b></div>)}</div>
 <p className="method-copy">The synthetic dataset tracks route rider counts, not individual student-to-bus records; transfers update counts only.</p></section></>
}

function Simulation(){
 const [scenarios,setScenarios]=useState([]),[scenario,setScenario]=useState(""),[duration,setDuration]=useState(4),[startsAt,setStartsAt]=useState(()=>{const now=new Date();return new Date(now.getTime()-now.getTimezoneOffset()*60000).toISOString().slice(0,16)}),[result,setResult]=useState(null),[running,setRunning]=useState(false),[loadError,setLoadError]=useState(""),[runError,setRunError]=useState("");
 const loadScenarios=()=>{get("/api/simulations/scenarios").then(d=>{setScenarios(d.scenarios);if(d.scenarios.length){setScenario(d.scenarios[0].id);setDuration(Math.max(1,Math.ceil(d.scenarios[0].duration_minutes/60)))}setLoadError("")}).catch(e=>setLoadError(e.message))};
 useEffect(()=>{loadScenarios()},[]);
 const selected=scenarios.find(s=>s.id===scenario);
 const chooseScenario=s=>{setScenario(s.id);setDuration(Math.max(1,Math.ceil(s.duration_minutes/60)))};
 const run=async()=>{if(!selected)return;setRunning(true);setRunError("");try{const response=await post("/api/simulations/run",{root_node_ids:[selected.root_node_id],duration_minutes:duration*60,starts_at:startsAt});setResult({...response,name:selected.name})}catch(e){setRunError(e.message)}finally{setRunning(false)}};
 return <><PageTitle title="Failure Simulation Centre" subtitle="Introduce one failure and trace it through the institutional dependency network."/><div className="simulation-layout"><section className="panel scenario-panel"><h3>Select failure scenario</h3><div className="scenario-list">{scenarios.map(s=><button key={s.id} onClick={()=>chooseScenario(s)} className={scenario===s.id?"selected":""}><div className="scenario-icon"><Zap size={18}/></div><div><strong>{s.name}</strong><span>{s.description}</span></div></button>)}</div>{!scenarios.length&&!loadError&&<p>No failure scenarios are available.</p>}{loadError&&<ApiError message={loadError} onRetry={loadScenarios}/>}<label className="duration">Simulation start<input type="datetime-local" value={startsAt} onChange={e=>setStartsAt(e.target.value)}/></label><label className="duration">Outage duration: <strong>{duration} hours</strong><input type="range" min="1" max="12" value={duration} onChange={e=>setDuration(+e.target.value)}/></label>{runError&&<ApiError message={runError}/>}<button className="primary-btn" onClick={run} disabled={running||!selected}>{running?"Simulating…":"Run cascading simulation"}<ChevronRight size={17}/></button></section>
 {result?<section className="panel result-panel"><div className="panel-head"><div><h3>{result.name}</h3><p>Failure root: {result.root_failures.join(", ")} · {new Date(result.starts_at).toLocaleString()} · {result.duration_minutes} minutes</p></div><span className={`severity ${result.severity.toLowerCase()}`}>{result.severity}</span></div><div className="impact-ring" style={{"--score":`${result.impact_score*3.6}deg`}}><div><strong>{result.impact_score}</strong><span>Impact</span></div></div><div className="mini-stats"><div><strong>{result.affected_resources.length}</strong><span>Affected nodes</span></div><div><strong>{result.affected_students}</strong><span>Students impacted</span></div><div><strong>{result.affected_faculty}</strong><span>Faculty impacted</span></div></div><h4>Critical chain</h4>{result.critical_chain.length?<div className="chain">{result.critical_chain.map((n,i)=><React.Fragment key={`${n}-${i}`}><span>{n}</span>{i<result.critical_chain.length-1&&<ChevronRight size={16}/>}</React.Fragment>)}</div>:<p>No downstream nodes were affected by this failure.</p>}</section>:<section className="panel empty-simulation"><Cpu size={38}/><h3>Ready to simulate</h3><p>Choose a scenario and run the constraint-aware cascade engine.</p></section>}</div></>
}

function Impact(){
 return <><PageTitle title="Cascading Impact Analysis" subtitle="One failure, traced through consequences across the campus ecosystem."/><div className="impact-grid"><section className="panel"><div className="panel-head"><h3>Impact distribution</h3></div><div className="chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={[{name:"Students",value:120},{name:"Faculty",value:18},{name:"Systems",value:9},{name:"Facilities",value:6},{name:"Operations",value:12}]}><XAxis dataKey="name" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip/><Bar dataKey="value" fill="#315efb" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer></div></section><section className="panel"><div className="panel-head"><h3>Consequence timeline</h3></div><div className="cascade-timeline"><div><time>0 min</time><span>Root failure</span><p>Main grid or service node becomes unavailable.</p></div><div><time>15 min</time><span>Direct dependencies</span><p>Dependent applications and operational rooms are degraded.</p></div><div><time>45 min</time><span>Institutional impact</span><p>Academic sessions, examination and student access are affected.</p></div></div></section></div></>
}

function Recovery(){
 const [data,setData]=useState(null),[error,setError]=useState("");
 const load=()=>{setData(null);setError("");get("/api/recovery").then(setData).catch(e=>setError(e.message))};
 useEffect(()=>{load()},[]);
 if(error)return <><PageTitle title="Intelligent Recovery Centre" subtitle="Plans evaluated against the current incident and available campus constraints."/><ApiError message={error} onRetry={load}/></>;
 if(!data)return <Loading/>;
 if(!data.plans.length)return <><PageTitle title="Intelligent Recovery Centre" subtitle="Plans evaluated against the current incident and available campus constraints."/><section className="panel"><p>No recovery options match the current incident.</p></section></>;
 return <><PageTitle title="Intelligent Recovery Centre" subtitle="Constraint-ranked recovery options for the latest open incident."/><p className="method-copy">{data.recommendation_reason}</p><div className="recovery-grid">{data.plans.map((p,i)=>{const recommended=p.id===data.recommended_plan_id;const restoredCount=p.services_restored.length+p.allocations.length;return <motion.section initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} className={`panel recovery-card ${recommended?"recommended":""}`} key={p.id}><div className="plan-head"><div><span>Plan {i+1} · {p.scenario_family}</span><h3>{p.name}</h3></div>{recommended&&<b>Recommended</b>}</div><div className="plan-score"><strong>{restoredCount}</strong><span>restored items</span></div><div className="plan-metrics"><div><span>Feasibility</span><strong>{p.feasible?"Feasible":"Blocked"}</strong></div><div><span>Setup</span><strong>{p.estimated_setup_minutes} min</strong></div><div><span>Disruption</span><strong>{p.disruption}</strong></div></div><p>Capacity: {p.capacity_limit} · Cost: {p.cost_units} units</p>{p.services_restored.length>0&&<><h4>Services and activities</h4><ol>{p.services_restored.map(id=><li key={id}><CheckCircle2 size={15}/>{id}</li>)}</ol></>}{p.allocations.length>0&&<><h4>Room allocations</h4><ol>{p.allocations.map(a=><li key={a.activity_id}><CheckCircle2 size={15}/>{a.activity_id}: {a.from_room} → {a.to_room}</li>)}</ol></>}{p.constraints.length>0&&<><h4>Constraints</h4><ol>{p.constraints.map(item=><li key={item}><AlertTriangle size={15}/>{item}</li>)}</ol></>}</motion.section>})}</div><section className="panel"><h3>Data limitations</h3>{data.data_limitations.map(item=><p className="method-copy" key={item}>{item}</p>)}<p className="method-copy">{data.optimization_method}</p></section></>
}

function Optimization(){
 const before=[{name:"Rooms",used:78,available:22},{name:"Labs",used:64,available:36},{name:"Faculty",used:82,available:18},{name:"Transport",used:71,available:29},{name:"Power",used:88,available:12}];
 return <><PageTitle title="Resource Optimization" subtitle="Before-and-after capacity planning under campus constraints."/><div className="dashboard-grid"><section className="panel chart-panel"><div className="panel-head"><h3>Resource utilization</h3><span className="status-badge green">Optimized</span></div><div className="chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={before}><XAxis dataKey="name" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip/><Bar dataKey="used" stackId="a" fill="#315efb" radius={[5,5,0,0]}/><Bar dataKey="available" stackId="a" fill="#e8edf5" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer></div></section><section className="panel"><div className="panel-head"><h3>Optimization constraints</h3></div><div className="constraint-list"><div><span>Capacity</span><b>Within limits</b></div><div><span>Faculty availability</span><b>Within limits</b></div><div><span>Equipment</span><b>1 exception</b></div><div><span>Time windows</span><b>Resolved</b></div></div></section></div></>
}

function Risk(){
 const heat=[{n:"Power",c:92},{n:"Network",c:74},{n:"ERP",c:68},{n:"Labs",c:61},{n:"Transport",c:48},{n:"Water",c:55}];
 return <><PageTitle title="Risk Analytics" subtitle="Dependency-informed institutional risk indicators from defined simulation assumptions."/><div className="risk-grid">{heat.map(h=><div className="risk-cell" key={h.n} style={{"--risk":`${h.c}%`}}><strong>{h.n}</strong><span>{h.c} risk index</span></div>)}</div><div className="section-grid"><section className="panel"><div className="panel-head"><h3>Preventive recommendations</h3></div><div className="recommendation-list"><div><ShieldCheck/><p><strong>Test campus generator monthly</strong><span>Reduces power-failure duration exposure.</span></p></div><div><WifiOff/><p><strong>Add secondary ISP failover</strong><span>Protects ERP and cloud-dependent operations.</span></p></div><div><Bus/><p><strong>Cross-train backup transport staff</strong><span>Improves response to bus breakdowns.</span></p></div></div></section><section className="panel"><div className="panel-head"><h3>Risk methodology</h3></div><p className="method-copy">This prototype reports a deterministic risk index derived from resource criticality, dependency breadth and simulated frequency assumptions. It does not claim statistical predictive accuracy.</p></section></div></>
}

function Incidents(){
 const [rows,setRows]=useState([]),[q,setQ]=useState("");useEffect(()=>get("/api/incidents").then(d=>setRows(d.incidents)),[]);
 const filtered=rows.filter(r=>`${r.id} ${r.failure_type} ${r.failed_resource}`.toLowerCase().includes(q.toLowerCase()));
 return <><PageTitle title="Incident History & Reports" subtitle="Search, review and export simulated institutional incidents." action={<a className="secondary-btn" href={`${API}/api/incidents/export`}><Download size={16}/>Export CSV</a>}/><div className="filter-row"><div className="search-box"><Search size={17}/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search incident ID or resource"/></div><select><option>All statuses</option><option>Open</option><option>Resolved</option></select></div><div className="table-panel"><table><thead><tr><th>Incident</th><th>Failed resource</th><th>Timestamp</th><th>Severity</th><th>Impact</th><th>Status</th></tr></thead><tbody>{filtered.map(r=><tr key={r.id}><td><strong>{r.failure_type}</strong><small>{r.id}</small></td><td>{r.failed_resource}</td><td>{new Date(r.timestamp).toLocaleString()}</td><td><span className={`severity ${r.severity.toLowerCase()}`}>{r.severity}</span></td><td>{r.impact_score}</td><td><span className={`status-badge ${r.resolution_status==="Resolved"?"green":"orange"}`}>{r.resolution_status}</span></td></tr>)}</tbody></table></div></>
}

function Settings(){
 return <><PageTitle title="Administration" subtitle="Configure campus model, account access and operational preferences."/><div className="settings-grid"><section className="panel"><div className="panel-head"><h3>Institution profile</h3></div><div className="form-grid"><label>Institution name<input defaultValue="Engineering College Campus"/></label><label>Administrator email<input defaultValue="admin@omnisx.com"/></label><label>Timezone<select defaultValue="Asia/Kolkata"><option>Asia/Kolkata</option><option>UTC</option></select></label><label>Operational mode<select><option>Live command centre</option><option>Training simulation</option></select></label></div><button className="primary-btn" onClick={()=>alert("Institution settings saved for this demo session.")}>Save settings</button></section><section className="panel"><div className="panel-head"><h3>System status</h3><span className="status-badge green">Online</span></div><div className="constraint-list"><div><span>Backend API</span><b>Connected</b></div><div><span>SQLite database</span><b>Initialized</b></div><div><span>Dependency engine</span><b>Ready</b></div><div><span>Recovery engine</span><b>Rule-based</b></div></div></section></div></>
}

createRoot(document.getElementById("root")).render(<BrowserRouter><Routes><Route path="/" element={<Login/>}/><Route path="/*" element={<Shell/>}/></Routes></BrowserRouter>);
