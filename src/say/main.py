import typing as ty
import argparse
import os
import re
import subprocess
import json
from pathlib import Path
import shutil
import shlex
import logging


def make_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='func')
    subparsers.add_parser('list-models', help='list available models')
    subparsers.add_parser('list-speakers', help='list availabel speakers')
    subparsers.add_parser('save-cfg', help='save config to disk')
    subparsers.add_parser('check-cfg', help='check current config')
    parser_says = subparsers.add_parser('says', help='speak string message')
    parser_says.add_argument('message')
    subparsers.add_parser(
        'play-result', help='play the result using QuickTime Player')
    return parser


def get_host() -> ty.Optional[str]:
    """
    :return: the host address where ``TTS`` is installed, or ``None`` if
             ``TTS`` is installed locally
    """
    host = os.getenv('host')
    if not host or host in ['localhost', '127.0.0.1']:
        return None
    return host


def get_tts() -> Path:
    """
    :return: the local/remote path to the ``tts`` executable
    """
    return Path(os.environ['tts'])


def get_cachedir() -> Path:
    cachedir = Path(os.environ['alfred_workflow_cache'])
    cachedir.mkdir(exist_ok=True)
    return cachedir


def get_datadir() -> Path:
    datadir = Path(os.environ['alfred_workflow_data'])
    datadir.mkdir(exist_ok=True)
    return datadir


def get_device() -> ty.Optional[str]:
    device = os.environ['device']
    if not device or device == 'cpu':
        return None
    return device


def config_logging():
    if 'alfred_debug' in os.environ:
        level = logging.DEBUG
    else:
        level = logging.CRITICAL
    logging.basicConfig(
        format='%(levelname)s:%(name)s -> %(message)s', level=level)


def form_tts_cmdline(
    host: ty.Optional[str],
    tts_bin: Path,
    argv: ty.List[str],
) -> ty.List[str]:
    cmd = []
    if host:
        cmd.extend(['ssh', host])
    cmd.append(str(tts_bin))
    cmd.extend(argv)
    return cmd


def form_bash_cmdline(host: ty.Optional[str],) -> ty.List[str]:
    cmd = []
    if host:
        cmd.extend(['ssh', host])
    cmd.append('bash')
    return cmd


def list_model_names(host: ty.Optional[str], tts_bin: Path):
    logger = logging.getLogger('list_model_names')
    cmd = form_tts_cmdline(host, tts_bin, ['--list_models'])
    models = []
    with subprocess.Popen(
            cmd, text=True, stdout=subprocess.PIPE, encoding='utf-8') as proc:
        logger.debug('Command issued: %s', ' '.join(cmd))
        logger.info('Process PID: %d', proc.pid)
        for line in proc.stdout:
            line = line.strip()
            logger.debug('Read line: %r', line)
            matchobj = re.match(
                r'\d+: *(tts_models/[-/\w]+)( *\[already downloaded])?', line)
            if matchobj:
                models.append((matchobj.group(1), bool(matchobj.group(2))))
                logger.debug('Added model: %s (installed: %s)',
                             matchobj.group(1), bool(matchobj.group(2)))
    resp = {'items': []}
    for name, installed in models:
        _, lang, dataset, basename = name.split('/')
        resp['items'].append({
            'uid': name,
            'title': name if not installed else f'{name} [installed]',
            'subtitle':
            f'lang: {lang} | dataset: {dataset} | base: {basename}',
            'arg': name,
            'match': name.replace('/', ' '),
        })
    print(json.dumps(resp), end='')


