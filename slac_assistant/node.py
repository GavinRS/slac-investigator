"""Node agent path: answer one node_task with only the node_report JSON (spec §3-4)."""
import json,os

def node_task(prompt):
    try:msg=json.loads(prompt);task=json.loads(msg['payload'])
    except (ValueError,TypeError,KeyError):return None
    if 'src_node_id' in msg and isinstance(task,dict) and task.get('kind')=='node_task':return msg,task

def local_root():
    return os.environ.get('SLAC_NODE_DATA_DIR') or os.environ.get('FLWR_FILESYSTEM_ALLOWED_DIRS','').split(os.pathsep)[0] or None

def reply(grid,msg,payload):
    # flwr 1.39 nodes expose push_reply_message; 1.37 SuperNodes only have push_messages.
    if 'push_reply_message' in {t['name'] for t in grid.tools()}:
        return grid.call({'type':'function_call','name':'push_reply_message','arguments':{'payload':payload},'call_id':'node-reply'})
    m={'dst_node_id':msg['src_node_id'],'payload':payload,'reply_to_message_id':msg['message_id']}
    return grid.call({'type':'function_call','name':'push_messages','arguments':{'messages':[m]},'call_id':'node-reply'})

def run_node(agent,msg,task):
    from .instruments import detect_local_instrument,load_slice
    from .tools import node_summary
    local=detect_local_instrument()
    instrument,role_source,root=(local,'local_data',local_root()) if local else (task['instrument'],'assigned',None)
    _,arrays=load_slice(task['event_id'],instrument,root)
    report=node_summary(task['event_id'],instrument,arrays);report['role_source']=role_source
    # #7 hook: when task['mode']!='smoke', the node model rewrites observation/assessment from report['summary'] here.
    return reply(agent.grid,msg,json.dumps(report))
