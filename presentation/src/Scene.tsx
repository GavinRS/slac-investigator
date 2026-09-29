import { Component, Suspense, useMemo, useRef, type ReactNode } from 'react';
import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber';
import * as THREE from 'three';

const cyan = '#4de7ff';
const violet = '#9c81ff';
const mix = THREE.MathUtils.lerp;
const clamp = THREE.MathUtils.clamp;
const smooth = (x:number) => { const t=clamp(x,0,1); return t*t*(3-2*t); };

function ribbon(index:number) {
  const vertices:number[]=[], indices:number[]=[];
  const n=160, turns=3.7 + (index%3)*.3;
  for(let i=0;i<=n;i++) {
    const t=i/n, a=t*Math.PI*2*turns;
    for(const edge of [-1,1]) {
      const y=(t-.5)*3.7+edge*.21;
      vertices.push(Math.cos(a)*.49,y,Math.sin(a)*.49);
    }
    if(i<n) { const j=i*2; indices.push(j,j+1,j+2,j+1,j+3,j+2); }
  }
  const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));g.setIndex(indices);g.computeVertexNormals(); return g;
}
const helixPositions: [number,number,number][] = [[-1.65,.15,.2],[-.5,.25,-.8],[.7,-.05,-.6],[1.6,.0,.6],[.45,-.2,1.1],[-.8,-.4,1.0],[-.2,.7,.15]];
function Protein({progress,reduced}:{progress:number;reduced:boolean}) {
  const mobile=useThree(state=>state.size.width<700);
  const group=useRef<THREE.Group>(null), spin=useRef(0), drag=useRef<{x:number;rotation:number}|null>(null);
  const geometries=useMemo(()=>helixPositions.map((_,i)=>ribbon(i)),[]);
  const connectors=useMemo(()=>helixPositions.slice(0,-1).map((p,i)=>{
    const q=helixPositions[i+1],sign=i%2? -1:1;
    return new THREE.TubeGeometry(new THREE.CatmullRomCurve3([new THREE.Vector3(p[0],p[1]+sign*1.8,p[2]),new THREE.Vector3((p[0]+q[0])/2,sign*2.5,(p[2]+q[2])/2+.4),new THREE.Vector3(q[0],q[1]+sign*1.8,q[2])]),32,.045,7,false);
  }),[]);
  useFrame((_,dt)=> { if(group.current) { if(!drag.current&&!reduced)spin.current+=dt*.09; group.current.rotation.y=spin.current; group.current.rotation.z=-.2; const s=1-smooth(progress/.85);group.current.scale.setScalar(s*(mobile?.5:1));group.current.visible=s>.01; } });
  function down(e:ThreeEvent<PointerEvent>) {e.stopPropagation();drag.current={x:e.clientX,rotation:spin.current};(e.target as HTMLElement).setPointerCapture?.(e.pointerId);}
  return <group ref={group} position={mobile?[1.4,-1.7,0]:[3.2,0,0]} onPointerDown={down} onPointerUp={()=>drag.current=null} onPointerCancel={()=>drag.current=null} onPointerMove={e=>{if(drag.current)spin.current=drag.current.rotation+(e.clientX-drag.current.x)*.012;}}>
    {helixPositions.map((p,i)=><mesh key={i} position={p} rotation={[i%2?.23:-.2,0,(i-3)*.13]} geometry={geometries[i]}><meshPhysicalMaterial color={i%3?'#27a8f9':'#56dfff'} metalness={.35} roughness={.25} clearcoat={.7} side={THREE.DoubleSide}/></mesh>)}
    {connectors.map((g,i)=><mesh geometry={g} key={i}><meshStandardMaterial color="#57d3ff" metalness={.25} roughness={.3}/></mesh>)}
  </group>;
}
function Machine({progress,reduced,agentStep}:{progress:number;reduced:boolean;agentStep:number}) {
  const group=useRef<THREE.Group>(null), electron=useRef<THREE.Mesh>(null), photon=useRef<THREE.Mesh>(null), alert=useRef<THREE.Mesh>(null);
  const nodes=useRef<THREE.Group>(null);
  useFrame(({clock})=>{
    const t=clock.elapsedTime;
    if(group.current){const s=smooth((progress-.4)/.65);group.current.scale.setScalar(s);group.current.visible=s>.01;}
    const disturbed=progress>2.15&&progress<3;
    if(electron.current){electron.current.position.x=reduced?-3: -16+(t*5)%26;electron.current.scale.setScalar(disturbed&&electron.current.position.x>0?.4:1);}
    if(photon.current){photon.current.position.x=reduced?14: 10+(t*6)%9;photon.current.scale.setScalar(disturbed?.45:1);}
    if(alert.current){alert.current.visible=progress>2.2;const mat=alert.current.material as THREE.MeshBasicMaterial;mat.opacity=reduced?.6:.3+Math.sin(t*2.5)*.18;}
    if(nodes.current){nodes.current.visible=false;}
  });
  const segments=Array.from({length:13},(_,i)=>-15+i*1.9);
  return <group ref={group} position={[0,-1.2,0]}>
    <mesh position={[0,-2.2,0]} rotation={[-Math.PI/2,0,0]}><planeGeometry args={[80,45]}/><meshStandardMaterial color="#070f1c" roughness={.6} metalness={.3}/></mesh>
    {segments.map((x,i)=><group key={i} position={[x,0,0]}>
      <mesh rotation={[0,0,Math.PI/2]}><cylinderGeometry args={[.61,.61,1.62,24,1,true,Math.PI/5,Math.PI*1.4]}/><meshStandardMaterial color={i===8&&progress>2.2?'#b97d4f':'#697b8e'} roughness={.3} metalness={.88} side={THREE.DoubleSide}/></mesh>
      {[-.76,.76].map(v=><mesh key={v} position={[v,0,0]} rotation={[0,Math.PI/2,0]}><torusGeometry args={[.64,.075,8,28]}/><meshStandardMaterial color="#8b9aac" roughness={.28} metalness={.8}/></mesh>)}
      <mesh position={[0,-1.2,0]}><boxGeometry args={[.16,1.6,.2]}/><meshStandardMaterial color="#344457" metalness={.8} roughness={.5}/></mesh>
      <mesh position={[0,-1.9,0]}><boxGeometry args={[.75,.12,1.4]}/><meshStandardMaterial color="#253448"/></mesh>
      <mesh position={[0,.84,-.18]}><boxGeometry args={[1.32,.18,.3]}/><meshStandardMaterial color="#8a6041" metalness={.6} roughness={.45}/></mesh>
      {i%2===0&&<mesh position={[0,1.2,-.55]}><boxGeometry args={[.3,.55,.5]}/><meshStandardMaterial color="#425976" roughness={.4} metalness={.7}/></mesh>}
    </group>)}
    <mesh position={[-3,0,0]} rotation={[0,0,Math.PI/2]}><cylinderGeometry args={[.035,.035,26,8]}/><meshBasicMaterial color={cyan}/></mesh>
    <mesh ref={electron}><sphereGeometry args={[.14,12,12]}/><meshBasicMaterial color="#edfcff"/></mesh>
    {Array.from({length:10},(_,i)=><group key={i} position={[10+i*.42,0,0]}><mesh position={[0,.4,0]}><boxGeometry args={[.28,.3,.8]}/><meshStandardMaterial color={i%2?'#a386e6':'#426fae'} metalness={.55} roughness={.35}/></mesh><mesh position={[0,-.4,0]}><boxGeometry args={[.28,.3,.8]}/><meshStandardMaterial color={i%2?'#426fae':'#a386e6'} metalness={.55} roughness={.35}/></mesh></group>)}
    <mesh position={[14.5,0,0]} rotation={[0,0,Math.PI/2]}><cylinderGeometry args={[.025,.025,9,8]}/><meshBasicMaterial color={violet}/></mesh>
    <mesh ref={photon}><sphereGeometry args={[.12,12,12]}/><meshBasicMaterial color="#d3bbff"/></mesh>
    <mesh position={[18.8,0,0]}><octahedronGeometry args={[.45]}/><meshPhysicalMaterial color="#bfefff" transparent opacity={.8} metalness={.1} roughness={.05}/></mesh>
    <mesh ref={alert} position={[.2,0,0]} rotation={[0,Math.PI/2,0]}><torusGeometry args={[1.2,.035,8,48]}/><meshBasicMaterial color="#ffab6d" transparent opacity={.6}/></mesh>
    {Array.from({length:15},(_,i)=><mesh key={i} position={[-17+i*2.7,0,-2.5]} rotation={[0,Math.PI/2,0]}><torusGeometry args={[3.2,.055,6,24,Math.PI]}/><meshStandardMaterial color="#1d3046" metalness={.5} roughness={.6}/></mesh>)}
    <group ref={nodes}>
      {[[-5,3,0],[4,3,0],[.1,6,0]].map((p,i)=><group key={i} position={p as [number,number,number]}><mesh><icosahedronGeometry args={[.32,1]}/><meshStandardMaterial color={i===2?violet:cyan} emissive={i===2?violet:cyan} emissiveIntensity={1.3} wireframe/></mesh><mesh rotation={[Math.PI/2,0,0]}><torusGeometry args={[.55,.018,6,32]}/><meshBasicMaterial color={i===2?violet:cyan}/></mesh></group>)}
    </group>
  </group>;
}
function World({progress,reduced,agentStep}:{progress:number;reduced:boolean;agentStep:number}) {
  const mobile=useThree(state=>state.size.width<700);
  const aim=useRef(new THREE.Vector3(1.7,0,0));
  const cameraStates=[{p:[0,0,13],t:[1.4,0,0]},{p:[1,4.5,31],t:[1,0,0]},{p:[17,12,26],t:[0,-.2,0]},{p:[8,7,22],t:[0,.8,0]},{p:[8,9,26],t:[0,1,0]},{p:[8,9,26],t:[0,1,0]},{p:[2,7,33],t:[1,0,0]}];
  const v=new THREE.Vector3();
  useFrame(({camera},dt)=>{const n=clamp(progress,0,6),i=Math.floor(n),a=smooth(n-i),s=cameraStates[i],e=cameraStates[Math.min(i+1,6)],distance=mobile?1+smooth(n)*1.9:1;v.set(mix(s.p[0],e.p[0],a),mix(s.p[1],e.p[1],a),mix(s.p[2],e.p[2],a)*distance);camera.position.lerp(v,reduced?1:1-Math.exp(-dt*5));v.set(mix(s.t[0],e.t[0],a),mix(s.t[1],e.t[1],a),mix(s.t[2],e.t[2],a));aim.current.lerp(v,reduced?1:1-Math.exp(-dt*5));camera.lookAt(aim.current);});
  return <><color attach="background" args={['#050a14']}/><fog attach="fog" args={['#050a14',32,80]}/><ambientLight intensity={.85}/><directionalLight position={[3,9,8]} intensity={3.5} color="#b6dbff"/><pointLight position={[-5,3,5]} color={cyan} intensity={35} distance={30}/><pointLight position={[8,4,0]} color={violet} intensity={30} distance={25}/><Protein progress={progress} reduced={reduced}/><Machine progress={progress} reduced={reduced} agentStep={agentStep}/></>;
}
class CanvasBoundary extends Component<{children:ReactNode},{failed:boolean}> {
  state={failed:false};static getDerivedStateFromError(){return {failed:true};}
  render(){return this.state.failed?<div className="webgl-fallback"><span>BEAMLINE / SLAC</span><div className="fallback-beam"/>Interactive 3D unavailable. All evidence and controls remain available below.</div>:this.props.children;}
}
export default function Scene(props:{progress:number;reduced:boolean;agentStep:number}) {return <CanvasBoundary><Canvas dpr={[1,1.75]} camera={{position:[0,0,13],fov:43}} gl={{antialias:true,alpha:false,powerPreference:'high-performance'}} fallback={<div className="webgl-fallback">3D unavailable. Continue to explore the evidence below.</div>}><Suspense fallback={null}><World {...props}/></Suspense></Canvas></CanvasBoundary>;}
