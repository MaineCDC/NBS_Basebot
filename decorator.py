import traceback
from datetime import datetime
from functools import wraps

def error_handle(func):
    @wraps(func)
    def wrapper_error_handle(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            tb = traceback.format_exc()
            print(f"\n!!! ERROR in {func.__name__} !!!")
            print(tb)
            print(f"!!! Error also logged to error_logs.txt !!!\n")
            with open("error_logs.txt", "a") as log:
                log.write(
    f"saved/{datetime.now().date().strftime('%m_%d_%Y')} - "
    f"{datetime.now().time()} | "
    f"{func.__name__.replace('start_', '')} - "
    f"{str(tb)}\n"
)
    return wrapper_error_handle