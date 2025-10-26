# config.py
# Shared thresholds (in days). Default example: Green=3, Amber=14, Red=30.
_green_days = 3
_amber_days = 14
_red_days = 30

_callbacks = []  # functions to notify when thresholds change

def get_thresholds() -> tuple[int, int, int]:
    return _green_days, _amber_days, _red_days

def set_thresholds(green: int, amber: int, red: int) -> None:
    global _green_days, _amber_days, _red_days
    _green_days, _amber_days, _red_days = int(green), int(amber), int(red)
    for fn in list(_callbacks):
        try:
            fn(_green_days, _amber_days, _red_days)
        except Exception:
            pass

def register_callback(fn) -> None:
    if callable(fn) and fn not in _callbacks:
        _callbacks.append(fn)
