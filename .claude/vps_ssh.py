import sys, time, os, paramiko

HOST = "177.7.55.56"
USER = "root"
PW = os.environ.get("VPS_ROOT_PW", "")  # key auth is installed; password no longer needed
KEYFILE = os.path.expanduser("~/.ssh/kbm_vps")

def connect_pw(retries=6, delay=5):
    last = None
    for i in range(retries):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, username=USER, password=PW, timeout=12,
                      allow_agent=False, look_for_keys=False)
            return c
        except Exception as e:
            last = e
            print(f"[attempt {i+1}] not ready: {e}", flush=True)
            time.sleep(delay)
    raise last

def connect_key():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, key_filename=KEYFILE, timeout=12,
              allow_agent=False, look_for_keys=False)
    return c

def run(c, cmd):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    return out, err

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "install"
    if mode == "install":
        c = connect_pw()
        pub = open(KEYFILE + ".pub").read().strip()
        setup = (
            "mkdir -p /root/.ssh && chmod 700 /root/.ssh && "
            "grep -qxF '%s' /root/.ssh/authorized_keys 2>/dev/null || "
            "echo '%s' >> /root/.ssh/authorized_keys; "
            "chmod 600 /root/.ssh/authorized_keys; echo INSTALLED" % (pub, pub)
        )
        out, err = run(c, setup)
        print("KEY:", out.strip(), err.strip())
        c.close()
        # verify key works
        c2 = connect_key()
        out, err = run(c2, "echo KEYAUTH_OK; hostname; whoami")
        print(out, err)
        c2.close()
    else:
        # run an arbitrary command file via key auth
        c = connect_key()
        cmd = open(sys.argv[2]).read()
        out, err = run(c, cmd)
        sys.stdout.write(out)
        if err.strip():
            sys.stderr.write("\n--STDERR--\n" + err)
        c.close()

if __name__ == "__main__":
    main()
