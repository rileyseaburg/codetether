"""Setup script for A2A Server MCP."""

from setuptools import setup, find_packages

setup(
    name="a2a-server-mcp",
    version="1.0.0",
    description="Agent-to-Agent (A2A) Server with MCP integration",
    author="A2A Server Team",
    author_email="",
    url="https://github.com/rileyseaburg/A2A-Server-MCP",
    packages=find_packages(exclude=["tests", "tests.*", "examples", "examples.*"]),
    package_data={
        "a2a_server": ["../ui/*.html", "../ui/*.js"],
    },
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "pydantic>=2.0.0",
        "httpx>=0.25.0",
        "redis>=5.0.0",
        "mcp>=1.0.0",
    ],
    extras_require={
        "test": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
        ],
        "dev": [
            "black>=23.0.0",
            "ruff>=0.1.0",
            "mypy>=1.6.0",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
