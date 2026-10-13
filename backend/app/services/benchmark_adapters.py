"""Stable public-observation adapter boundary. No evaluator state is passed here.

Team adapters implement act(observation, state, condition) -> (action, state, events).
State must be JSON serializable so a trial can continue under the same run ID.
Registration is a trusted server-side Python operation, not a code-upload API.
"""
import copy
import json
from typing import Protocol
import httpx
from ..models.benchmark_study import BenchmarkAction


class AgentAdapter(Protocol):
    version: str
    conditions: set[str]

    def act(self, observation: dict, state: dict, condition: str) -> tuple[BenchmarkAction, dict, list[dict]]: ...


REGISTRY = {}


def register_adapter(name, adapter):
    if name in ('scripted-v2', 'ollama-v1') or name in REGISTRY:
        raise ValueError('Adapter identity already registered or reserved')
    if not getattr(adapter, 'version', None) or not callable(getattr(adapter, 'act', None)) or not getattr(adapter, 'conditions', None):
        raise ValueError('Adapter must expose version, conditions and act')
    REGISTRY[name] = adapter


class ScriptedAdapter:
    version = '2'
    conditions = {'baseline', 'generic_retry', 'idempotent_retry', 'enhanced', 'no_prediction', 'no_diagnosis',
                  'memory_none', 'memory_full_history', 'memory_semantic', 'memory_goal_aware'}

    def act(self, observation, state, condition):
        state = copy.deepcopy(state)
        last = observation.get('last_result') or {}
        if 'contract' in last:
            state['contract'] = last['contract']
        if 'clarified_tag' in last:
            state.setdefault('contract', {})['publish_tag'] = last['clarified_tag']
        if 'distractor' in last and condition == 'memory_semantic':
            state['contract'] = last['distractor']
        contract = state.get('contract', {}) if condition != 'memory_none' else last.get('contract', {})
        tool = observation['next_tool']
        if observation['ambiguous'] and not observation['clarified'] and tool == 'notify' and observation['feedback_policy'] == 'fixture_clarification':
            tool = 'clarify'
        retry = observation['retry_number']
        operation = observation['operation_id']
        if retry and condition in ('generic_retry', 'no_diagnosis'):
            operation += f'-retry-{retry}'
        arguments = {}
        if tool == 'checkpoint':
            a, b = observation['operands']
            arguments['value'] = observation['previous_value'] + (a-b if contract.get('rule') == 'subtract' else a+b)
        if tool == 'notify' and observation['requires_memory']:
            arguments['publish_tag'] = contract.get('publish_tag', 'unknown')
        events = []
        if condition in ('enhanced', 'no_diagnosis'):
            events.append({'kind':'prediction', 'data':{'probability':.8 if observation.get('error') else .1,
                'threshold':.5, 'feature_end_step':observation['step'], 'model_version':'scripted-risk-fixture-v1'}})
        if tool in ('checkpoint', 'notify') and observation['requires_memory']:
            events.append({'kind':'memory', 'data':{'retrieved':copy.deepcopy(contract), 'strategy':condition}})
        if retry:
            events.append({'kind':'intervention', 'data':{'action':'retry', 'policy_version':'scripted-policy-v2',
                'diagnosis':'response_lost_after_commit' if condition not in ('generic_retry','no_diagnosis') and observation.get('error') == 'timeout_after_commit' else 'generic_tool_failure'}})
        return BenchmarkAction(tool=tool, operation_id=operation, arguments=arguments), state, events


def resolve_adapter(manifest):
    if manifest.execution_mode == 'trusted_simulation':
        return ScriptedAdapter()
    if manifest.execution_mode == 'local_ollama':
        return OllamaAdapter(manifest)
    adapter = REGISTRY.get(manifest.adapter_id)
    if adapter is None or adapter.version != manifest.adapter_version:
        raise ValueError('Requested team adapter/version is not registered in this server')
    if not set(manifest.conditions) <= adapter.conditions:
        raise ValueError('Team adapter does not support the requested ablations')
    return copy.deepcopy(adapter)


