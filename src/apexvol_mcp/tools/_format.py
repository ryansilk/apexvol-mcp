"""Small formatting helpers shared by the tool modules (0.1.4)."""


def csv_symbols(value) -> str:
    """'spy, qqq,iwm' or ['SPY', 'QQQ'] -> 'SPY,QQQ,IWM' (deduped, upper case)."""
    parts = value if isinstance(value, (list, tuple)) else str(value).replace(';', ',').split(',')
    out = []
    for p in parts:
        sym = str(p).strip().upper()
        if sym and sym not in out:
            out.append(sym)
    return ','.join(out)


def num(value, digits: int = 1) -> str:
    """A number for a markdown cell, or n/a."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 'n/a'
    return f"{value:,.{digits}f}"


def money(value) -> str:
    return f"${value:,.2f}" if isinstance(value, (int, float)) and not isinstance(value, bool) else 'n/a'
