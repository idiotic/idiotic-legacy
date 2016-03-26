# How to run Idiotic

Idiotic is written in Python3, and packaged as a module. To run idiotic, construct a configuration
directory (`/etc/idiotic` by default) which contains directories `items`, `modules`, and `rules`.

It is easy to install dependencies inside a virtual environment.
Use `python3 -m venv env` to create a virtual environment named `env`.
Then, use `env/bin/pip install -r requirements.txt` to install Idiotic requirements inside the
virtual environment.

Invoke with
```
env/bin/python3 -m idiotic -b path/to/config/directory
```
or just
```
python3 -m idiotic -b path/to/config/directory
```
if you are not using virtual environments.
