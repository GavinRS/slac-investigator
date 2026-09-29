import { memo, useId, useState } from 'react';
import data from './evidence.json';
type Point=[number,number|null];
const W=850,H=240,L=54,R=24,T=31,B=38;
export const Signal = memo(function Signal({type,compact=false}:{type:'rf'|'beam';compact?:boolean}) {
  const [hover,setHover]=useState<number|null>(null),uid=useId().replace(/:/g,'');
  const isRF=type==='rf', points=(isRF?data.rf.points:data.beam[0].points) as Point[];
  const xmin=-12,xmax=5.3,ymin=isRF?0:-32,ymax=isRF?75:3;
  const x=(v:number)=>L+(v-xmin)/(xmax-xmin)*(W-L-R),y=(v:number)=>H-B-(v-ymin)/(ymax-ymin)*(H-T-B);
  let line='',started=false;
  if(isRF){
    const prev=points.filter(p=>p[0]<=xmin).at(-1);if(prev&&prev[1]!==null){line=`M${x(xmin)},${y(prev[1])}`;started=true;}
    points.filter(p=>p[0]>xmin&&p[0]<=xmax).forEach(p=>{if(p[1]!==null){line+=`${started?'H':'M'}${x(p[0])}${started?'V':','}${y(p[1])}`;started=true;}});
    if(started)line+=`H${x(xmax)}`;
  }else{
    points.filter(p=>p[0]>=xmin&&p[0]<=xmax).forEach(p=>{if(p[1]===null){started=false;return;}line+=`${started?'L':'M'}${x(p[0])},${y(p[1])}`;started=true;});
  }
  const nearest=hover===null?null:points.reduce((best,p)=>Math.abs(p[0]-hover)<Math.abs(best[0]-hover)?p:best,points[0]);
  return <div className={`signal ${compact?'compact':''}`}>
    <div className="signal-title"><span><i className={type}/>{isRF?'Equipment · RF amplitude':'Beam · horizontal position'}</span><code>{isRF?'KLYS:LI29:11:AMPL':'BPMS:LTUH:250:X'}</code></div>
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={isRF?'Recorded RF amplitude drops from about 69.1 to 0.024 at candidate end, then returns at 5 seconds.':'Charge-valid horizontal position at LTUH 250 changes during the candidate window. Position uses source-scaled units.'} onPointerMove={e=>{const rect=e.currentTarget.getBoundingClientRect();const px=(e.clientX-rect.left)/rect.width*W;setHover(xmin+(px-L)/(W-L-R)*(xmax-xmin));}} onPointerLeave={()=>setHover(null)}>
      <defs><clipPath id={uid}><rect x={L} y={T-8} width={W-L-R} height={H-T-B+8}/></clipPath></defs>
      <rect x={x(-5.3)} y={T-10} width={x(0)-x(-5.3)} height={H-T-B+10} fill="#59c7e7" opacity=".055"/>
      <text x={x(-5.3)+8} y={T-15} className="chart-label">SAME CANDIDATE WINDOW</text>
      {(isRF?[0,35,70]:[-30,-15,0]).map(n=><g key={n}><line x1={L} x2={W-R} y1={y(n)} y2={y(n)} stroke="#23313f" strokeWidth="1"/><text x={L-12} y={y(n)+4} textAnchor="end" className="chart-tick">{n}</text></g>)}
      {[-10,-5,0,5].map(n=><g key={n}><line x1={x(n)} x2={x(n)} y1={H-B} y2={H-B+5} stroke="#57657b"/><text x={x(n)} y={H-13} textAnchor="middle" className="chart-tick">{n>0?'+':''}{n}s</text></g>)}
      <g clipPath={`url(#${uid})`}><line x1={x(0)} x2={x(0)} y1={T-8} y2={H-B} stroke="#8192ad" opacity=".4" strokeDasharray="3 5"/><path d={line} fill="none" stroke={isRF?'#ffb073':'#54deec'} strokeWidth={isRF?2.5:1.5} strokeLinejoin="round"/>
        {isRF&&points.filter(p=>p[0]>=xmin&&p[0]<=xmax&&p[1]!==null).map((p,i)=><circle key={i} cx={x(p[0])} cy={y(p[1]!)} r="3.5" fill="#ffb073" stroke="#08121d" strokeWidth="1.5"/>)}
        {!isRF&&<rect x={x(0)} y={T-8} width={x(xmax)-x(0)} height={H-T-B+8} fill="#050a14" opacity=".5"/>}
        {nearest&&hover!==null&&hover>=xmin&&hover<=xmax&&<line x1={x(nearest[0])} x2={x(nearest[0])} y1={T-8} y2={H-B} stroke="#eef7ff" opacity=".5"/>}
      </g>
      {!isRF&&<text x={x(2.6)} y={y(-15)} textAnchor="middle" className="chart-label">NO BPM SAMPLES</text>}
    </svg>
    <div className="signal-foot"><span>{isRF?'Dots = recorded updates · steps hold last known value':'Charge-valid samples only · source-scaled position'}</span><span>{nearest&&hover!==null?`${nearest[0].toFixed(3)}s · ${nearest[1]?.toFixed(3)??'invalid'}`:'0s = candidate end'}</span></div>
  </div>;
});

export const ChargeSignal=memo(function ChargeSignal(){
  const x=(v:number)=>L+(v+12)/17.3*(W-L-R),y=(v:number)=>160-v/1.2e9*125;
  return <div className="charge-signal"><div className="signal-title"><span>Why charge changes the interpretation</span><code>TMIT · electrons per pulse</code></div><svg viewBox="0 0 850 192" role="img" aria-label="Recorded charge: DMPH 502 drops below the 100 million validity threshold while LTUH 250 retains charge near one billion."><rect x={x(-5.3)} y="20" width={x(0)-x(-5.3)} height="140" fill="#59c7e7" opacity=".055"/>{[0,1e9].map(v=><g key={v}><line x1={L} x2={x(0)} y1={y(v)} y2={y(v)} stroke="#243444"/><text x={L-10} y={y(v)+4} textAnchor="end" className="chart-tick">{v===0?'0':'10⁹'}</text></g>)}<line x1={L} x2={x(0)} y1={y(1e8)} y2={y(1e8)} stroke="#c78654" strokeDasharray="4 5"/>{evidenceChargePaths().map((p,i)=><path key={p.channel} d={p.points.filter(v=>v[0]>=-12).map((v,j)=>`${j?'L':'M'}${x(v[0]).toFixed(2)},${y(v[1]).toFixed(2)}`).join('')} fill="none" stroke={i?'#54deec':'#ffb073'} strokeWidth="1.4"/>)}<text x={x(.4)} y={y(1e8)+3} className="chart-label">10⁸ VALIDITY THRESHOLD</text>{[-10,-5,0,5].map(n=><text key={n} x={x(n)} y="185" textAnchor="middle" className="chart-tick">{n>0?'+':''}{n}s</text>)}</svg><div className="charge-legend"><span><i className="orange-dot"/>BPMS:DMPH:502:TMIT</span><span><i className="cyan-dot"/>BPMS:LTUH:250:TMIT</span></div></div>;
});
function evidenceChargePaths(){return data.charge;}
