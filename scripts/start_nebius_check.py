"""Start an isolated local test SuperLink without touching the existing provider.
No infrastructure is provisioned. Requires operator-confirmed credit coverage.
"""
import os
from slac_assistant.data import ROOT
from slac_assistant.nebius import require_nebius_environment

def main():
    require_nebius_environment()
    env=os.environ.copy()
    env['PATH']=str(ROOT/'.venv/bin')+os.pathsep+env.get('PATH','')
    env['FLWR_HOME']=str(ROOT/'.flower-nebius-check')
    # Only this NEW child runtime: prevent background title generation from
    # spending through the existing provider. The running original is untouched.
    env.pop('FLWR_MODEL_API_ENDPOINT',None)
    env.pop('FLWR_MODEL_API_KEY',None)
    binary=str(ROOT/'.venv/bin/flower-superlink')
    os.chdir(ROOT)
    os.execve(binary,[binary,'--insecure','--host','127.0.0.1','--port','8001',
        '--fleet-api-address','127.0.0.1:19093','--disable-runtime-dependency-installation'],env)

if __name__=='__main__':main()
