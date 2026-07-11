import hashlib
import json


def build_blind_profile(data, days=40):
    """Convert a raw OHLCV DataFrame to an anonymized indexed profile.

    Pure function: no I/O, no network, no globals.

    Price transform: Day 1 Close = 100.00. Every O/H/L/C value is expressed as a
    percentage of that anchor. This preserves shape and relative range exactly while
    removing the absolute price band that fingerprints a specific stock.

    Volume transform: each day's volume divided by the mean volume across the 40-day
    window. Removes the absolute share-count fingerprint that distinguishes a
    60M-share/day mega-cap from a 2M-share/day name.

    Returns:
        {
            "rows": [{"day": int, "O": float, "H": float, "L": float,
                      "C": float, "V_ratio": float}, ...],
            "profile_hash": str,  # SHA-256 hex of canonical JSON — proves a
                                  # prediction was made against this exact input
        }
    """
    window = data.iloc[-days:]

    anchor = float(window["Close"].iloc[0])
    mean_vol = float(window["Volume"].mean())

    rows = []
    for i, (_, row) in enumerate(window.iterrows(), start=1):
        rows.append({
            "day": i,
            "O": round(float(row["Open"])   / anchor * 100, 2),
            "H": round(float(row["High"])   / anchor * 100, 2),
            "L": round(float(row["Low"])    / anchor * 100, 2),
            "C": round(float(row["Close"])  / anchor * 100, 2),
            "V_ratio": round(float(row["Volume"]) / mean_vol, 2),
        })

    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    profile_hash = hashlib.sha256(canonical.encode()).hexdigest()

    return {"rows": rows, "profile_hash": profile_hash}


def format_profile_table(rows):
    """Format profile rows as a compact text table for the AI prompt.

    Output per row (no ticker, no dates, no absolute dollar values):
        Day  1  O:100.00 H:102.67 L: 99.94 C:101.89 V_ratio: 0.87
    """
    lines = []
    for r in rows:
        lines.append(
            f"Day {r['day']:>2}  "
            f"O:{r['O']:>7.2f} H:{r['H']:>7.2f} "
            f"L:{r['L']:>7.2f} C:{r['C']:>7.2f} "
            f"V_ratio:{r['V_ratio']:>5.2f}"
        )
    return "\n".join(lines)
