"""Six argv-only harness adapters. No GUI imports or implicit login/model calls."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from .io import atomic_write, FileLock

KINDS=('hermes','claude','codex','pi','command-code','opencode')
LABELS=dict(zip(KINDS,('Hermes','Claude Code','Codex','Pi','Command Code','OpenCode')))
DEFAULTS={'executable':'','model':'','provider':'','profile':'','home':'','cwd':''}
REQUIRED_FLAGS={'hermes':('--format','--query','--query-file','--toolsets'),'claude':('--output-format','--permission-mode'),'codex':('--json',),'pi':('--mode','--session'),'command-code':('--output-format','--resume'),'opencode':('--format','--agent','--session')}


def options_for(store,kind):
    if kind not in KINDS: raise ValueError('Unknown harness')
    path=store.home/'harnesses.json'
    saved=json.loads(path.read_text()) if path.exists() else {}
    values={**DEFAULTS,**saved.get(kind,{})}
    if kind=='hermes' and kind not in saved:
        from .research import hermes_options
        previous=hermes_options(store)
        values.update({k:v for k,v in previous.items() if k in values})
    values['executable']=values['executable'] or kind
    return validate_options(kind,values)


def validate_options(kind,values):
    if kind not in KINDS: raise ValueError('Unknown harness')
    if any(k not in DEFAULTS or not isinstance(v,str) or len(v)>4096 or any(c in v for c in '\x00\n\r') for k,v in values.items()):
        raise ValueError('Invalid harness setting; secrets and raw argv are not accepted')
    values={**DEFAULTS,**values}
    values['executable']=values['executable'] or kind
    for key in ['home','cwd']:
        if values[key] and not Path(values[key]).expanduser().is_absolute(): raise ValueError(key+' must be an absolute path')
    if values['profile'] and (values['profile'].startswith('-') or not re.fullmatch(r'[\w.-]+',values['profile'])): raise ValueError('Invalid profile')
    for key in ['model','provider']:
        if values[key].startswith('-'): raise ValueError('Invalid '+key)
    if kind=='hermes' and values['home']: hermes_home(values)
    return values


def save_options(store,kind,values):
    values=validate_options(kind,values)
    path=store.home/'harnesses.json'
    with FileLock(store.lock_path):
        saved=json.loads(path.read_text()) if path.exists() else {}
        saved[kind]=values
        atomic_write(path,json.dumps(saved,ensure_ascii=False).encode())


def resolve_executable(kind,options):
    name=options.get('executable') or kind
    found=shutil.which(name)
    if not found and kind=='command-code' and name==kind: found=shutil.which('cmdc' if os.name=='nt' else 'cmd')
    return found


def hermes_home(options):
    explicit=options.get('home')
    inherited=os.getenv('HERMES_HOME')
    candidate=Path(explicit or inherited or Path.home()/'.hermes').expanduser()
    uid=getattr(os,'getuid',lambda: None)()
    owned=(candidate.stat().st_uid==uid) if uid is not None and candidate.exists() else candidate.is_relative_to(Path.home())
    if not owned:
        if explicit: raise ValueError('Hermes home belongs to another account; credentials are never shared implicitly')
        candidate=Path.home()/'.hermes'
    return candidate


def environment(kind,options):
    # Never inherit another agent's task ownership into the launched harness.
    env={k:v for k,v in os.environ.items() if not k.startswith(('HERMES_KANBAN_','PYTEST_')) and k not in {'PYTHONPATH','VIRTUAL_ENV'}}
    env['STICKY_INTENT_SUPERVISED_RUN']='1'
    if kind=='hermes': env['HERMES_HOME']=str(hermes_home(options))
    return env


def build_command(kind,prompt,options=None,session=None):
    o=validate_options(kind,options or {})
    if not isinstance(prompt,str): raise ValueError('Prompt must be text')
    if session and (not isinstance(session,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}',session)):
        raise ValueError('Invalid session identifier')
    exe=o['executable']; model=o['model']; provider=o['provider']
    if kind=='hermes':
        argv=[exe]
        if o['profile']: argv+=['--profile',o['profile']]
        if session: argv+=['--resume',session]
        argv+=['chat','--format','stream-json','--toolsets','web']
        if provider: argv+=['--provider',provider]
        if model: argv+=['--model',model]
        return argv+['-q',prompt]
    if kind=='claude':
        argv=[exe,'-p',prompt,'--output-format','json','--permission-mode','plan','--max-turns','12']
        if session: argv+=['--resume',session]
    elif kind=='codex':
        argv=[exe,'--sandbox','read-only','--ask-for-approval','never','--search']
        if o['profile']: argv+=['--profile',o['profile']]
        if model: argv+=['--model',model]
        argv+=['exec']+(['resume',session] if session else [])+['--json','--skip-git-repo-check',prompt]
        return argv
    elif kind=='pi':
        argv=[exe,'--mode','json','--print','--tools','read,grep,find,ls','--no-mcp','--no-extensions']
        if session: argv+=['--session',session]
        if provider:
            if not model: raise ValueError('Pi requires a model when a provider is selected')
            argv+=['--provider',provider]
        argv+=['--',prompt]
        if model: argv[1:1]=['--model',model]
        return argv
    elif kind=='command-code':
        argv=[exe,'-p',prompt,'--output-format','json','--permission-mode','plan','--max-turns','12']
        if session: argv+=['--resume',session]
    else:
        argv=[exe,'run','--format','json','--agent','plan']
        if session: argv+=['--session',session]
        argv+=['--',prompt]
        if model: argv[2:2]=['--model',model]
        return argv
    if model: argv+=['--model',model]
    return argv


def parse_reply(kind,output,exit_code=0):
    if kind not in KINDS: raise ValueError('Unknown harness')
    result=dict(success=False,text='',session_id='',error='No completed structured reply was returned')
    if exit_code!=0:
        result['error']='Harness exited with code '+str(exit_code); return result
    try:
        # LF only: U+2028/U+2029 may legitimately occur inside a JSON string.
        records=[json.loads(line) for line in output.split('\n') if line.strip()]
    except (ValueError,TypeError): return result
    if not records or not all(isinstance(r,dict) for r in records): return result
    text=''; session=''; completed=False; error=''; pi_final=False; pi_message_error=''
    for r in records:
        typ=r.get('type')
        if not isinstance(typ,str): return result
        if typ in {'error','turn.failed','run_error'}: error=str(r.get('error') or r.get('message') or 'Harness reported failure')
        if kind=='hermes' and typ=='result':
            session=r.get('session_id',''); completed=r.get('exit_code')==0
            text=r.get('text',''); error=error or str(r.get('error') or '')
        elif kind=='claude' and typ=='result':
            session=r.get('session_id',''); completed=r.get('subtype')=='success' and not r.get('is_error',False)
            text=r.get('result',''); error=error or str(r.get('error') or ('' if completed else 'Claude did not complete successfully'))
        elif kind=='codex':
            if typ=='thread.started': session=r.get('thread_id','')
            if typ=='item.completed' and isinstance(r.get('item'),dict) and r['item'].get('type')=='agent_message': text=r['item'].get('text','')
            if typ=='turn.completed': completed=True
        elif kind=='pi':
            if typ=='session': session=r.get('id','')
            if typ=='message_end' and isinstance(r.get('message'),dict) and r['message'].get('role')=='assistant':
                msg=r['message']; content=msg.get('content',[])
                if not isinstance(content,list) or any(isinstance(c,dict) and c.get('type')=='text' and not isinstance(c.get('text'),str) for c in content): return result
                text=''.join(c.get('text','') for c in content if isinstance(c,dict) and c.get('type')=='text')
                pi_final=msg.get('stopReason') in {'stop','end_turn'}
                pi_message_error='' if pi_final else str(msg.get('errorMessage') or 'Pi did not finish with a final answer')
            if typ=='agent_settled':
                completed=r.get('aborted') is False and pi_final
                if not completed and pi_message_error: error=pi_message_error
                if r.get('aborted') is True: error='Pi run was aborted'
        elif kind=='command-code' and typ=='result':
            session=r.get('sessionId',''); completed=r.get('subtype')=='success'; text=r.get('finalText','')
            if not completed: error=str(r.get('error') or 'Command Code did not complete successfully')
        elif kind=='opencode':
            session=r.get('sessionID') or session
            if typ=='text' and isinstance(r.get('part'),dict):
                if not isinstance(r['part'].get('text'),str): return result
                text+=r['part']['text']
            if typ=='step_finish' and isinstance(r.get('part'),dict): completed=r['part'].get('reason')=='stop'
    if not isinstance(text,str) or not text.strip() or not completed or error:
        result['error']=error or result['error']; return result
    result.update(success=True,text=text,session_id=session if isinstance(session,str) else '',error='')
    return result


def setup_command(kind,options):
    exe=options.get('executable') or kind
    if kind=='hermes': return [exe]+(['--profile',options['profile']] if options.get('profile') else [])+['model']
    return [exe]+{'claude':['auth','login'],'codex':['login'],'pi':[],'command-code':['login'],'opencode':['auth','login']}[kind]


def _hermes_provider(options):
    if options.get('provider'): return options['provider']
    home=hermes_home(options)
    if options.get('profile'): home=home/'profiles'/options['profile']
    try:
        # Read only a literal model.provider scalar; do not inspect/export credentials.
        text=(home/'config.yaml').read_text()[:256000]
        match=re.search(r'^model:\s*\n((?:[ \t]+[^\n]*\n?)*)',text,re.M)
        if match:
            provider=re.search(r'^\s+provider:\s*[\"\']?([A-Za-z0-9_.:-]+)',match[1],re.M)
            if provider: return provider[1]
    except OSError: pass
    return ''


def connection(kind,options=None,*,probe=False):
    options=validate_options(kind,options or {})
    # The visual-review launcher deliberately disables every agent CLI. It
    # must not present its blocked wrappers as installed-but-incompatible
    # applications when the operator checks the connection picker.
    if os.getenv('STICKY_INTENT_REVIEW_MODE')=='1':
        return dict(kind=kind,label=LABELS[kind],state='review_only',can_run=False,
                    reason='Agent connections are disabled in local visual-review mode; nothing was run.',
                    executable='',can_resume=False)
    if kind=='pi' and not options['model'] and not options['provider']:
        directory=Path(os.getenv('PI_CODING_AGENT_DIR') or Path.home()/'.pi/agent')
        try:
            defaults=json.loads((directory/'settings.json').read_text())
            if isinstance(defaults,dict):
                model=defaults.get('defaultModel'); provider=defaults.get('defaultProvider')
                if isinstance(model,str) and isinstance(provider,str): options=validate_options(kind,{**options,'model':model,'provider':provider})
        except (OSError,ValueError): pass
    exe=resolve_executable(kind,options)
    base=dict(kind=kind,label=LABELS[kind],state='not_installed',can_run=False,reason='Executable not found: '+options['executable'],executable=exe or '',can_resume=False)
    if not exe: return base
    base.update(state='unchecked',reason='Installed. Check connection before starting work.')
    if not probe: return base
    options={**options,'executable':exe}; env=environment(kind,options)
    help_argv=[exe]+({'hermes':['chat'],'codex':['exec'],'opencode':['run']}.get(kind,[]))+['--help']
    try:
        help_result=subprocess.run(help_argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=12,env=env)
        help_text=help_result.stdout+help_result.stderr
        if help_result.returncode!=0:
            return {**base,'state':'check_failed','reason':LABELS[kind]+' could not report its CLI options (help exited '+str(help_result.returncode)+'); no run was made.'}
        missing=[flag for flag in REQUIRED_FLAGS[kind] if flag not in help_text]
        if missing:
            return {**base,'state':'unsupported_version','reason':LABELS[kind]+' CLI is missing required option'+('s ' if len(missing)>1 else ' ')+', '.join(missing)+'; no run was made.'}
        base['can_resume']=('--resume' in help_text or '--session' in help_text or kind=='codex')
        if kind=='hermes':
            provider=_hermes_provider(options)
            if not provider: return {**base,'state':'setup_required','reason':'Select your Hermes provider/model using Connect / configure.'}
            args=[exe]+(['--profile',options['profile']] if options['profile'] else [])+['auth','status',provider]
        elif kind=='claude': args=[exe,'auth','status']
        elif kind=='codex': args=[exe,'login','status']
        elif kind=='pi':
            if not options['model'] and not options['provider']: return {**base,'state':'setup_required','reason':'Choose a Pi model/provider, then check its credentials.'}
            args=[exe,'auth','check','--no-refresh','--json']+(['--model',options['model']] if options['model'] else ['--provider',options['provider']])
        elif kind=='command-code': args=[exe,'status','--json']
        else: args=[exe,'auth','list']
        done=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=12,env=env)
        text=(done.stdout+'\n'+done.stderr).strip(); lower=re.sub(r'\x1b\[[0-9;]*[A-Za-z]','',text.lower())
        if any(marker in lower for marker in ['logged out','not logged in','no access token','not_ready','0 credentials','authentication required']):
            return {**base,'state':'authentication_required','reason':'Sign in/configure '+LABELS[kind]+' in this desktop account, then recheck.'}
        authenticated=False
        try:
            obj=json.loads(done.stdout)
            if isinstance(obj,dict):
                if obj.get('error'): return {**base,'state':'setup_required','reason':'Native harness reports a configuration/authentication error. Use its terminal setup to inspect and repair it.'}
                if any(obj.get(k) is False for k in ['loggedIn','authenticated','logged_in']): return {**base,'state':'authentication_required','reason':'Sign in/configure '+LABELS[kind]+' in this desktop account, then recheck.'}
                authenticated=obj.get('loggedIn') is True or obj.get('authenticated') is True or obj.get('logged_in') is True or obj.get('status')=='ready'
        except ValueError: pass
        authenticated=authenticated or ('logged in' in lower and 'not logged in' not in lower) or (kind=='pi' and done.returncode==0) or (kind=='opencode' and bool(re.search(r'\b[1-9][0-9]* credentials?\b',lower)))
        if done.returncode==0 and authenticated: return {**base,'state':'ready','can_run':True,'reason':'Native harness reports credentials available. Provider execution is checked when you start a run.'}
        return {**base,'state':'authentication_required' if done.returncode else 'unverified','reason':'Native connection check did not establish readiness. Connect/configure and recheck; no model call was made.'}
    except (OSError,subprocess.TimeoutExpired) as exc:
        return {**base,'state':'check_failed','reason':'Connection check failed: '+str(exc)}
