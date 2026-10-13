"use client";
import { useEffect, useState } from "react";

type Slot = {start:string;end:string;energy_kwh:string;power_kw:string;cost:string;price_per_kwh:string};
type Schedule = {slots:Slot[];cost:string;energy_kwh:string};
type Proposal = {plan_id:string;deadline:string;optimized:Schedule;baseline:Schedule;savings:string;savings_percent:string};
type Execution = {execution_id:string;status:string;executed_at:string;proposal:Proposal};
type State = {demo_now:string;device:{name:string;required_kwh:string;max_power_kw:string;available_from:string;available_until:string;active_plan_id:string|null};prices:{tariffs:{start:string;price_per_kwh:string}[]};history:{executions:Execution[]}};
type Recognition = {lang:string;onresult:((event:{results:{transcript:string}[][]})=>void)|null;onerror:(()=>void)|null;onend:(()=>void)|null;start:()=>void};
const money = (v:string|number) => new Intl.NumberFormat("en-IN", {style:"currency",currency:"INR",maximumFractionDigits:2}).format(Number(v));
const time = (v:string) => new Date(v).toLocaleTimeString("en-IN", {timeZone:"Asia/Kolkata",hour:"numeric",minute:"2-digit"});
const date = (v:string) => new Date(v).toLocaleDateString("en-IN", {timeZone:"Asia/Kolkata",day:"numeric",month:"short",year:"numeric"});
async function api(path:string, body?:unknown) {
  const res = await fetch(`/api/${path}`, body ? {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)} : {cache:"no-store"});
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail?.message || "The request could not be completed.");
  return data;
}

function ScheduleTable({label,schedule,accent=false}:{label:string;schedule:Schedule;accent?:boolean}) {
  return <section className={`schedule ${accent ? "optimized" : ""}`}><div className="flex items-center justify-between gap-3"><h3>{label}</h3><strong>{money(schedule.cost)}</strong></div><p className="muted text-sm mb-5">{Number(schedule.energy_kwh)} kWh · {schedule.slots[0]?.power_kw} kW charging</p><table><thead><tr><th>Time · IST</th><th>Energy</th><th>Cost</th></tr></thead><tbody>{schedule.slots.map(s=><tr key={s.start}><td>{time(s.start)}–{time(s.end)}</td><td>{Number(s.energy_kwh).toFixed(2)} kWh</td><td>{money(s.cost)}</td></tr>)}</tbody></table></section>;
}

