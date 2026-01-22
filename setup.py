"""Setup script for DevAIFlow - AI-Powered Development Workflow Manager."""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="devaiflow",
    version="1.0.0-dev",
    author="Dominique Vernier",
    description="DevAIFlow - Manage AI coding assistant sessions with optional issue tracker integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/itdove/devaiflow",
    project_urls={
        "Bug Tracker": "https://github.com/itdove/devaiflow/issues",
        "Documentation": "https://github.com/itdove/devaiflow/blob/main/README.md",
        "Source Code": "https://github.com/itdove/devaiflow",
    },
    packages=find_packages(),
    package_data={},
    data_files=[
        ("", ["DAF_AGENTS.md"]),
    ],
    include_package_data=True,
    keywords=[
        "ai",
        "claude",
        "github-copilot",
        "cursor",
        "windsurf",
        "development-workflow",
        "jira",
        "project-management",
        "automation",
        "session-manager",
        "devops",
        "cli",
        "ai-assistant",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "click>=8.1.7",
        "pydantic>=2.5.0",
        "rich>=13.7.0",
        "textual>=0.47.0",
        "anthropic>=0.40.0",
        "requests>=2.31.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
            "black>=23.12.1",
            "ruff>=0.1.9",
            "mypy>=1.8.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "daf=devflow.cli.main:cli",
        ],
    },
)
