"""Start the job API with public model settings, without provider credentials."""
import os
from start_flower import ROOT, DEFAULT_MODEL, read_configuration


def main():
    try:
        settings = read_configuration(ROOT / '.env') if (ROOT / '.env').exists() else {}
    except (OSError, ValueError):
        raise SystemExit('Private configuration is invalid; API not started.') from None
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('OPENAI_', 'FLWR_MODEL_', 'FLWR_RUNTIME_', 'PACTERRA_'))}
    env['INVESTIGATOR_MODEL'] = settings.get('INVESTIGATOR_MODEL') or DEFAULT_MODEL
    os.chdir(ROOT)
    binary = str(ROOT / '.venv/bin/uvicorn')
    os.execve(binary, [binary, 'slac_assistant.api:create_app', '--factory',
                     '--host', '127.0.0.1', '--port', '8080', '--workers', '1'], env)


if __name__ == '__main__':
    main()