def list_speakers(host: ty.Optional[str], tts_bin: Path):
    logger = logging.getLogger('list_speakers')
    model = os.environ['model']
    cmd = form_tts_cmdline(host, tts_bin, [
        '--model_name', model, '--list_speaker_idxs', '--progress_bar', 'false'
    ])
    resp = None
    with subprocess.Popen(
            cmd,
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8') as proc:
        logger.info('Process PID: %d', proc.pid)
        logger.debug('Command issued: %s', ' '.join(cmd))
        for line in proc.stdout:
            line = line.strip()
            logger.debug('Read line: %r', line)
            if line.startswith('dict_keys(['):
                line = line[len('dict_keys(['):-len('])')]
                names = [x[1:-1] for x in line.split(', ')]
                resp = {'items': [{'title': x, 'arg': x} for x in names]}
                break
            if 'I agree to the terms' in line:
                proc.stdin.write('y\n')
                proc.stdin.flush()
        proc.stdin.close()
        retcode = proc.wait()
    if not resp:
        logger.warning('Alfred response not set with retcode %d', retcode)
        resp = {
            'items': [{
                'title': 'default speaker',
                'arg': '',
            }],
        }
    print(json.dumps(resp), end='')


def save_cfg(datadir: Path):
    model = os.environ['model']
    speaker = os.environ['speaker'] or None
    with open(datadir / 'config.json', 'w', encoding='utf-8') as outfile:
        json.dump({'model': model, 'speaker': speaker}, outfile)


def check_cfg(datadir: Path):
    try:
        with open(datadir / 'config.json', encoding='utf-8') as infile:
            cfg = json.load(infile)
    except FileNotFoundError:
        cfg = {}
    model = cfg.get('model', '<default model>')
    speaker = cfg.get('speaker', '<default speaker>') or '<default speaker>'
    resp = {
        'items': [
            {
                'title': f'Model: {model}',
                'text': {
                    'copy': model if model != '<default model>' else '',
                    'largetype': model,
                },
            },
            {
                'title': f'Speaker: {speaker}',
                'text': {
                    'copy': speaker if speaker != '<default speaker>' else '',
                    'largetype': speaker,
                },
            },
        ]
    }
    print(json.dumps(resp), end='')


def says(
    host: ty.Optional[str],
    tts_bin: Path,
    device: ty.Optional[str],
    datadir: Path,
    cachedir: Path,
    message: str,
):
    logger = logging.getLogger('says')
    logger.debug('Received message %r', message)
    try:
        with open(datadir / 'config.json', encoding='utf-8') as infile:
            cfg = json.load(infile)
    except FileNotFoundError:
        cfg = {}
    model = cfg.get('model', None)
    speaker = cfg.get('speaker', None)
    tmp_output = '/tmp/tts_output.wav'
    cmd = [
        str(tts_bin),
        '--text',
        message,
        '--out_path',
        tmp_output,
        '--pipe_out',
    ]
    if device:
        cmd.extend(['--use_cuda', device])
    if model:
        cmd.extend(['--model_name', model])
    if speaker:
        cmd.extend(['--speaker_idx', speaker])
    cmdline = f'if [ -f {tmp_output} ]; then\n'
    cmdline += f'echo {tmp_output} already exists >&2\n'
    cmdline += 'exit 1\n'
    cmdline += 'fi\n'
    cmdline += shlex.join(cmd) + '\n'
    cmdline += f'rm -f {tmp_output}\n'

    output = cachedir / 'speech.wav'
    with subprocess.Popen(
            form_bash_cmdline(host),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE) as proc:
        logger.info('Process PID: %d', proc.pid)
        proc.stdin.write(cmdline.encode('utf-8'))
        proc.stdin.close()
        logger.debug('Command issued: %s', cmdline)
        with open(output, 'wb') as outfile:
            shutil.copyfileobj(proc.stdout, outfile)
        for line in proc.stderr:
            logger.debug('Read line (stderr): %r',
                         line.decode('utf-8').strip())
        logger.info('Waiting for process to complete')
        retcode = proc.wait()
        if retcode != 0:
            output.unlink()
            logger.error('Returns nonzero %d; unlinked the output', retcode)
    if retcode == 0:
        resp = {
            'items': [
                {
                    'title': 'Received result',
                    'subtitle': 'Press enter to play.',
                    'arg': str(output),
                },
            ]
        }
    else:
        resp = {
            'items': [
                {
                    'title': 'Error occurs',
                    'subtitle': 'Open Alfred debug panel to debug.',
                    'valid': False,
                },
            ]
        }
    print(json.dumps(resp), end='')


def speak_result():
    logger = logging.getLogger('speak_result')
    result_wav = Path(os.environ['result_wav'])
    logger.debug('Received result_wav as: %s', result_wav)
    result_mp3 = result_wav.with_suffix('.mp3')
    cmd = ['ffmpeg', '-y', '-i', str(result_wav), str(result_mp3)]
    logger.debug('Command issued: %s', ' '.join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        logger.error('Call to ffmpeg failed with err: %s', err)
        return
    applescript = '''\
on run argv
    set theFile to the first item of argv
    set theFile to POSIX file theFile
    tell application "QuickTime Player"
        set theAudio to open file theFile
        tell theAudio
            set theDuration to duration
            play
        end tell
        delay theDuration + 1
        close theAudio
        quit
    end tell
end run'''
    cmd = ['osascript']
    for line in applescript.split('\n'):
        cmd.extend(['-e', line.strip()])
    cmd.append(str(result_mp3))
    logger.debug('Command issued: %s', ' '.join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        logger.error(
            'Call to osascript (QuickTime Player) failed with err: %s', err)
        return


def main():
    args = make_parser().parse_args()
    config_logging()
    if args.func == 'list-models':
        host = get_host()
        tts = get_tts()
        list_model_names(host, tts)
    elif args.func == 'list-speakers':
        host = get_host()
        tts = get_tts()
        list_speakers(host, tts)
    elif args.func == 'save-cfg':
        datadir = get_datadir()
        save_cfg(datadir)
    elif args.func == 'check-cfg':
        datadir = get_datadir()
        check_cfg(datadir)
    elif args.func == 'says':
        host = get_host()
        tts = get_tts()
        device = get_device()
        datadir = get_datadir()
        cachedir = get_cachedir()
        says(host, tts, device, datadir, cachedir, args.message)
    elif args.func == 'play-result':
        speak_result()


if __name__ == '__main__':
    main()