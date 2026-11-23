import argparse
import subprocess
import time

I2C_TRANSFER = "/usr/sbin/i2ctransfer"
ADDRESS = "0x2a"
OEM_GPIO_MODE = 0x4854
OEM_VSYNC_PHASE_DELAY = 0x4858
GPIO_MODE_VSYNC = 5
VSYNC_PHASE_PLUS_2 = 2


def transfer(*args):
    result = subprocess.run(
        [I2C_TRANSFER, "-y", "1", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def write_words(register, words):
    data = [register >> 8, register & 0xFF]
    for word in words:
        data.extend((word >> 8, word & 0xFF))
    transfer(
        "w%d@%s" % (len(data), ADDRESS),
        *("0x%02x" % value for value in data),
    )


def read_words(register, count=1):
    output = transfer(
        "w2@" + ADDRESS,
        "0x%02x" % (register >> 8),
        "0x%02x" % (register & 0xFF),
        "r%d" % (2 * count),
    )
    data = [int(value, 16) for value in output.split()]
    if len(data) != 2 * count:
        raise RuntimeError("short I2C read: %r" % output)
    return [(data[i] << 8) | data[i + 1] for i in range(0, len(data), 2)]


def wait_ready():
    for _ in range(200):
        status = read_words(0x0002)[0]
        if not (status & 1):
            return status
        time.sleep(0.005)
    raise TimeoutError("Lepton CCI remained busy")


def get_attribute(command_id, word_count):
    wait_ready()
    write_words(0x0006, [word_count])
    write_words(0x0004, [command_id])
    status = wait_ready()
    return status, read_words(0x0008, word_count)


def set_attribute(command_id, words):
    wait_ready()
    write_words(0x0008, words)
    write_words(0x0006, [len(words)])
    write_words(0x0004, [command_id | 1])
    return wait_ready()


def enable_vsync(verbose=True):
    before_status, before = get_attribute(OEM_GPIO_MODE, 2)
    if verbose:
        print("before: status=0x%04x mode_words=%s" % (before_status, before))
    phase_status = set_attribute(OEM_VSYNC_PHASE_DELAY, [VSYNC_PHASE_PLUS_2, 0])
    status = set_attribute(OEM_GPIO_MODE, [GPIO_MODE_VSYNC, 0])
    if verbose:
        print("set: phase_status=0x%04x mode_status=0x%04x" % (phase_status, status))
    after_status, after = get_attribute(OEM_GPIO_MODE, 2)
    phase_read_status, phase = get_attribute(OEM_VSYNC_PHASE_DELAY, 2)
    if verbose:
        print("after: status=0x%04x mode_words=%s" % (after_status, after))
        print("phase: status=0x%04x words=%s" % (phase_read_status, phase))
    if (
        (phase_status >> 8) != 0
        or (status >> 8) != 0
        or (after_status >> 8) != 0
        or (phase_read_status >> 8) != 0
        or after[0] != GPIO_MODE_VSYNC
        or phase[0] != VSYNC_PHASE_PLUS_2
    ):
        raise RuntimeError("VSYNC mode verification failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--set-vsync", action="store_true")
    args = parser.parse_args()
    if args.set_vsync:
        enable_vsync()
    else:
        status, words = get_attribute(OEM_GPIO_MODE, 2)
        print("before: status=0x%04x mode_words=%s" % (status, words))
