import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Signal, ChargeSignal } from './Signals';
import evidence from './evidence.json';
const Scene=lazy(()=>import('./Scene'));
const chapters=['The question','Follow the beam','The machine','The evidence','The investigation','The challenge','What we know'];
const ids=['question','beam','machine','evidence','investigation','challenge','conclusion'];
const Arrow=({down=false}:{down?:boolean})=><span aria-hidden="true">{down?'↓':'↗'}</span>;
const steps=[
  {agent:'Equipment specialist',role:'equipment',title:'One amplitude reading collapses.',text:'KLYS:LI29:11:AMPL records 0.024 against a baseline of 69.116. A later update returns to 69.092.',tag:'RF amplitude · 20 recorded updates'},
  {agent:'Beam specialist',role:'beam',title:'The beam evidence changes too.',text:'Three monitors lose charge. LTUH:250 retains valid charge and shows a sustained horizontal excursion.',tag:'4 beam monitors · charge + position'},
  {agent:'Equipment specialist',role:'equipment',title:'Timing has a blind spot.',text:'Sparse, asynchronous RF reporting limits timestamp comparisons. Neighboring stations include 28 unknown baselines.',tag:'Additional timing + neighbor checks'},
  {agent:'Investigator',role:'lead',title:'Associated. Not proven causal.',text:'Both an RF anomaly and a beam disturbance are supported. The evidence does not identify this station as the unique cause.',tag:'Specialist findings reconciled'},
];

