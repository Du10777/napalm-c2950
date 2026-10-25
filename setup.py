"""Packaging for napalm-c2950."""
from setuptools import setup, find_packages

with open("requirements.txt") as f:
    reqs = [line.strip() for line in f if line.strip() and not line.startswith("#")]

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="napalm-c2950",
    version="0.2.0",
    description=(
        "NAPALM driver for Cisco Catalyst 2950 (WS-C2950G-48-EI) classic IOS switches"
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Du10777",
    url="https://github.com/Du10777/napalm-c2950",
    project_urls={
        "Source": "https://github.com/Du10777/napalm-c2950",
        "Issues": "https://github.com/Du10777/napalm-c2950/issues",
    },
    license="Apache 2.0",
    keywords="napalm cisco catalyst 2950 ios switch network automation",
    packages=find_packages(exclude=("test", "test.*")),
    include_package_data=True,
    package_data={"napalm_c2950": ["templates/*.textfsm"]},
    install_requires=reqs,
    extras_require={"dev": ["pytest"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Topic :: System :: Networking",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
    ],
    python_requires=">=3.8",
)
