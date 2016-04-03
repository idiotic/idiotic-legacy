from setuptools import setup, find_packages
import os

libfiles = []
for x in os.walk('lib'):
    libfiles.append((os.path.join('/usr/lib/idiotic', *(x[0].split(os.path.sep)[1:])), [os.path.join(x[0], y) for y in x[2]]))

def read_license():
    with open("LICENSE") as f:
        return f.read()

setup(
    name='idiotic',
    packages=find_packages(exclude=['etc', 'contrib']),
    version='0.2.0',
    description='Distributed home automation controller',
    long_description="""The idiotic distributed internet of things inhabitance
    controller (idiotic), aims to be an extremely extensible, capable, and most
    importantly developer-and-user-friendly solution for mashing together a wide
    assortment of existing home automation technologies into something which is
    useful as a whole.""",    
    license=read_license(),
    author='Dylan Whichard',
    author_email='dylan@whichard.com',
    url='https://github.com/umbc-hackafe/idiotic',
    keywords=[
        'home automation', 'iot', 'internet of things'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: No Input/Output (Daemon)',
        'Framework :: Flask',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Home Automation',
    ],
    install_requires=[
        'docopt>=0.6.2',
        'schedule>=0.3.2',
        'aiohttp>=0.21.2',
        'werkzeug>=0.11.4',
        'Flask>=0.10.1',
    ],
    data_files=[
        ('/usr/lib/systemd/system/', ['contrib/idiotic.service']),
        ('/etc/idiotic/', ['contrib/conf.json']),
    ] + libfiles,
    entry_points={
        'console_scripts': [
            'idiotic=idiotic.__main__:main',
        ]
    },
)
