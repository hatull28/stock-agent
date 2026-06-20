from data import get_price_history
from analysis import analyze_stock

benchmark = get_price_history("^GSPC")
r = analyze_stock("NVDA", benchmark)

pl = r["price_levels"]
bz = r["buy_zone"]

print("=== CYCLE STAGE ===")
print(f"  Stage:     {r['cycle_stage']}")
print(f"  Reasoning: {r['cycle_stage_reasoning']}")

print()
print("=== BUY ZONE ===")
if bz:
    print(f"  Low:       ${bz['low']:.2f}")
    print(f"  High:      ${bz['high']:.2f}")
    print(f"  Floor:     ${bz['floor']:.2f}")
else:
    print("  None (stock not in uptrend)")
print(f"  Narrative: {r['buy_zone_narrative']}")

print()
print("=== PRICE LEVELS ===")
print(f"  Price now:             ${pl['price_now']:.2f}")
print(f"  SMA50:                 ${pl['sma50']:.2f}  ({pl['price_vs_sma50_pct']:+.1f}% above)")
print(f"  SMA150:                ${pl['sma150']:.2f}  ({pl['price_vs_sma150_pct']:+.1f}% above)")
print(f"  Recent 3m low:         ${pl['recent_3m_low']:.2f}")
print(f"  52-week low:           ${pl['week_52_low']:.2f}")
print(f"  Golden cross days ago: {pl['golden_cross_days_ago']}")

print()
print("=== SCORES ===")
print(f"  Micha:  {r['micha_score']}/12")
print(f"  Peter:  {r['peter_score']}/10")
v = r["verdict"]
if v:
    print(f"  Action: {v['action']}")
