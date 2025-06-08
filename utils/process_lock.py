import os
import fcntl

class ProcessLock:
    def __init__(self, lockfile: str = "/tmp/bot.lock"):
        self.lockfile = lockfile
        self.fp = None

    def acquire(self):
        self.fp = open(self.lockfile, "w")
        try:
            fcntl.flock(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except IOError:
            return False

    def release(self):
        if self.fp:
            fcntl.flock(self.fp, fcntl.LOCK_UN)
            self.fp.close()
            self.fp = None
