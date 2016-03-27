import subprocess

# Only change LISTED by hand.
LISTED = '0.2.0'
# Do not bump or change elements below.

def scm_version(silent = False):
    try:
        return subprocess.check_output(
                ['git', 'describe', '--tags', '--dirty=+'],
                stderr = subprocess.DEVNULL
            ).decode('UTF-8').strip()
    except subprocess.CalledProcessError as e:
        if not silent:
            print("Could not get git output:", e)

SOURCE = scm_version(silent = True)

# Provide the most explicit available version.
VERSION = SOURCE if SOURCE else LISTED
