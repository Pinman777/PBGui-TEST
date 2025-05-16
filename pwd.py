"""
Mock implementation of pwd for Windows systems.
This module provides dummy implementations of functions from the pwd module,
which is only available on Unix-like systems.
"""

class struct_passwd:
    """Dummy implementation of struct_passwd class"""
    def __init__(self, name="user", passwd="x", uid=1000, gid=1000, gecos="", dir="/home/user", shell="/bin/bash"):
        self.pw_name = name
        self.pw_passwd = passwd
        self.pw_uid = uid
        self.pw_gid = gid
        self.pw_gecos = gecos
        self.pw_dir = dir
        self.pw_shell = shell

def getpwuid(uid):
    """Dummy implementation of getpwuid function"""
    return struct_passwd(uid=uid)

def getpwnam(name):
    """Dummy implementation of getpwnam function"""
    return struct_passwd(name=name)

def getpwall():
    """Dummy implementation of getpwall function"""
    return [struct_passwd()] 