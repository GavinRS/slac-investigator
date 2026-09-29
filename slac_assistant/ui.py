"""Operator replay interface. Investigations are submitted to Flower, never called in-process."""
import os
os.environ.setdefault('MPLBACKEND','Agg')
os.environ.setdefault('MPLCONFIGDIR','/tmp/slac-mpl')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/slac-cache')
import json
import matplotlib.pyplot as plt
import streamlit as st
from slac_assistant.data import event_ids,load_event,plot_event
from slac_assistant.runtime import run_flower
st.set_page_config(page_title='RF Investigation | SLAC replay',page_icon='🔎',layout='wide')
st.markdown('''<style>.block-container{padding-top:4rem;max-width:1400px}h1{letter-spacing:-.04em}div[data-testid="stMetric"]{background:#edf5f6;padding:1rem;border-radius:8px}</style>''',unsafe_allow_html=True)
st.caption('FLOWER AGENTAPP • HUMAN-SUPERVISED INVESTIGATION • ARCHIVED DATA')
st.title('RF fault investigation')
st.write('Inspect an RF candidate, compare beam evidence, and review the limits of the assessment.')
with st.sidebar:
    st.subheader('Investigation setup')
    event=st.selectbox('Selected event',event_ids())
    mode_name=st.selectbox('Investigation mode',['Specialist collaboration','Single-agent baseline','Deterministic runtime check'])
    mode={'Specialist collaboration':'collaborative','Single-agent baseline':'baseline','Deterministic runtime check':'smoke'}[mode_name]
    model=st.text_input('Model',value=os.environ.get('INVESTIGATOR_MODEL','openai/gpt-5.6-sol'))
    st.caption('Model modes require a provider configured on the local Flower SuperLink.')
    start=st.button('Start investigation',type='primary',use_container_width=True)
    if mode=='smoke':st.warning('Software check only. No model or specialist agents are invoked.')
    st.divider();st.caption('Replay only. No machine-control tools. Operator review is required for any real-world interpretation.')
m,_=load_event(event)
key=(event,mode,model)
if st.session_state.get('selection')!=key:
    st.session_state.update(selection=key,report=None,series=None,events=[],questions=[])
a,b,c=st.columns(3)
a.metric('Event',event);b.metric('Candidate station',m['station'].replace('KLYS:',''));c.metric('Measured source','SLAC')
with st.expander('Data provenance and limitations',expanded=False):
    st.markdown(f"[Public dataset]({m['source_url']}) · HDF5 group `{m['hdf5_group']}`")
    st.write(m['timestamp_unit']);st.write(m['timing']);st.write(m['license'])
    for limit in m['limitations']:st.write('• '+limit)
    st.caption('Four deliberately selected demonstration cases. Ground-truth labels are excluded from model inputs and the Flower bundle.')
fig=plot_event(event);st.pyplot(fig,width='stretch');plt.close(fig)
st.caption('Shaded area: published candidate interval. Lines retain recorded timestamps; low-charge position readings are masked. RF steps hold only previously observed values.')
left,right=st.columns([1.2,1])
with left:
    st.subheader('Findings and tool activity')
    activity=st.container()
with right:
    st.subheader('Current assessment')
    assessment_box=st.container()

def show_event(e,container):
    with container:
        if e['kind']=='delegation':st.info(f"{e['agent'].title()} → {e['to']}: {e['question']}")
        elif e['kind']=='tool_request':st.caption(f"{e['agent']} requests {e['analysis']}")
        elif e['kind']=='finding':
            f=e['finding']
            with st.expander(f"{f['finding_id']} · {f['agent']} · {f['assessment']}",expanded=True):
                st.write(f['observation']);st.caption('Evidence: '+', '.join(f['tool_result_refs']))
                if f.get('requested_next_check'):st.write('Next check: '+f['requested_next_check'])
                with st.expander('Structured finding'):st.json(f)

def execute(question=''):
    st.session_state.events=[]
    try:
        with st.spinner('Flower is executing the investigation…'):
            def receive(e):
                st.session_state.events.append(e);show_event(e,activity)
            report,series=run_flower(event,mode,question,model,st.session_state.series,on_event=receive)
        st.session_state.report=report;st.session_state.series=series
        if question:st.session_state.questions.append(question)
    except Exception as exc:
        st.error(f'Investigation did not complete: {exc}')
        st.info('Check the local Flower SuperLink and provider configuration. No final diagnosis was accepted.')
        st.session_state.report=None
    st.rerun()

if start:execute()
for e in st.session_state.events:show_event(e,activity)
report=st.session_state.report
with assessment_box:
    if report:
        f=report['final'];st.subheader(f['assessment'].replace('_',' ').title());st.write(f['observation'])
        if report['mode']=='smoke':st.warning('Deterministic runtime check. This is not an agent-generated assessment.')
        st.write('**Limitations**')
        for limitation in f['data_limitations']:st.write('• '+limitation)
        st.caption(f"Flower run {report['flower_run_id']} · {report['metrics']['model_calls']} model calls · {report['metrics']['tool_calls']} tool calls · {report['wall_latency_s']} s end-to-end")
        st.download_button('Download evidence report',json.dumps(report,indent=2),f'{event}-{mode}.json','application/json')
    else:st.info('Select an event and start an investigation. A supported insufficient-evidence outcome is valid.')
if report:
    st.subheader('Evidence ledger')
    for result in report['evidence']:
        with st.expander(f"{result['ref']} · {result['analysis']} · {result['event_id']}"):st.json(result)
    if mode!='smoke':
        with st.form('human_followup'):
            question=st.text_input('Ask a follow-up question',placeholder='Could low charge explain the position readings?')
            submit=st.form_submit_button('Ask investigators')
        if submit and question.strip():execute(question.strip())
    else:st.caption('Natural-language follow-up is available in model modes. The deterministic check only verifies data and runtime behavior.')
    for question in st.session_state.questions:st.caption('Operator question: '+question)
