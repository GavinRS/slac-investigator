import {escapeHTML as h,plotPath} from './replay.js';
const colors=['#138993','#d49440','#686fb0','#c56e73'];
export function plot(event,focus,series,kind){
  const W=600,H=155,left=47,right=13,top=11,bottom=27;
  const end=event.candidate_interval_s[0];
  const extent=focus?[end-.3,.5]:[-18,6];
  const points=series.flatMap(s=>s.points.filter(p=>p[0]>=extent[0]&&p[0]<=extent[1]&&p[1]!==null));
  let min=points.length?Math.min(...points.map(p=>p[1])):0,max=points.length?Math.max(...points.map(p=>p[1])):1;
  if(kind==='rf'){min=Math.min(0,min);max=Math.max(max,1);}
  if(kind==='charge')min=0;
  let pad=(max-min||1)*.13;min-=kind==='position'?pad:0;max+=pad;
  const x=t=>left+(t-extent[0])/(extent[1]-extent[0])*(W-left-right),y=v=>H-bottom-(v-min)/(max-min)*(H-top-bottom);
  const fmt=v=>kind==='charge'?(v/1e9).toFixed(1):Math.abs(v)>10?v.toFixed(0):v.toFixed(1);
  const ticks=focus?[end, end/2,0]:[-15,-10,-5,0,5];
  const grid=[0,.5,1].map(frac=>{const value=min+(max-min)*frac;return `<line x1="${left}" x2="${W-right}" y1="${y(value)}" y2="${y(value)}" stroke="#e7eef1"/><text x="${left-8}" y="${y(value)+3}" text-anchor="end">${fmt(value)}</text>`;}).join('');
  const title=kind==='rf'?'RF station amplitude':kind==='position'?'Beam position · charge-qualified':'Beam charge';
  const unit=kind==='rf'?'AMPL · source units':kind==='position'?'Source-scaled position':'TMIT · ×10⁹ source units';
  const shadeStart=Math.max(extent[0],end),shadeEnd=Math.min(extent[1],0);
  return `<div class="plot"><div class="plot-title"><strong>${title}</strong><span>${unit}</span></div><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${h(title)} against recorded time. Candidate interval shaded. No timestamps shifted." data-chart="${kind}" data-min="${extent[0]}" data-max="${extent[1]}"><title>${h(title)}; no timestamps shifted</title><defs><clipPath id="clip-${kind}"><rect x="${left}" y="${top}" width="${W-left-right}" height="${H-top-bottom}"/></clipPath></defs><rect x="${x(shadeStart)}" y="${top}" width="${Math.max(0,x(shadeEnd)-x(shadeStart))}" height="${H-top-bottom}" fill="#f7eddc"/>${grid}<line x1="${x(0)}" x2="${x(0)}" y1="${top}" y2="${H-bottom}" stroke="#c8a565" stroke-dasharray="3 4"/>${ticks.map(t=>`<text x="${x(t)}" y="${H-10}" text-anchor="middle">${Number(t.toFixed(1))}s</text>`).join('')}<g clip-path="url(#clip-${kind})">${series.map((s,i)=>`<path d="${plotPath(s.points,x,y,kind==='rf')}" fill="none" stroke="${kind==='rf'?'#157d87':colors[i%4]}" stroke-width="${kind==='rf'?1.8:1.1}" vector-effect="non-scaling-stroke"/>`).join('')}</g><line class="cursor" y1="${top}" y2="${H-bottom}" stroke="#526f81" stroke-dasharray="2 3" visibility="hidden"/><text class="cursor-text" y="${top+9}" x="${W-right-3}" text-anchor="end"></text></svg><div class="legend">${series.map((s,i)=>`<span><i style="background:${kind==='rf'?'#157d87':colors[i%4]}"></i>${h(s.channel.replace('BPMS:',''))}</span>`).join('')}</div></div>`;
}
