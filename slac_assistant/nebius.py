"""Opt-in, narrow Chat Completions adapter; never rewrites Flower provider settings.

The responses-shaped facade is an application interface only. Every inference
request on this path is POST /v1/chat/completions, made inside the AgentApp.
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from types import SimpleNamespace
from openai import OpenAI, OpenAIError

NEBIUS_BASE_URL = 'https://api.tokenfactory.us-central1.nebius.com/v1/'

class ProviderConfigurationError(RuntimeError):
    pass

class ProviderRequestError(RuntimeError):
    pass


def require_nebius_environment(env=None):
    env = os.environ if env is None else env
    if env.get('NEBIUS_EVENT_CREDITS_CONFIRMED') != '1':
        raise ProviderConfigurationError('Event credit coverage must be confirmed before Nebius requests.')
    missing = [key for key in ('NEBIUS_API_KEY', 'NEBIUS_MODEL') if not env.get(key, '').strip()]
    if missing:
        raise ProviderConfigurationError('Missing environment variables: ' + ', '.join(missing))
    return env['NEBIUS_API_KEY'].strip(), env['NEBIUS_MODEL'].strip()


def safe_request(call, **kwargs):
    try:
        return call(**kwargs)
    except OpenAIError as exc:
        # Provider error bodies may echo inputs; never put them in Flower logs/UI.
        status = getattr(exc, 'status_code', None)
        hint = {401: 'authentication failed', 403: 'access denied', 404: 'route or model unavailable',
                429: 'rate limit or quota exceeded'}.get(status, 'request failed')
        raise ProviderRequestError(f'Nebius {hint}; HTTP status {status or "unavailable"}. No automatic retry.') from None


@dataclass
class OutputItem:
    payload: dict
    def __getattr__(self, key):
        try: return self.payload[key]
        except KeyError: raise AttributeError(key) from None
    def model_dump(self, **kwargs):
        return dict(self.payload)


def chat_messages(items, instructions):
    """Translate only the text/function subset our investigators actually use."""
    messages = [{'role': 'system', 'content': instructions}]
    if isinstance(items, str): items = [{'role': 'user', 'content': items}]
    pending = None
    outstanding = set()
    seen = set()
    def flush():
        nonlocal pending
        if pending is not None:
            messages.append(pending)
            pending = None
    for item in items:
        kind = item.get('type')
        if kind == 'function_call':
            call_id = item['call_id']
            if not call_id or call_id in seen: raise ValueError('Duplicate or empty function call ID')
            seen.add(call_id); outstanding.add(call_id)
            if pending is None: pending = {'role': 'assistant', 'content': None, 'tool_calls': []}
            pending.setdefault('tool_calls', []).append({'id': call_id, 'type': 'function',
                'function': {'name': item['name'], 'arguments': item['arguments']}})
        elif kind == 'function_call_output':
            flush()
            if item['call_id'] not in outstanding: raise ValueError('Unmatched or duplicate function result')
            outstanding.remove(item['call_id'])
            messages.append({'role': 'tool', 'tool_call_id': item['call_id'], 'content': item['output']})
        elif item.get('role') in ('user', 'assistant') and kind in (None, 'message'):
            if outstanding: raise ValueError('Missing tool results before next message')
            flush()
            content = item.get('content', '')
            if isinstance(content, list):
                if any(part.get('type') not in ('input_text', 'output_text') for part in content):
                    raise ValueError('Only text content is supported')
                content = ''.join(part['text'] for part in content)
            if not isinstance(content, str): raise ValueError('Only text content is supported')
            message = {'role': item['role'], 'content': content}
            if item['role'] == 'assistant': pending = message
            else: messages.append(message)
        else:
            raise ValueError('Unsupported history item; no silent protocol conversion')
    flush()
    if outstanding: raise ValueError('Missing tool results')
    return messages


class NebiusChatAdapter:
    """No fallback, endpoint probing, GPU provisioning, or provider config mutation."""
    provider = 'nebius-chat'
    def __init__(self, sdk, model):
        self.sdk = sdk
        self.model = model
        self.responses = self  # Existing application's narrow call interface.
        self.model_verified = False

    def verify_model(self):
        if not self.model_verified:
            listing = safe_request(self.sdk.models.list)
            if self.model not in {item.id for item in listing.data}:
                raise ProviderConfigurationError('NEBIUS_MODEL was not found in the authenticated regional model list.')
            self.model_verified = True
        return self.model

    def create(self, *, model, input, instructions, tools, max_output_tokens, tool_choice=None):
        if model != self.model: raise ProviderConfigurationError('Requested model must match NEBIUS_MODEL.')
        messages = chat_messages(input, instructions)
        names = set()
        chat_tools = []
        for tool in tools:
            if tool.get('type') != 'function': raise ValueError('Only function tools are supported')
            if tool['name'] in names: raise ValueError('Duplicate tool name')
            names.add(tool['name'])
            chat_tools.append({'type': 'function', 'function': {k: tool[k] for k in ('name', 'description', 'parameters') if k in tool}})
        args = dict(model=self.model, messages=messages, max_tokens=max_output_tokens, stream=False)
        if chat_tools: args['tools'] = chat_tools
        if tool_choice is not None:
            if tool_choice not in names: raise ValueError('Forced tool was not advertised')
            args['tool_choice'] = {'type': 'function', 'function': {'name': tool_choice}}
        self.verify_model()
        completion = safe_request(self.sdk.chat.completions.create, **args)
        if len(completion.choices) != 1: raise ProviderRequestError('Expected one chat completion choice.')
        choice = completion.choices[0]
        if choice.finish_reason not in ('stop', 'tool_calls'):
            raise ProviderRequestError('Nebius response was truncated, filtered, or incomplete; no finding accepted.')
        message = choice.message
        if getattr(message, 'refusal', None): raise ProviderRequestError('Nebius declined the request.')
        text = message.content or ''
        # Separate reasoning fields are never copied into history or visible events.
        if any(marker in text.lower() for marker in ('<think>', '</think>', '<analysis>', '</analysis>')):
            raise ProviderRequestError('Unexpected reasoning markup in visible output; no finding accepted.')
        output = []
        if text:
            output.append(OutputItem({'type': 'message', 'role': 'assistant',
                'content': [{'type': 'output_text', 'text': text}]}))
        call_ids = set()
        for call in message.tool_calls or []:
            if call.type != 'function' or call.function.name not in names:
                raise ProviderRequestError('Model requested an unadvertised tool.')
            if not call.id or call.id in call_ids: raise ProviderRequestError('Invalid tool call IDs.')
            call_ids.add(call.id)
            output.append(OutputItem({'type': 'function_call', 'call_id': call.id,
                'name': call.function.name, 'arguments': call.function.arguments}))
        if not output: raise ProviderRequestError('Model returned no visible text or function calls.')
        usage = completion.usage
        return SimpleNamespace(status='completed', output=output, output_text=text,
            usage=None if usage is None else SimpleNamespace(input_tokens=usage.prompt_tokens, output_tokens=usage.completion_tokens))


def create_model_client(provider, requested_model=None, default_model='openai/gpt-5.6-sol', env=None):
    env = os.environ if env is None else env
    if provider == 'flower':
        # Preserve the existing runtime route and credential variables exactly.
        return OpenAI(base_url=env['FLWR_RUNTIME_BASE_URL'], api_key=env['FLWR_RUNTIME_API_KEY'],
                      max_retries=0, timeout=120), requested_model or default_model
    if provider != 'nebius-chat': raise ProviderConfigurationError('Unknown model provider path.')
    token, model = require_nebius_environment(env)
    if requested_model is not None and requested_model != model:
        raise ProviderConfigurationError('Requested model must match NEBIUS_MODEL; no default model substitution.')
    sdk = OpenAI(base_url=NEBIUS_BASE_URL, api_key=token, max_retries=0, timeout=120)
    return NebiusChatAdapter(sdk, model), model
