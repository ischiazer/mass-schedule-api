def post_fork(server, worker):
    from app.utilities import log_msg
    from background_threads import start_background_threads

    log_msg(f"[Gunicorn post_fork] Starting background threads in worker PID {worker.pid}")
    start_background_threads()
