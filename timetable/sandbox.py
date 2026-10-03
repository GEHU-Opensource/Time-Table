import multiprocessing
import os
import resource

from django.conf import settings

from solver.types import UNKNOWN, Result
from timetable import bridge

INLINE_ENV = "TT_SOLVER_INLINE"
JOIN_GRACE_SECONDS = 60
CPU_GRACE_SECONDS = 60

TIMED_OUT = Result(status=UNKNOWN, reasons=("solver timed out",))
CRASHED = Result(status=UNKNOWN, reasons=("solver crashed",))


def inline():
    return os.environ.get(INLINE_ENV) == "1"


def apply_limits(memory_bytes, cpu_seconds):
    for limit, value in ((resource.RLIMIT_AS, memory_bytes), (resource.RLIMIT_CPU, cpu_seconds)):
        try:
            resource.setrlimit(limit, (value, value))
        except (ValueError, OSError):
            continue


def child(instance, pipe, memory_bytes, cpu_seconds):
    apply_limits(memory_bytes, cpu_seconds)
    try:
        result = bridge.solve_instance(instance)
    except Exception:
        result = CRASHED
    try:
        pipe.send(result)
    finally:
        pipe.close()


def run_inline(instance):
    try:
        return bridge.solve_instance(instance)
    except Exception:
        return CRASHED


def run(instance):
    if inline():
        return run_inline(instance)
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    cpu_seconds = int(instance.max_seconds * instance.workers) + CPU_GRACE_SECONDS
    process = context.Process(
        target=child,
        args=(instance, sender, settings.SOLVER_MEMORY_BYTES, cpu_seconds),
        daemon=True,
    )
    process.start()
    sender.close()
    timeout = instance.max_seconds + JOIN_GRACE_SECONDS
    try:
        if not receiver.poll(timeout):
            process.terminate()
            process.join(JOIN_GRACE_SECONDS)
            return TIMED_OUT
        try:
            result = receiver.recv()
        except (EOFError, OSError):
            result = CRASHED
        process.join(JOIN_GRACE_SECONDS)
        if process.is_alive():
            process.kill()
        return result if isinstance(result, Result) else CRASHED
    finally:
        receiver.close()
