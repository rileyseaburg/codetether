"""Setup script for CodeTether.

Distribution name: CodeTether
Python packages: a2a_server (server implementation), agent_worker (system worker)
"""

from setuptools import setup, find_packages


def _read_readme() -> str:
    try:
        with open('README.md', 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return 'CodeTether - production-ready agent orchestration platform.'


setup(
    name='codetether',
    version='1.2.0',
    description='CodeTether: A2A Protocol v0.3 compliant agent orchestration platform with MCP + OpenCode integration',
    long_description=_read_readme(),
    long_description_content_type='text/markdown',
    author='CodeTether Contributors',
    author_email='',
    url='https://github.com/rileyseaburg/codetether',
    packages=find_packages(
        exclude=['tests', 'tests.*', 'examples', 'examples.*']
    ),
    # Include top-level modules used by console entrypoints.
    py_modules=['run_server'],
    package_data={
        'a2a_server': ['../ui/*.html', '../ui/*.js'],
    },
    include_package_data=True,
    python_requires='>=3.10',
    install_requires=[
        'fastapi>=0.104.0',
        'uvicorn>=0.24.0',
        'pydantic>=2.0.0',
        'httpx>=0.25.0',
        # Worker runtime
        'aiohttp>=3.9.0',
        'redis>=5.0.0',
        'mcp>=1.0.0',
        # LiveKit integration for real-time media
        'livekit>=0.15.0',
        'livekit-api>=1.0.0',
        # Official A2A Protocol SDK
        'a2a-sdk[http-server]>=0.3.22',
    ],
    entry_points={
        'console_scripts': [
            # Main UX: `codetether` starts a server by default.
            'codetether=codetether.cli:main',
            # Worker runner.
            'codetether-worker=codetether.worker_cli:main',
            # Back-compat friendly alias.
            'a2a-server=codetether.cli:main',
        ]
    },
    extras_require={
        'test': [
            'pytest>=7.4.0',
            'pytest-asyncio>=0.21.0',
            'pytest-cov>=4.1.0',
        ],
        'dev': [
            'black>=23.0.0',
            'ruff>=0.1.0',
            'mypy>=1.6.0',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
)
