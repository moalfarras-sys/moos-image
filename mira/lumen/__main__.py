"""`mira-lumen` — Lumen from a terminal.

    mira-lumen serve                     run the engine (the user service does this at login)
    mira-lumen status                    every light, room, scene and what Screen Sync is doing
    mira-lumen set TARGET [--on|--off] [--color C] [--brightness N] [--kelvin K] [--effect E]
    mira-lumen scene NAME [TARGET]       a scene (aurora, sunset, focus …) on TARGET (default: all)
    mira-lumen sync start|stop [--mode video|game|ambient] [--target T]
    mira-lumen pc                        the computer's lighting controller and its headers
    mira-lumen hue pair|status|forget    pair Lumen with the Hue bridge (press its button)

TARGET is words: all, pc, a room, a group, a light's name («المكتب», "Büro"), comma-separated.
"""
from __future__ import annotations

import argparse
import json
import sys


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ['serve']:
        from lumen.service import serve
        return serve()
    from lumen import client
    p = argparse.ArgumentParser(prog='mira-lumen', description='Lumen, the MoOS lighting engine')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    s = sub.add_parser('set')
    s.add_argument('target')
    s.add_argument('--on', action='store_true')
    s.add_argument('--off', action='store_true')
    s.add_argument('--color')
    s.add_argument('--brightness', type=float)
    s.add_argument('--kelvin', type=int)
    s.add_argument('--effect')
    sc = sub.add_parser('scene')
    sc.add_argument('name')
    sc.add_argument('target', nargs='?', default='all')
    sy = sub.add_parser('sync')
    sy.add_argument('action', choices=['start', 'stop', 'status'])
    sy.add_argument('--mode', default='video', choices=['video', 'game', 'ambient'])
    sy.add_argument('--target')
    sub.add_parser('pc')
    h = sub.add_parser('hue')
    h.add_argument('action', choices=['pair', 'status', 'forget', 'discover'])
    h.add_argument('--host')
    args = p.parse_args(argv)

    if args.cmd == 'status':
        reply = client.request('snapshot')
        if reply.get('status') == 'ok':
            for light in reply['lights']:
                st = light['state']
                print('%-28s %-14s %-6s %-7s %s' % (light['name'][:28], (light['room'] or '-')[:14],
                      'on' if st.get('on') else ('off' if st.get('on') is False else '?'),
                      ('%s%%' % st['brightness']) if st.get('brightness') is not None else '',
                      '' if light['online'] else 'UNAVAILABLE'))
            print('sync:', json.dumps(reply['sync'], ensure_ascii=False))
            return 0
    elif args.cmd == 'set':
        on = True if args.on else (False if args.off else None)
        reply = client.request('set', target=args.target, on=on, color=args.color, brightness=args.brightness,
                               kelvin=args.kelvin, effect=args.effect)
    elif args.cmd == 'scene':
        reply = client.request('scene', name=args.name, target=args.target)
    elif args.cmd == 'sync':
        if args.action == 'start':
            reply = client.request('sync_start', mode=args.mode, target=args.target)
        elif args.action == 'stop':
            reply = client.request('sync_stop')
        else:
            reply = client.request('sync_status')
    elif args.cmd == 'pc':
        reply = client.request('snapshot')
        reply = {'status': reply.get('status'), 'pc': reply.get('pc'),
                 'lights': [l for l in reply.get('lights', []) if l['source'] == 'pc']}
    else:
        op = {'pair': 'hue_pair', 'status': 'hue_status', 'forget': 'hue_forget', 'discover': 'hue_discover'}[args.action]
        reply = client.request(op, **({'host': args.host} if args.host else {}))
    print(json.dumps(reply, ensure_ascii=False, indent=1))
    return 0 if reply.get('status') in ('ok', 'pending') else 1


if __name__ == '__main__':
    sys.exit(main())
