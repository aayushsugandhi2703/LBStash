"""Build the importable iPhone Shortcut "Ledger Capture" (apps/web/public/ledger-capture.shortcut).

    python3 scripts/make-shortcut.py [--url http://192.168.1.33:8088]                 # generic file: asks for address and token
    python3 scripts/make-shortcut.py --url http://192.168.1.33:8088 --token ledg_live_... --out ~/Downloads/ledger-capture.shortcut
                                                                                        # personal file: nothing to type

What the Shortcut does when a Message automation runs it (input = the message): POST {text, receivedAt, nonce} to
<server>/api/ingest/message with the bearer token. The filtering is done by the automation's Message Contains word
(for example your bank's tag, -BOB); the server drops OTPs, promos and anything that is not a payment.

iOS only imports SIGNED shortcuts, and only macOS can sign them, so run this on a Mac and commit the result.
Personal automations cannot be shared as files; the user adds the 3-tap automation that runs this Shortcut.
"""

from __future__ import annotations

import plistlib
import subprocess
import sys
import uuid
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / 'apps/web/public/ledger-capture.shortcut'
OBJ = '￼'  # the placeholder character a variable replaces inside text


def uid() -> str:
    return str(uuid.uuid4()).upper()


def out_ref(u: str, name: str) -> dict:
    return {'Type': 'ActionOutput', 'OutputUUID': u, 'OutputName': name}


def text_token(parts: list) -> dict:
    """Text made of literal strings and variables: ['abc', ref, '/x'] -> a WFTextTokenString."""
    s, att, i = '', {}, 0
    for p in parts:
        if isinstance(p, str):
            s += p
            i += len(p)
        else:
            s += OBJ
            att[f'{{{i}, 1}}'] = p
            i += 1
    return {'Value': {'string': s, 'attachmentsByRange': att}, 'WFSerializationType': 'WFTextTokenString'}


def attach(ref: dict) -> dict:
    return {'Value': ref, 'WFSerializationType': 'WFTextTokenAttachment'}


def field(key: str, parts: list) -> dict:
    return {'WFItemType': 0, 'WFKey': text_token([key]), 'WFValue': text_token(parts)}


def dictionary(items: list) -> dict:
    return {'Value': {'WFDictionaryFieldValueItems': items}, 'WFSerializationType': 'WFDictionaryFieldValue'}


def current_date(fmt: str) -> dict:
    """The Current Date variable with a date format, written the way the Shortcuts app writes it."""
    if fmt == 'iso':
        ag = {'Type': 'WFDateFormatVariableAggrandizement', 'WFDateFormatStyle': 'ISO 8601', 'WFISO8601IncludeTime': True}
    else:
        ag = {'Type': 'WFDateFormatVariableAggrandizement', 'WFDateFormatStyle': 'Custom', 'WFDateFormat': 'yyyyMMddHHmmssSSS'}
    return {'Type': 'CurrentDate', 'Aggrandizements': [ag]}


def build(url: str = 'http://YOUR-MAC-IP:8088', token: str | None = None) -> dict:
    """Three actions: the server address, the token, then POST {text, receivedAt, nonce}. With a token baked in there are no
    import questions; without one the Shortcut asks for the address and the token when it is added."""
    u_url, u_token = uid(), uid()
    shortcut_input = {'Type': 'ExtensionInput'}
    actions = [
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.gettext',
         'WFWorkflowActionParameters': {'UUID': u_url, 'WFTextActionText': url}},
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.gettext',
         'WFWorkflowActionParameters': {'UUID': u_token, 'WFTextActionText': token or 'ledg_live_paste_your_token'}},
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.downloadurl',
         'WFWorkflowActionParameters': {
             'UUID': uid(), 'ShowHeaders': True, 'WFHTTPMethod': 'POST', 'WFHTTPBodyType': 'JSON',
             'WFURL': text_token([out_ref(u_url, 'Text'), '/api/ingest/message']),
             'WFHTTPHeaders': dictionary([field('Authorization', ['Bearer ', out_ref(u_token, 'Text')])]),
             'WFJSONValues': dictionary([
                 field('text', [shortcut_input]),
                 field('receivedAt', [current_date('iso')]),
                 field('nonce', [current_date('custom')]),
             ])}},
    ]
    questions = [] if token else [
        {'ParameterKey': 'WFTextActionText', 'Category': 'Parameter', 'ActionIndex': 0,
         'Text': 'Server address. Leave it as it is unless it is wrong.', 'DefaultValue': url},
        {'ParameterKey': 'WFTextActionText', 'Category': 'Parameter', 'ActionIndex': 1,
         'Text': 'Paste your token (tap Copy next to TOKEN on the Setup guide first).', 'DefaultValue': 'ledg_live_paste_your_token'},
    ]
    out = {
        'WFWorkflowClientVersion': '2900.0.1', 'WFWorkflowMinimumClientVersion': 900, 'WFWorkflowMinimumClientVersionString': '900',
        'WFWorkflowIcon': {'WFWorkflowIconStartColor': 4282601983, 'WFWorkflowIconGlyphNumber': 59511},
        'WFWorkflowTypes': [], 'WFWorkflowHasShortcutInputVariables': True,
        'WFWorkflowInputContentItemClasses': ['WFStringContentItem', 'WFRichTextContentItem', 'WFGenericFileContentItem', 'WFURLContentItem'],
        'WFWorkflowActions': actions,
    }
    if questions:
        out['WFWorkflowImportQuestions'] = questions
    return out


def main() -> int:
    arg = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None  # noqa: E731
    url = arg('--url') or 'http://YOUR-MAC-IP:8088'
    token = arg('--token')
    out_path = Path(arg('--out')).expanduser() if arg('--out') else OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw = out_path.with_suffix('.unsigned.shortcut')
    raw.write_bytes(plistlib.dumps(build(url, token), fmt=plistlib.FMT_BINARY))
    r = subprocess.run(['shortcuts', 'sign', '--mode', 'anyone', '--input', str(raw), '--output', str(out_path)], capture_output=True, text=True)
    raw.unlink(missing_ok=True)
    if r.returncode != 0:
        print('signing failed (needs macOS with the `shortcuts` tool and a network):', r.stderr.strip() or r.stdout.strip(), file=sys.stderr)
        return 1
    print(f'wrote {out_path} ({out_path.stat().st_size} bytes)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
