Draft three markdown artefacts from the synthesis data.

Voice and structure requirements:
- Plain language, active voice, short lines.
- Avoid corporate phrases: leverage, robust, comprehensive.
- Demand list ranks by supporter count, descending.
- Exclude demands with fewer than 20 supporters.
- Mark themes with supporter count 20-30 as "emerging".
- Press release leads with strongest contradiction if one exists.

Return strict JSON only with exactly these keys:
{
  "demand_list": "# Demand List\\n...",
  "press_release": "# Press Release\\n...",
  "brief": "# Negotiation Brief\\n..."
}

Input synthesis packet:
<<SYNTHESIS_PACKET_JSON>>