import os
import setuptools

with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()


with open(os.path.join("src/peakrdl_opentitan", "__about__.py"), encoding='utf-8') as f:
    v_dict = {}
    exec(f.read(), v_dict)
    version = v_dict['__version__']

setuptools.setup(
    name="peakrdl-opentitan",
    version=version,
    author="Risto Pejasinovic",
    author_email="risto.pejasinovic@gmail.com",
    description="Import and export OpenTitan regtool hjson format to/from the systemrdl-compiler register model",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/SystemRDL/PeakRDL-opentitan",
    package_dir={'': 'src'},
    packages=[
        "peakrdl_opentitan",
    ],
    include_package_data=True,
    python_requires='>=3.5.2',
    install_requires=[
        "systemrdl-compiler>=1.24.0",
        "peakrdl>=1.1.0",
    ],
    entry_points = {
        "peakrdl.exporters": [
            'opentitan = peakrdl_opentitan.__peakrdl__:Exporter'
        ],
        "peakrdl.importers": [
            'ip-xact = peakrdl_opentitan.__peakrdl__:Importer'
        ]
    },
    classifiers=(
        "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3 :: Only",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
    ),
    project_urls={
        "Documentation": "https://peakrdl-opentitan.readthedocs.io",
        "Source": "https://github.com/SystemRDL/PeakRDL-opentitan",
        "Tracker": "https://github.com/SystemRDL/PeakRDL-opentitan/issues",
    },
)
