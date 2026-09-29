"""Flower node envelope and reply transport; assessment lives in node_agent."""
import json


def node_task(prompt):
    try:
        message=json.loads(prompt)
        task=json.loads(message['payload'])
    except (ValueError,TypeError,KeyError):
        return None
    if isinstance(message,dict) and 'src_node_id' in message and isinstance(task,dict) and task.get('kind')=='node_task':
        return message,task
    return None


def local_root():
    from .instruments import local_data_dir
    root=local_data_dir()
    return str(root) if root is not None else None


def reply(grid,msg,payload):
    """Use 1.39's bound reply, or explicitly correlated older Grid transport."""
    if 'push_reply_message' in {tool['name'] for tool in grid.tools()}:
        return grid.call(dict(type='function_call',name='push_reply_message',arguments={'payload':payload},call_id='node-reply'))
    if not msg or not msg.get('message_id') or not msg.get('src_node_id'):
        raise ValueError('Reply transport requires the received message identity')
    message=dict(dst_node_id=str(msg['src_node_id']),payload=payload,reply_to_message_id=msg['message_id'])
    return grid.call(dict(type='function_call',name='push_messages',arguments={'messages':[message]},call_id='node-reply'))


def run_node(agent,msg,task,client=None,model=None):
    """Single shared discovery/validated assessment path for every node task."""
    from .node_agent import reply_to_node
    return reply_to_node(agent,task,client,model,message=msg)
