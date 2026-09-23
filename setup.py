from setuptools import setup, find_packages

setup(
    name="passx",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "passx = passx.cli.main:main",
        ],
    },
)
