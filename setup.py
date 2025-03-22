from setuptools import setup, find_packages

setup(
    name="cachemanager",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "pydantic",
        "python-dotenv",
        "tenacity",
        "pytest",
        "pytest-asyncio"
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.12",
    ],
)