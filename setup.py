from setuptools import setup, find_packages

setup(
    name="cachemanager",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pydantic",
        "python-dotenv",
        "tenacity",
        "pytest",
        "pytest-asyncio"
    ],
) 