export default function Home() {
  const [state,setState] = useState<State|null>(null);
  const [text,setText] = useState("Charge my EV before 7 AM using the cheapest available electricity.");
  const [review,setReview] = useState<{proposal:Proposal;confirmation_token:string}|null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [listening,setListening] = useState(false);
  const [voice,setVoice] = useState(false);
  async function refresh() {setState(await api("state"));}
  useEffect(()=>{refresh().catch(e=>setError(e.message)); const w=window as unknown as {SpeechRecognition?:unknown;webkitSpeechRecognition?:unknown};setVoice(Boolean(w.SpeechRecognition || w.webkitSpeechRecognition));},[]);
  async function plan() {
    setBusy(true);setError("");setReview(null);
    try {setReview(await api("plan",{text}));} catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  async function approve() {
    if(!review) return;
    setBusy(true);setError("");
    try {await api("approve",{plan_id:review.proposal.plan_id,confirmation_token:review.confirmation_token,confirmed:true});setReview(null);await refresh();}
    catch(e){setError((e as Error).message);} finally {setBusy(false);}
  }
  function dictate() {
    const w=window as unknown as {SpeechRecognition?:new()=>Recognition;webkitSpeechRecognition?:new()=>Recognition};
    const Constructor=w.SpeechRecognition || w.webkitSpeechRecognition;
    if(!Constructor)return;
    const recognition=new Constructor();recognition.lang="en-IN";
    recognition.onresult=e=>{setText(e.results[0][0].transcript);setReview(null);};
    recognition.onerror=()=>{setError("Microphone unavailable. You can type your request instead.");setListening(false);};
    recognition.onend=()=>setListening(false);setListening(true);
    try{recognition.start();}catch{setListening(false);setError("Could not start microphone.");}
  }
  const executed=state?.history.executions[0];
  const displayed=review?.proposal || executed?.proposal;
  return <main className="shell">
    <header><a className="brand" href="/" aria-label="WattWise home"><span className="brand-icon">ϟ</span> wattwise<span className="brand-dot">.</span></a><div className="flex items-center gap-3"><span className="status-dot"/><span className="text-sm">Home energy lab</span><span className="pill">SIMULATION</span></div></header>
    <div className="intro"><div><p className="eyebrow">LESS SPEND. SAME MORNING.</p><h1>A smarter night<br/>for your next drive.</h1><p className="subtitle">Tell us when you need a charge.<br className="sm:hidden"/> We’ll find the lowest-cost hours.</p></div><div className="clock"><span className="eyebrow">DEMO CLOCK · IST</span><strong>{state ? time(state.demo_now) : "Connecting…"}</strong><span>{state ? date(state.demo_now) : "Waiting for MCP server"}</span><small>Fixed time for a repeatable scenario</small></div></div>
    {error && <div role="alert" className="error">{error}<button onClick={()=>refresh().then(()=>setError("")).catch(e=>setError(e.message))}>Retry connection</button></div>}
    <div className="workspace"><div className="main-column">
      <section className="request-card"><div className="flex items-center justify-between"><p className="eyebrow">01 / YOUR REQUEST</p><span className="text-sm muted">EV charging</span></div><label htmlFor="request" className="sr-only">Charging request</label><textarea id="request" value={text} onChange={e=>{setText(e.target.value);setReview(null);}} disabled={busy||Boolean(executed)} rows={3}/><div className="request-actions"><button className="mic" disabled={!voice||busy||listening||Boolean(executed)} onClick={dictate}>{listening ? "Listening…" : "◉ Speak request"}</button><button className="primary" onClick={plan} disabled={busy||!state||!text.trim()||Boolean(executed)}>{busy ? "Working…" : "Find my best schedule →"}</button></div><p className="fine">{voice ? "Microphone uses your browser’s speech service. Review the transcript before planning." : "Voice input isn’t available in this browser. Type your request to use the same flow."} Nothing runs until you confirm.</p></section>
      <section className="tariff-card"><div className="section-heading"><div><p className="eyebrow">TONIGHT’S ELECTRICITY</p><h2>Good things come to those who wait.</h2></div><span className="pill">SYNTHETIC DATA</span></div><div className="tariff-bars" aria-label="Hourly synthetic electricity rates in INR per kWh">{state?.prices.tariffs.map(t=><div className="bar-column" key={t.start}><span className="bar-price">₹{t.price_per_kwh}</span><div className={`bar ${Number(t.price_per_kwh)<=4?"cheap":""}`} style={{height:`${Number(t.price_per_kwh)/12*100}px`}}/><span className="bar-label">{time(t.start).replace(":00","")}</span></div>)}</div><div className="flex justify-between text-xs muted mt-4 gap-3"><span><i className="legend"/> Lowest-price hours</span><span>INR / kWh · synthetic-demo-v1</span></div></section>
      {displayed && <section className="results" aria-live="polite"><div className="section-heading"><div><p className="eyebrow">02 / {review ? "REVIEW YOUR PLAN" : "APPROVED PLAN"}</p><h2>{review ? "Ready for a cheaper charge?" : "Your morning is planned."}</h2></div><span className="pill">{review?"AWAITING APPROVAL":"SCHEDULED"}</span></div><p className="muted mb-5">Ready by {time(displayed.deadline)} on {date(displayed.deadline)} · IST</p><div className="savings"><span>Estimated savings<strong>{money(displayed.savings)}</strong></span><span className="saving-percent">{Number(displayed.savings_percent).toFixed(1)}%<small>vs. charging immediately</small></span></div><div className="schedules"><ScheduleTable label="Charge immediately" schedule={displayed.baseline}/><ScheduleTable label="WattWise schedule" schedule={displayed.optimized} accent/></div>{review && <div className="confirmation"><p>Apply this exact schedule to the <strong>simulated driveway charger</strong>?</p><div className="flex gap-3 mt-4"><button className="primary" onClick={approve} disabled={busy}>Confirm & apply schedule</button><button className="secondary" onClick={()=>setReview(null)} disabled={busy}>Cancel</button></div></div>}{!review && <p className="success">✓ Approved and saved to the simulated charger. Energy delivery is not simulated.</p>}</section>}
    </div><aside><section className="device-card"><div className="flex justify-between"><p className="eyebrow">YOUR DEVICE</p><span className="device-symbol">↯</span></div><h2>Driveway EV</h2><span className="pill">SIMULATED CHARGER</span><div className="device-stat"><span>Energy needed</span><strong>{state?.device.required_kwh || "—"} <small>kWh</small></strong></div><div className="device-stat"><span>Maximum power</span><strong>{state?.device.max_power_kw || "—"} <small>kW</small></strong></div><div className="device-stat"><span>Availability · IST</span><strong className="text-lg">{state ? time(state.device.available_from) + ' – ' + time(state.device.available_until) : '—'}</strong></div><div className="device-state"><span className="status-dot"/>{state?.device.active_plan_id ? "Schedule applied" : "Awaiting a schedule"}</div></section><section className="log"><p className="eyebrow">EXECUTION LOG</p><h2>Every action, accounted for.</h2>{state?.history.executions.length ? state.history.executions.map(e=><article key={e.execution_id}><span className="log-check">✓</span><div><strong>Charging schedule applied</strong><p>Explicitly confirmed · simulated</p><p>{date(e.executed_at)} · {time(e.executed_at)} IST</p><code>{e.execution_id.slice(0,8)}</code></div></article>) : <p className="muted text-sm mt-4">No actions yet. Approved schedules appear here and persist across restarts.</p>}</section><div className="lab-note"><span>↳</span><p>A working local energy lab.<br/>Real calculations. Synthetic prices.<br/>You stay in control.</p></div></aside></div>
    <footer><span>WATTWISE / HOME ENERGY LAB</span><span>Local MCP connection · No live tariffs · No Alexa+ connection</span></footer>
  </main>;
}
