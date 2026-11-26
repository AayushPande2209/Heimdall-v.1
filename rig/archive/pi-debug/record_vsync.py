import os
import queue
import sys
import threading
import time

from lep_vsync import Stream, grab


secs = float(sys.argv[1]) if len(sys.argv) > 1 else 20
name = sys.argv[2] if len(sys.argv) > 2 else time.strftime("%H%M%S")
d = os.path.expanduser("~/rec")
os.makedirs(d, exist_ok=True)
raw_path = os.path.join(d, name + ".raw")
ts_path = os.path.join(d, name + ".txt")

write_queue = queue.Queue()
writer_error = []


def writer():
    try:
        with open(raw_path, "wb", buffering=1024 * 1024) as raw, open(
            ts_path, "w", buffering=1024 * 1024
        ) as ts:
            raw_batch = []
            ts_batch = []
            while True:
                item = write_queue.get()
                if item is None:
                    break
                frame_bytes, elapsed = item
                raw_batch.append(frame_bytes)
                ts_batch.append("%.4f\n" % elapsed)
                if len(raw_batch) >= 32:
                    raw.write(b"".join(raw_batch))
                    ts.write("".join(ts_batch))
                    raw_batch.clear()
                    ts_batch.clear()
            if raw_batch:
                raw.write(b"".join(raw_batch))
                ts.write("".join(ts_batch))
    except BaseException as exc:
        writer_error.append(exc)


writer_thread = threading.Thread(target=writer, name="lepton-writer")
writer_thread.start()

st = Stream()
st.hard()
n = bad = max_queued = 0
t0 = time.time()
print("recording %.0f s -> ~/rec/%s" % (secs, name), flush=True)
try:
    while time.time() - t0 < secs:
        f = grab(st)
        if f is None:
            bad += 1
            st.hard()
            continue
        elapsed = time.time() - t0
        write_queue.put((f.tobytes(), elapsed))
        max_queued = max(max_queued, write_queue.qsize())
        n += 1
        if n % 10 == 0:
            print("  %d frames  %.1f fps" % (n, n / elapsed), flush=True)
except KeyboardInterrupt:
    pass
finally:
    elapsed = max(0.1, time.time() - t0)
    st.close()
    write_queue.put(None)
    writer_thread.join()

if writer_error:
    raise writer_error[0]
print(
    "done: %d frames in %.1f s (%.1f fps), %d resyncs, max queue %d"
    % (n, elapsed, n / elapsed, bad, max_queued)
)
print(
    "capture stats: invalid segments %d, recoveries %d, VSYNC timeouts %d, phase corrections %d"
    % (
        getattr(st, "invalid_segments", 0),
        getattr(st, "recoveries", 0),
        getattr(st, "vsync_timeouts", 0),
        getattr(st, "phase_corrections", 0),
    )
)
