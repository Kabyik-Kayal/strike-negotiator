# Contradiction Targets

Fill in the Chunk IDs after running `load_filings.py`. Each target needs a specific,
worker-related claim from the filing that the seeded grievances can plausibly contradict.

Good claims: a number + "partner" or "earnings" in the same sentence.
Bad claims: aspirational language, aggregate company financials, forward-looking projections.

---

## Target: SWIGGY-DRHP-PARTNER-EARNINGS-GROWTH

- **Chunk ID:** swiggy-drhp-pXX-cY  ← fill after load_filings.py runs
- **Filing claim:** ← paste the exact sentence, e.g. "Partner earnings grew 18% YoY in FY24."
- **What workers contradict:** Per-order rates cut from ₹35 to ₹28 since March 2026; monthly earnings down ₹6k for same hours
- **Grievance angle:** rate cuts, payout reductions, incentive threshold changes
- **Seeded by:** seed_targeted_grievances.py grievances 0–10 (swiggy rate-cut set)

---

## Target: SWIGGY-DRHP-INCENTIVE-COVERAGE

- **Chunk ID:** swiggy-drhp-pXX-cY
- **Filing claim:** ← e.g. "95% of active partners received at least one incentive payment in FY24."
- **What workers contradict:** Incentive tier changed unilaterally — now 50 deliveries needed vs 35 before; many miss payout entirely
- **Grievance angle:** missing incentives, goal-post shifting
- **Seeded by:** seed_targeted_grievances.py grievances 11–14 (swiggy incentive set)

---

## Target: SWIGGY-DRHP-INSURANCE-WELFARE

- **Chunk ID:** swiggy-drhp-pXX-cY
- **Filing claim:** ← e.g. "All active delivery partners are covered under the group accident insurance scheme."
- **What workers contradict:** Insurance claims denied after road accidents; support unresponsive for weeks
- **Grievance angle:** insurance denials, accident claims rejected
- **Seeded by:** seed_targeted_grievances.py grievances 15–19 (swiggy insurance set)

---

## Target: ZOMATO-ANNUAL-REPORT-PARTNER-EARNINGS

- **Chunk ID:** zomato-annual_report-pXX-cY
- **Filing claim:** ← e.g. "Average monthly earnings per active delivery partner increased to ₹X in FY24."
- **What workers contradict:** Actual monthly take-home down ₹5k–₹8k year-on-year in Bengaluru and Mumbai despite same or more hours
- **Grievance angle:** earnings drop, more orders for less money
- **Seeded by:** seed_targeted_grievances.py grievances 20–24 (zomato earnings set)

---

## Target: ZOMATO-ANNUAL-REPORT-PARTNER-WELFARE

- **Chunk ID:** zomato-annual_report-pXX-cY
- **Filing claim:** ← e.g. "We invested ₹X crore in partner welfare initiatives including health insurance and skilling."
- **What workers contradict:** Account deactivations without notice or appeal; no grievance redressal; welfare benefits inaccessible
- **Grievance angle:** wrongful deactivation, no due process, welfare claims vs reality
- **Seeded by:** seed_targeted_grievances.py grievances 25–29 (zomato deactivation set)

---

## Target: ZOMATO-INVESTOR-CALL-PARTNER-GROWTH

- **Chunk ID:** zomato-investor_call-pXX-cY
- **Filing claim:** ← e.g. "Our delivery partner fleet is healthier than ever with strong retention metrics."
- **What workers contradict:** Partners leaving due to falling rates; high churn; those who stay work longer for less
- **Grievance angle:** retention vs reality, unsustainable conditions
- **Seeded by:** seed_targeted_grievances.py grievances 30–34 (zomato retention set)

---

## How to fill this in

1. Run `python seed/load_filings.py` — note the chunk IDs printed to stdout.
2. Open each `.txt` file in `seed/filings/text/`, search for "partner", "earnings", "rate".
3. Find a sentence with a specific number. Copy it into **Filing claim** above.
4. Note which chunk it fell into (by line count and chunk sequence) → fill the **Chunk ID**.
5. Adjust the **Seeded by** grievances if you need sharper contradictions.

Aim for 6–10 confirmed targets before the hour-9 integration call.