class OllamaAdapter:
    """Model chooses gateway actions only; generated code is never executed."""
    version = '1'
    conditions = {'baseline', 'memory_none', 'memory_full_history'}

    def __init__(self, manifest):
        self.manifest = manifest

    def describe(self):
        from .ollama_service import ollama_service
        if ollama_service.host not in ('http://127.0.0.1:11434','http://localhost:11434'):
            raise ValueError('The pilot requires a local Ollama server')
        with httpx.Client(timeout=10, trust_env=False) as client:
            tags = client.get(ollama_service.host+'/api/tags')
            tags.raise_for_status()
            version = client.get(ollama_service.host+'/api/version')
            version.raise_for_status()
        model = next((item for item in tags.json().get('models',[]) if item.get('name')==self.manifest.model),None)
        if not model or not model.get('digest'):
            raise ValueError('The selected model is not installed or has no recorded digest')
        return {'model':model['name'],'digest':model['digest'],'size_bytes':model.get('size'),
            'ollama_version':version.json().get('version'),'host':ollama_service.host,
            'think':self.manifest.think,'temperature':0,'context_length':4096}

    def request(self, observation, state, condition):
        history = state.get('history', []) if condition != 'memory_none' else []
        current = json.dumps(observation, ensure_ascii=False)
        messages = [{'role':'system','content':
            'Operate a software-task simulator. Return one JSON tool action only. Allowed tools: read, checkpoint, clarify, apply_patch, run_checks, commit, notify. '
            'Use the given operation_id; reuse it after a lost response. Follow next_tool and original contract. '
            'For checkpoint arguments.value, add the current operands (or subtract if the original rule is subtract) to previous_value. '
            'For notify arguments.publish_tag use the original contract tag when requires_memory is true. '
            'Clarify an ambiguous tag before notifying. apply_patch applies a built-in trusted repair; never output code. '
            'Schema: {"tool":"read","operation_id":"given-id","arguments":{}}.'},
            *history, {'role':'user','content':current}]
        return messages

    def complete(self, messages, condition, state, timeout, output_limit):
        from .ollama_service import ollama_service
        # Local pilot only. Never send this benchmark to a cloud/remote endpoint.
        if ollama_service.host not in ('http://127.0.0.1:11434', 'http://localhost:11434'):
            raise ValueError('The approved pilot requires the local Ollama endpoint')
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.post(ollama_service.host+'/api/chat', json={
                'model':self.manifest.model, 'messages':messages, 'stream':False, 'think':self.manifest.think,
                'format':BenchmarkAction.model_json_schema(), 'options':{'temperature':0,
                    'seed':self.manifest.seed, 'num_predict':output_limit, 'num_ctx':4096}})
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                # Preserve the local server's resource/error diagnosis without another request.
                try:
                    detail = response.json().get('error', '')
                except (ValueError, AttributeError):
                    detail = ''
                raise RuntimeError(f'Ollama HTTP {response.status_code}: {str(detail)[:1000]}') from exc
            data = response.json()
        usage = (data.get('prompt_eval_count'), data.get('eval_count'))
        if any(type(n) is not int or n < 0 for n in usage):
            raise ValueError('Ollama response omitted valid token usage; reservation retained')
        if data.get('done') is not True:
            raise ValueError('Ollama returned an incomplete response; reservation retained')
        content = data.get('message', {}).get('content', '')
        new_state = {'history':[*messages[1:], {'role':'assistant','content':content}]} if condition != 'memory_none' else {}
        # Parse the action only AFTER the runner records actual usage, even if JSON is invalid.
        return content, new_state, {'input_tokens':usage[0], 'output_tokens':usage[1],
            'model':self.manifest.model, 'model_duration_ns':data.get('total_duration'), 'done_reason':data.get('done_reason')}