export default function App(){
  const [progress,setProgress]=useState(0),[active,setActive]=useState(0),[reduced,setReduced]=useState(false),[step,setStep]=useState(-1),[running,setRunning]=useState(false),[challenged,setChallenged]=useState(false),[modal,setModal]=useState<'sources'|'initial'|'followup'|null>(null);
  const timer=useRef<ReturnType<typeof setInterval>|null>(null),closeRef=useRef<HTMLButtonElement>(null),previousFocus=useRef<HTMLElement|null>(null);
  useEffect(()=>{const mq=matchMedia('(prefers-reduced-motion: reduce)');const change=()=>setReduced(mq.matches);change();mq.addEventListener('change',change);return()=>mq.removeEventListener('change',change);},[]);
  useEffect(()=>{let frame=0;const update=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{const positions=ids.map(id=>document.getElementById(id)!.offsetTop);const scroll=window.scrollY;let current=0;while(current<6&&scroll>=positions[current+1])current++;const delta=current<6?(scroll-positions[current])/(positions[current+1]-positions[current]):0;setProgress(current+Math.min(1,Math.max(0,delta)));setActive(Math.min(6,Math.max(0,Math.round(current+delta))));});};update();addEventListener('scroll',update,{passive:true});addEventListener('resize',update);return()=>{cancelAnimationFrame(frame);removeEventListener('scroll',update);removeEventListener('resize',update);};},[]);
  useEffect(()=>()=>{if(timer.current)clearInterval(timer.current);},[]);
  useEffect(()=>{if(!modal)return;previousFocus.current=document.activeElement as HTMLElement;const old=document.body.style.overflow;document.body.style.overflow='hidden';closeRef.current?.focus();const esc=(e:KeyboardEvent)=>{if(e.key==='Escape')setModal(null);if(e.key==='Tab'){const els=Array.from(document.querySelectorAll<HTMLElement>('.modal button,.modal a'));const first=els[0],last=els.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}};addEventListener('keydown',esc);return()=>{document.body.style.overflow=old;removeEventListener('keydown',esc);previousFocus.current?.focus();};},[modal]);
  function go(i:number){document.getElementById(ids[i])?.scrollIntoView({behavior:reduced?'instant':'smooth'});}
  function investigate(){if(timer.current)clearInterval(timer.current);let index=0;setStep(0);setRunning(true);timer.current=setInterval(()=>{index++;setStep(index);if(index>=3){if(timer.current)clearInterval(timer.current);setRunning(false);}},reduced?900:2400);}
  function reset(){if(timer.current)clearInterval(timer.current);setStep(-1);setRunning(false);setChallenged(false);go(0);}
  return <>
    <a className="skip-link" href="#evidence">Skip to real SLAC evidence</a>
    <div className={`stage scene-${active}`} aria-hidden="true"><Suspense fallback={<div className="loading">Preparing the beamline<span/></div>}><Scene progress={progress} reduced={reduced} agentStep={step}/></Suspense></div>
    <div className="vignette"/>
    <header><a className="brand" href="#question" aria-label="Beamline Investigator home"><span className="brand-mark">↗</span><span>BEAMLINE<span className="brand-sub">INVESTIGATOR</span></span></a><div className="header-right"><span className="recorded"><i/>REAL SLAC DATA · RECORDED RUN</span><button className="text-button" onClick={()=>setModal('sources')}>About the evidence <Arrow/></button></div></header>
    <nav className="chapters" aria-label="Story chapters">{chapters.map((c,i)=><button key={c} aria-label={`Chapter ${i+1}: ${c}`} title={c} className={active===i?'active':''} onClick={()=>go(i)} aria-current={active===i?'step':undefined}><span className="chapter-number">0{i+1}</span><span className="chapter-name">{c}</span></button>)}</nav>
    <main>
      <section id="question" className="chapter hero">
        <div className="copy hero-copy"><p className="eyebrow">A SMALL STRUCTURE. A VERY BIG MACHINE.</p><h1>To see the<br/>invisible,<br/><em>trust the beam.</em></h1><p className="lede">A protein is tiny. The instrument that helps us understand it is anything but.</p><button className="primary" onClick={()=>go(1)}>Follow the beam <Arrow down/></button></div>
        <div className="model-label"><span className="crosshair">+</span> MOLECULAR STRUCTURE<span>Illustrative ribbon model · drag to rotate</span></div>
        <div className="bottom-note"><span>COLLABORATIVE AI FOR ACCELERATOR INVESTIGATION</span><span>SCROLL TO EXPLORE ↓</span></div>
      </section>
      <section id="beam" className="chapter beam-section">
        <div className="copy wide-copy"><p className="eyebrow">01 / FROM ACCELERATOR TO EXPERIMENT</p><h2>A line of light.<br/><em>A chain of precision.</em></h2><p className="lede">Accelerator equipment energizes electrons. An undulator turns that motion into X-rays, which illuminate a sample.</p></div>
        <div className="beam-labels"><span><i className="cyan-dot"/>ELECTRONS<small>Accelerator</small></span><span className="undulator-label">UNDULATOR<small>X-rays are produced here</small></span><span><i className="violet-dot"/>X-RAYS<small>Experiment → measurement</small></span></div>
        <p className="scene-note">ILLUSTRATIVE SYSTEM VIEW · NOT TO SCALE</p>
      </section>
      <section id="machine" className="chapter machine-section">
        <div className="copy"><p className="eyebrow orange">02 / WHEN SOMETHING CHANGES</p><h2>One signal changes.<br/><em>What else did?</em></h2><p className="lede">Did the beam suffer too—and are these events connected?</p></div>
        <div className="machine-callout"><span className="ping"/>EQUIPMENT SIGNAL CHANGES<span>Follow the evidence across subsystems.</span></div>
        <div className="physical-chain"><span>Equipment</span><b>→</b><span>Beam</span><b>→</b><span>Experiment</span><b>→</b><span>Measurement</span></div>
        <p className="scene-note">CONCEPTUAL DISTURBANCE · NOT A RECONSTRUCTION OF THIS EVENT</p>
      </section>
      <section id="evidence" className="chapter evidence-section">
        <div className="evidence-heading"><div><p className="eyebrow cyan">03 / THE ACTUAL RECORDING</p><h2>Now, the real signals.</h2></div><div className="event-stamp"><span>SLAC / RF ANOMALY DATASET</span><strong>slac-001</strong><span>KLYS:LI29:11 · 02 NOV 2020 UTC</span></div></div>
        <p className="section-intro">An equipment amplitude collapse. A charge-valid beam excursion. One shared investigation window.</p>
        <div className="signal-stack"><Signal type="rf"/><Signal type="beam"/></div>
        <div className="evidence-caption"><span><b>The clocks matter.</b> The beam disturbance appears about 2.5 seconds before the near-zero RF update. Sparse RF reporting prevents a causal reading of that order.</span><button className="text-button" onClick={()=>setModal('sources')}>Inspect the source <Arrow/></button></div>
        <button className="inline-next" onClick={()=>go(4)}>Bring in the specialists <Arrow down/></button>
      </section>
      <section id="investigation" className="chapter investigation-section">
        <div className="copy wide-copy"><p className="eyebrow">04 / DIFFERENT EVIDENCE. ONE INVESTIGATION.</p><h2>Specialists connect<br/><em>the evidence.</em></h2><p className="lede">Was the low-charge event associated with the equipment anomaly?</p></div>
        <div className="agent-workspace">
          <div className="agent-network" aria-label="Equipment and beam specialists pass evidence to the investigator">
            <svg viewBox="0 0 700 230" className="connections" aria-hidden="true"><path d="M125 190 Q125 68 350 58 M575 190 Q575 68 350 58"/><path className={running?'packet-path traveling':'packet-path'} d="M125 190 Q125 68 350 58 M575 190 Q575 68 350 58"/></svg>
            <div className={`agent investigator ${step===3?'thinking':''}`}><span className="orb">I</span><strong>Investigator</strong><small>Reconcile · request · assess</small></div>
            <div className={`agent equipment ${step===0||step===2?'thinking':''}`}><span className="orb">E</span><strong>Equipment specialist</strong><small>RF amplitude + neighboring stations</small></div>
            <div className={`agent beam ${step===1?'thinking':''}`}><span className="orb">B</span><strong>Beam specialist</strong><small>Charge + valid position measurements</small></div>
          </div>
          <div className="investigation-controls"><button className="primary" disabled={running} onClick={investigate}>{running?'Reviewing recorded findings…':step===3?'Replay investigation':'Investigate'} <Arrow/></button><span>Recorded agent run · accelerated playback<br/>No new model call</span></div>
          <div className="finding" aria-live="polite">{step<0?<><span className="finding-index">READY</span><div><h3>Different signals. Partial views.</h3><p>Watch the recorded handoffs, additional checks, and final synthesis.</p></div></>:<><span className="finding-index">0{step+1} / 04</span><div><p className="finding-agent">{steps[step].agent} <span>· {steps[step].tag}</span></p><h3>{steps[step].title}</h3><p>{steps[step].text}</p><div className="finding-actions"><button className="text-button" onClick={()=>setModal('initial')}>Read original agent evidence <Arrow/></button>{step===3&&<button className="text-button cyan" onClick={()=>go(5)}>Challenge the finding ↓</button>}</div></div></>}</div>
          <p className="micro-note">Presentation summaries of the saved run, in recorded finding order. Collaboration includes follow-up checks—not a vote.</p>
        </div>
      </section>
      <section id="challenge" className="chapter challenge-section">
        <div className="copy wide-copy"><p className="eyebrow">05 / THE HUMAN ASKS A BETTER QUESTION</p><h2>“Could low charge<br/><em>explain the readings?”</em></h2><p className="lede">A dramatic position value is not evidence of beam motion when the charge is too low to measure it.</p></div>
        <div className="charge-investigation"><ChargeSignal/><div className="charge-table"><div className="charge-row table-heading"><span>BEAM MONITOR</span><span>CHARGE IN THIS WINDOW</span><span>POSITION EVIDENCE</span></div>{['DMPH:502','DMPH:693','LTUH:450','LTUH:250'].map((name,i)=><div key={name} className={`charge-row ${i===3?'valid-row':''} ${challenged?'reviewed':''}`}><strong>{name}</strong><span><i className={i===3?'cyan-dot':'orange-dot'}/>{i===3?'Remains valid':'Low charge'}</span><span>{i===3?'Retained':challenged?'Excluded when charge is low':'Requires charge check'}{i===3&&<b>✓</b>}</span></div>)}</div>
          {!challenged?<button className="primary challenge-button" onClick={()=>setChallenged(true)}>Review the low-charge challenge <Arrow/></button>:<div className="challenge-answer" aria-live="polite"><div className="answer-mark">✓</div><div><h3>The disturbance survives the check.</h3><p>Low charge invalidates position readings at three monitors. But LTUH:250 still has valid charge and a sustained horizontal excursion. The beam disturbance remains supported.</p><button className="text-button" onClick={()=>setModal('followup')}>Read the saved follow-up <Arrow/></button></div></div>}
          <p className="micro-note">Actual rule: TMIT &lt; 10⁸ invalidates position. These invalid readings are already excluded from the plotted trace. This button reveals the recorded follow-up.</p>
        </div>
      </section>
      <section id="conclusion" className="chapter conclusion-section">
        <div className="copy conclusion-copy"><p className="eyebrow cyan">06 / FROM ANOMALY TO UNDERSTANDING</p><h2>More evidence.<br/><em>Less guesswork.</em></h2><div className="verdict"><p><span className="verdict-symbol">✓</span><span><strong>Beam disturbance supported.</strong><small>Valid beam evidence and an associated RF amplitude anomaly.</small></span></p><p><span className="verdict-symbol uncertain">?</span><span><strong>Unique cause not established.</strong><small>Reporting delays, missing neighbor baselines, and no RF phase data limit the conclusion.</small></span></p></div><p className="closing-line">AI helps scientists connect evidence<br/>across complex accelerator systems.</p><div className="closing-actions"><button className="primary" onClick={reset}>Replay the story ↺</button><button className="text-button" onClick={()=>setModal('sources')}>Explore the evidence <Arrow/></button></div></div>
        <div className="closing-quote">Before scientists can understand what nature did,<br/>they need to trust what their machine saw.</div>
        <footer><span>BEAMLINE INVESTIGATOR</span><span>REAL SLAC MEASUREMENTS · COLLABORATIVE AGENTS · HUMAN JUDGMENT</span><a href="https://github.com/GavinRS/slac-investigator" target="_blank" rel="noreferrer">View project <Arrow/></a></footer>
      </section>
    </main>
    <div className="progress-line" style={{transform:`scaleX(${Math.min(1,progress/6)})`}}/>
    {modal&&<div className="modal-backdrop" onClick={e=>{if(e.target===e.currentTarget)setModal(null);}}><div className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><button ref={closeRef} className="modal-close" onClick={()=>setModal(null)} aria-label="Close evidence">×</button>{modal==='sources'?<>
      <p className="eyebrow cyan">DATA & PROVENANCE</p><h2 id="modal-title">Real measurements.<br/>Explicit limits.</h2><p>This presentation uses <strong>slac-001</strong>, an extracted candidate from SLAC’s archived RF anomaly dataset. The cinematic geometry and disturbance are explanatory illustrations, not an event reconstruction or a facility digital twin.</p>
      <dl><dt>Source group</dt><dd>candidates/1604277203201922048</dd><dt>Time reference</dt><dd>0s = 2020-11-02 00:33:23.201922048 UTC, the candidate endpoint.</dd><dt>Candidate window</dt><dd>−5.3s to 0s. Both charts share the same time axis and highlighted candidate interval.</dd><dt>Equipment</dt><dd>82 RF amplitude channels in the extract. The selected station is KLYS:LI29:11:AMPL, with 20 finite updates across its extended history. Missing updates are not zero.</dd><dt>Beam</dt><dd>Four beam monitors, each with charge (TMIT) and one position coordinate. The charge-valid LTUH:250:X trace is shown in source-scaled units, not millimeters. No post-candidate BPM samples are available.</dd><dt>Measurement validity</dt><dd>Charge below 10⁸ invalidates position. Sentinel-coded low-charge positions are masked, not interpreted as beam motion.</dd><dt>What this establishes</dt><dd>An RF anomaly and a beam disturbance are supported within the selected incident window. Reporting latency and incomplete neighboring records prevent a unique-cause claim.</dd><dt>Agent execution</dt><dd>The buttons replay two saved collaborative Flower runs. They do not launch a live model call. Animated timing is compressed; the original initial run took about {Math.round(evidence.runs[0].latency)} seconds. The three roles are equipment, beam, and investigator.</dd></dl>
      <p>No protein measurements, RF phase measurements, causal intervention, or accelerator control are included. This selected case is not an accuracy benchmark.</p><div className="source-links"><a href="https://www.slac.stanford.edu/grp/ad/ard/rfanom/" target="_blank" rel="noreferrer">SLAC dataset ↗</a><a href="https://github.com/GavinRS/slac-investigator/blob/main/docs/DATA_PROVENANCE.md" target="_blank" rel="noreferrer">Extraction & limitations ↗</a><a href="./console/">Open operator console ↗</a></div>
    </>:<><p className="eyebrow cyan">ORIGINAL SAVED AGENT OUTPUT</p><h2 id="modal-title">{modal==='initial'?'The investigation':'The human challenge'}</h2><p>Run {evidence.runs[modal==='initial'?0:1].id} · recorded via Flower. This is the original saved report, including its original schema and assessment wording.</p>{modal==='followup'&&<blockquote>{evidence.runs[1].question}</blockquote>}<pre>{JSON.stringify(evidence.runs[modal==='initial'?0:1].report,null,2)}</pre></>}</div></div>}
  </>;
}
