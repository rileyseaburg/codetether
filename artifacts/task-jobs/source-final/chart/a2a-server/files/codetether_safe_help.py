#!/usr/bin/python3
"""Do not let CLI help render environment-backed credentials in Job output."""

import os
import sys


def main():
    env = dict(os.environ)
    if any(arg in {'--help', '-h'} for arg in sys.argv[1:]):
        env = {
            k: v
            for k, v in env.items()
            if not any(
                s in k.upper()
                for s in ('TOKEN', 'SECRET', 'PASSWORD', 'API_KEY')
            )
        }
    binary = '/usr/local/bin/codetether'
    os.execve(binary, [binary, *sys.argv[1:]], env)


if __name__ == '__main__':
    main()
