import asyncio
import copy
import json

import pytest
from jsonschema import Draft202012Validator
from the_framework.agent import Agent, Artifact, Session
from the_harness.plugins.artifacts.agent import HarnessArtifacts

KINDS = ('markdown', 'code', 'table', 'chart', 'timeline')


def test_catalogue_examples_validate_and_survive_session_replay(tmp_path):
    extension = HarnessArtifacts(Agent(client=object()))
    catalogue = extension.supported_artifacts()
    assert set(catalogue) == {'image', 'audio', 'file', *KINDS}
    session = Session.open(tmp_path / 'session.json')
    for kind in KINDS:
        entry = catalogue[kind]
        Draft202012Validator.check_schema(entry['payload_schema'])
        Draft202012Validator(entry['payload_schema']).validate(entry['example'])
        artifact = asyncio.run(extension.show_artifact(kind, entry['example']))
        assert isinstance(artifact, Artifact)
        assert artifact.kind == kind
        session.append(artifact)
    restored = Session.open(session.path)
    assert [item.kind for item in restored.history] == list(KINDS)
    assert json.loads(json.dumps(restored.history)) == json.loads(json.dumps(session.history))


@pytest.mark.parametrize('kind,payload', [
    ('markdown', {}), ('markdown', {'content': 42}),
    ('markdown', {'content': 'x' * 100001}),
    ('code', {'content': 'ok', 'filename': 'x' * 201}),
    ('table', {'columns': ['A', 'A'], 'rows': []}),
    ('table', {'columns': [' '], 'rows': []}),
    ('table', {'columns': ['A'], 'rows': [[1, 2]]}),
    ('table', {'columns': ['A'], 'rows': [[{}]]}),
    ('table', {'columns': ['A'], 'rows': [[float('nan')]]}),
    ('table', {'columns': ['A'], 'rows': [[1]] * 2001}),
    ('chart', {'labels': ['a'], 'series': [{'name': 'A', 'values': []}]}),
    ('chart', {'labels': ['a'], 'series': [{'name': 'A', 'values': [float('inf')]}]}),
    ('chart', {'labels': ['a'], 'series': [{'name': 'A', 'values': [True]}]}),
    ('chart', {'labels': [], 'series': []}),
    ('timeline', {'entries': []}),
    ('timeline', {'entries': [{'label': 'a', 'title': 'b', 'execute': True}]}),
    ('timeline', {'entries': [{'label': 'a', 'title': 'b', 'detail': 'x' * 2001}]}),
])
def test_invalid_payloads_are_rejected(kind, payload):
    extension = HarnessArtifacts(Agent(client=object()))
    with pytest.raises((ValueError, TypeError, KeyError)):
        asyncio.run(extension.show_artifact(kind, payload))


@pytest.mark.parametrize('kind', KINDS)
def test_shared_bounds_and_unknown_fields(kind):
    extension = HarnessArtifacts(Agent(client=object()))
    example = extension.supported_artifacts()[kind]['example']
    for extra in ({'title': 'x' * 301}, {'description': 'x' * 2001}, {'execute': True}):
        with pytest.raises((ValueError, TypeError, KeyError)):
            asyncio.run(extension.show_artifact(kind, {**copy.deepcopy(example), **extra}))
    with pytest.raises((ValueError, TypeError, KeyError)):
        asyncio.run(extension.show_artifact('markdown', {'content': '😀' * 100000}))
