"""Seed surgical grievances that contradict specific filing claims.

These 35 grievances are tuned to surface contradictions in the cross-reference stage.
Each set targets one contradiction_targets.md entry. Edit the transcripts if the actual
filing claims turn out to be worded differently from what is pre-seeded here.

Run after the API server is up:
  python seed/seed_targeted_grievances.py
"""
from __future__ import annotations

import argparse

import httpx


# ---------------------------------------------------------------------------
# Grievance data
# Each dict maps directly to the TextIngestRequest schema.
# worker_secret is assigned at POST time to keep this list readable.
# ---------------------------------------------------------------------------

_GRIEVANCES: list[dict[str, str | None]] = [
    # ------------------------------------------------------------------
    # SET A: Swiggy — per-order rate cuts (targets SWIGGY-DRHP-PARTNER-EARNINGS-GROWTH)
    # ------------------------------------------------------------------
    {
        "language": "hi",
        "platform": "swiggy",
        "city_bucket": "Bengaluru Urban",
        "transcript": (
            "I am a Swiggy delivery partner in Bengaluru. I have been doing this for two years. "
            "In January this year my per-order payout was around thirty-five rupees. "
            "From March they cut it. Now I get twenty-eight rupees per order. "
            "Same distance, same petrol cost, seven rupees less. "
            "Last month I did two hundred and sixty orders and earned thirty-two thousand. "
            "Six months ago same two hundred sixty orders gave me thirty-eight thousand. "
            "Bhai, six thousand rupees less for the same work. How do I pay rent? "
            "I raised a ticket. Auto-reply. No human. This is my complaint."
        ),
        "transcript_raw": (
            "Main Bengaluru mein Swiggy pe delivery karta hoon. Do saal se hoon. "
            "January mein per order paisa tees paanch rupaye tha. March se kaata. "
            "Ab aath aath rupaye milta hai. Same doori, same petrol, saat rupaye kam. "
            "Pichle mahine do sau saath orders kiye, baatis hazaar mila. "
            "Chhe mahine pehle same orders pe athathis hazaar milta tha. "
            "Chhe hazaar rupaye kam usi kaam ke liye. Kiraya kaise bharoon? "
            "Ticket daala. Auto-reply aaya. Koi insaan nahin. Yahi meri shikayat hai."
        ),
    },
    {
        "language": "en",
        "platform": "swiggy",
        "city_bucket": "Pune",
        "transcript": (
            "Swiggy partner here from Pune. I want to talk about the rate cut that happened in March 2026. "
            "Before March my rate was thirty-four to thirty-six rupees depending on distance. "
            "After March it became twenty-seven to twenty-nine. That is almost eight rupees per order less. "
            "I do around two hundred and forty deliveries a month. "
            "So I am losing around one thousand nine hundred rupees every month. "
            "That is nearly two thousand rupees gone just because Swiggy changed a number. "
            "No notice, no explanation. I found out from another driver. "
            "My earnings fell from thirty-six thousand to thirty-two thousand for the same hours worked. "
            "The company says partner earnings are growing. They are not growing for me."
        ),
        "transcript_raw": None,
    },
    {
        "language": "hi",
        "platform": "swiggy",
        "city_bucket": "Mumbai Suburban",
        "transcript": (
            "Mumbai se bol raha hoon, Swiggy partner hoon teen saal se. "
            "Yaar, March ke baad se rate bilkul cut ho gaya. Pehle thirty-six rupaye per order milte the. "
            "Ab twenty-eight milte hain. Aath rupaye seedha kata. "
            "Main roz das ghante kaam karta hoon, lagbhag nau orders per ghanta. "
            "Matlab roughly sattar se zyada orders roz. Mahine mein do sau orders se zyada. "
            "Ab jo difference hai, usme ek mahine mein paanch hazaar rupaye straight loss hai. "
            "Pichle FY mein mera monthly average tees paaanch hazaar tha. "
            "Ab tees hazaar bhi nahi hota wahi kaam karke. "
            "Swiggy ke filing mein likha hai partner earnings bade, hamare liye ulta hai."
        ),
        "transcript_raw": (
            "Mumbai se bol raha hoon, Swiggy partner hoon teen saal se. "
            "March ke baad rate cut ho gaya. Pehle thirty-six rupaye per order. Ab twenty-eight. "
            "Aath rupaye kata. Roz das ghante, nau orders per ghanta. "
            "Mahine mein paanch hazaar straight loss. Pichle FY mein taintis hazaar average. "
            "Ab tees hazaar bhi nahin. Filing mein likha earnings bade. Hamare liye ulta."
        ),
    },
    {
        "language": "en",
        "platform": "swiggy",
        "city_bucket": "Hyderabad",
        "transcript": (
            "I am calling from Hyderabad. I work for Swiggy. "
            "My per-order earnings dropped from thirty-five rupees to twenty-eight rupees after March. "
            "I work about two hundred and eighty orders a month, sometimes three hundred. "
            "My take-home used to be around thirty-eight thousand to forty thousand rupees. "
            "Now the same three hundred orders gives me thirty-one to thirty-two thousand only. "
            "That is almost seven to eight thousand rupees difference. "
            "My family has four people. I cannot manage on this cut. "
            "I reported this to Swiggy support three times. Each time closed automatically after two days. "
            "No resolution. No explanation for why the rate changed."
        ),
        "transcript_raw": None,
    },
    {
        "language": "hi",
        "platform": "swiggy",
        "city_bucket": "Delhi",
        "transcript": (
            "Bhai main Delhi se Swiggy pe kaam karta hoon. Paanch saal ho gaye. "
            "Rate cut toh hoti rehti hai lekin March wali bahut badi thi. "
            "Ek dum se saat rupaye per delivery cut ho gaye. Thirty-five se twenty-eight. "
            "Ek mahine mein main do sau pachaas se teen sau deliveries karta hoon. "
            "Matlab seedha chhah se saat hazaar rupaye mahine mein chale gaye. "
            "Pehle mujhe taintis chounitis hazaar milte the. Ab saathe baar pachhattis se kam. "
            "Koi notice nahin aaya. Ek din khula app, rate badal gayi thi. "
            "Swiggy bolte hain partner earnings grow kar rahi hai. "
            "Mere liye toh sirf cut ho rahi hai."
        ),
        "transcript_raw": (
            "Delhi se Swiggy pe kaam karta hoon. Paanch saal. "
            "March mein saat rupaye per delivery cut. Taintis se baais. "
            "Teen sau deliveries mahine mein. Chhah saat hazaar kam. "
            "Pehle chounitis milte the. Ab pachhattis se bhi kam. "
            "Notice nahin aaya. Earnings grow nahin, cut ho rahi hai."
        ),
    },
    {
        "language": "en",
        "platform": "swiggy",
        "city_bucket": "Chennai",
        "transcript": (
            "This is a Swiggy delivery partner from Chennai. "
            "I want to report the earnings drop I have seen since early 2026. "
            "In December 2025 I was earning approximately thirty-seven to thirty-nine thousand rupees monthly. "
            "After the per-order rate was reduced in March, my earnings fell to thirty-one thousand. "
            "I work the same hours, same area, same number of deliveries — roughly two hundred and fifty a month. "
            "The per-order rate went from thirty-five rupees to twenty-eight rupees. "
            "Seven rupees times two hundred and fifty is one thousand seven hundred and fifty rupees per month less. "
            "Plus with petrol costs up, my actual take-home dropped by nearly eight thousand rupees. "
            "I have not seen any official communication from Swiggy about this change."
        ),
        "transcript_raw": None,
    },
    # ------------------------------------------------------------------
    # SET B: Swiggy — incentive threshold change (targets SWIGGY-DRHP-INCENTIVE-COVERAGE)
    # ------------------------------------------------------------------
    {
        "language": "hi",
        "platform": "swiggy",
        "city_bucket": "Bengaluru Urban",
        "transcript": (
            "Swiggy ka incentive system pehle alag tha. Main Bengaluru mein hoon. "
            "Pehle paanch sau rupaye ka bonus milta tha agar main pachhattis orders karta tha week mein. "
            "Ab same bonus ke liye pachaas orders chahiye. Fifteen orders zyada. "
            "Main achha din pe bhi chalis orders karta hoon mushkil se. "
            "Toh ek bhi incentive nahin mila pichle teen mahine se. "
            "Pehle main har hafte bonus le leta tha. Mahine mein do do hazaar extra aata tha. "
            "Ab zero. Swiggy bolte hain most partners ko incentive milta hai. "
            "Mujhe toh nahin milta. Mere saare jaanne waalon ko bhi nahin mil raha."
        ),
        "transcript_raw": (
            "Swiggy incentive pehle pachhattis orders pe milta tha. Ab pachaas chahiye. "
            "Main chalis se zyada nahin kar sakta. Teen mahine se zero bonus. "
            "Pehle mahine mein do hazaar extra aata tha. Ab nahin. "
            "Most partners ko milta hai bolte hain. Mujhe nahin milta."
        ),
    },
    {
        "language": "en",
        "platform": "swiggy",
        "city_bucket": "Ahmedabad",
        "transcript": (
            "I am a Swiggy delivery partner in Ahmedabad. "
            "Earlier this year, the weekly bonus target was thirty-five orders for five hundred rupees. "
            "I was hitting this almost every week. Getting roughly two thousand rupees bonus per month. "
            "From April the threshold changed to fifty orders per week for the same five hundred rupees bonus. "
            "I cannot do fifty orders in six or seven hours of work. It is not physically possible. "
            "So now I get zero bonus. My total monthly income dropped by two thousand rupees overnight. "
            "No notification was sent. I discovered it when I checked my payout summary. "
            "Swiggy talks about incentive coverage for partners. My incentive coverage is now zero."
        ),
        "transcript_raw": None,
    },
    {
        "language": "hi",
        "platform": "swiggy",
        "city_bucket": "Kolkata",
        "transcript": (
            "Kolkata se hoon, Swiggy pe kaam karta hoon. Incentive ka issue hai. "
            "Pehle weekly target thirty-five orders tha. Paanch sau rupaye milte the bonus mein. "
            "Febraury mein kuch notification aaya achanak. Target fifty ho gaya. "
            "Bhai, fifty orders ek hafte mein? Matlab roz saat orders. "
            "Main shaam ko part time karta hoon, itna nahin hota. "
            "Toh incentive band ho gaya mere liye. Do hazaar rupaye mahine mein chale gaye. "
            "Yahi problem hai — company filing mein kuch aur dikhate hain, "
            "hamare haath mein kuch aur aata hai."
        ),
        "transcript_raw": (
            "Kolkata se hoon. Incentive target thirty-five se fifty ho gaya. "
            "Part time karta hoon, fifty nahin hota. Do hazaar rupaye band. "
            "Filing mein kuch dikhate, haath mein kuch aata."
        ),
    },
    {
        "language": "en",
        "platform": "swiggy",
        "city_bucket": "Pune",
        "transcript": (
            "Swiggy partner from Pune speaking. "
            "The incentive structure changed in early 2026 without proper notice. "
            "Earlier I needed thirty-five deliveries a week to get the five hundred rupee bonus. "
            "Now the minimum is fifty deliveries for the same amount. "
            "That is a forty-three percent increase in work for the same reward. "
            "I asked three other Swiggy partners in my area. Same story for all of us. "
            "We are all missing the bonus now that we used to get before. "
            "My monthly income dropped by around one thousand eight hundred to two thousand rupees "
            "just because of this one change. No email, no in-app message explaining it."
        ),
        "transcript_raw": None,
    },
    # ------------------------------------------------------------------
    # SET C: Swiggy — insurance claim denials (targets SWIGGY-DRHP-INSURANCE-WELFARE)
    # ------------------------------------------------------------------
    {
        "language": "hi",
        "platform": "swiggy",
        "city_bucket": "Delhi",
        "transcript": (
            "Main Delhi mein Swiggy delivery karta hoon. Accident ho gaya February mein. "
            "Bike aur ek car ke beech hua. Hospital mein teen din raha. "
            "Bill aaya saath hazaar rupaye. Maine insurance claim daala Swiggy ke through. "
            "Pehle bolte the processing mein hai. Phir bolte the documents chahiye. "
            "Phir bolte the yeh incident covered nahin hai. "
            "Koi reason nahin bataya. Sirf rejection. "
            "Saath hazaar rupaye khud se bharne pade. "
            "Swiggy kahte hain sab partners covered hain. "
            "Mere case mein toh kuch kaam nahin aaya insurance."
        ),
        "transcript_raw": (
            "Delhi mein accident February mein. Teen din hospital. Saath hazaar bill. "
            "Swiggy insurance claim daala. Rejection mili. Reason nahin bataya. "
            "Khud se bharna pada. Partners covered hain bolte hain. Mere liye nahin."
        ),
    },
    {
        "language": "en",
        "platform": "swiggy",
        "city_bucket": "Mumbai Suburban",
        "transcript": (
            "I am a Swiggy delivery partner from Mumbai. I had an accident while on a delivery in January. "
            "A car hit my bike near Andheri. I had a fracture in my wrist. "
            "Hospital bills came to around nine thousand rupees. "
            "I filed an insurance claim through the Swiggy app on the same day as the accident. "
            "After three weeks they rejected my claim. "
            "The reason given was that the injury documentation was insufficient. "
            "I submitted everything the hospital gave me. X-rays, discharge summary, bills. "
            "Still rejected. I had to borrow money to pay the hospital. "
            "Swiggy says all active partners have accident insurance coverage. "
            "This claim denial tells a different story."
        ),
        "transcript_raw": None,
    },
    {
        "language": "hi",
        "platform": "swiggy",
        "city_bucket": "Hyderabad",
        "transcript": (
            "Hyderabad se baat kar raha hoon. Swiggy partner hoon. "
            "March mein delivery ke dauran road accident hua. Leg mein injury. "
            "Do hafte kaam nahin kar saka. Hospital kharch aaya das hazaar. "
            "Insurance claim submit kiya. Pehle ek hafte tak koi response nahin. "
            "Phir ek message aaya claim rejected. "
            "Unhone kaha active delivery ke time ka proof nahin hai. "
            "Bhai, app mein toh order accept kiya tha, track bhi hua, proof kya chahiye aur? "
            "Woh das hazaar khud se bharne pade. Plus do hafte mein koi earning nahin. "
            "Yeh hai unka partner welfare program."
        ),
        "transcript_raw": (
            "Hyderabad. Swiggy. March mein accident. Do hafte kaam nahin. Das hazaar kharch. "
            "Insurance claim reject. Active delivery proof maanga. Order app mein tha phir bhi reject. "
            "Das hazaar khud se. Do hafte earning zero. Yeh hai welfare program."
        ),
    },
    {
        "language": "en",
        "platform": "swiggy",
        "city_bucket": "Bengaluru Urban",
        "transcript": (
            "Swiggy delivery partner from Bengaluru. "
            "I had a slip and fall accident on stairs while delivering in February. "
            "Sprained ankle, had to rest for ten days. Medical cost was around four thousand rupees. "
            "I applied for the insurance claim. Got auto-rejected after five days. "
            "No human reviewed it as far as I can tell. "
            "The rejection said the incident type was not covered under the policy. "
            "Nobody told me which incident types are actually covered. "
            "I lost four thousand rupees in medical bills plus ten days of earnings, "
            "roughly eight thousand rupees in lost income. "
            "The company literature says all partners are insured. "
            "My experience says the insurance does not actually work."
        ),
        "transcript_raw": None,
    },
    {
        "language": "hi",
        "platform": "swiggy",
        "city_bucket": "Chennai",
        "transcript": (
            "Chennai se hoon, Swiggy pe ek saal se kaam kar raha hoon. "
            "Bike ki side mein ek auto ne maara delivery ke time. "
            "Hath mein chot lagi. X-ray karana pada. Bill terah sau rupaye. "
            "Insurance claim kiya app se. Teen din baad automatically close ho gaya. "
            "Koi message nahin, koi call nahin. Claim hi close. "
            "Phir se daala. Same cheez. Phir close. "
            "Terah sau rupaye khud se bharne pade. "
            "Ek partner ne bataya ki uska bhi same hua. "
            "Swiggy ka brochure kehta hai hum sab covered hain."
        ),
        "transcript_raw": (
            "Chennai. Swiggy. Auto ne maara. Hath mein chot. Terah sau bill. "
            "Claim daala. Auto-close. Phir daala. Phir close. "
            "Khud se bhara. Brochure mein covered hain. Reality mein nahin."
        ),
    },
    # ------------------------------------------------------------------
    # SET D: Zomato — partner earnings drop (targets ZOMATO-ANNUAL-REPORT-PARTNER-EARNINGS)
    # ------------------------------------------------------------------
    {
        "language": "en",
        "platform": "zomato",
        "city_bucket": "Bengaluru Urban",
        "transcript": (
            "I am a Zomato delivery partner in Bengaluru. Two years on the platform. "
            "I want to talk about how my earnings have changed over the past year. "
            "In March 2025 my monthly earnings were around thirty-six to thirty-eight thousand rupees. "
            "I was working about two hundred and twenty to two hundred and forty hours a month. "
            "By March 2026, same hours, same area, my earnings dropped to twenty-nine to thirty-one thousand. "
            "That is roughly six to seven thousand rupees less per month for the same work. "
            "My petrol costs went up in the same period. My net income dropped even more. "
            "Zomato's annual report talks about partner earnings improving. "
            "For me earnings have not improved. They have fallen."
        ),
        "transcript_raw": None,
    },
    {
        "language": "hi",
        "platform": "zomato",
        "city_bucket": "Mumbai Suburban",
        "transcript": (
            "Mumbai se baat kar raha hoon, Zomato pe kaam karta hoon. "
            "Do saal pehle main mahine mein pachhattis hazar rupaye kamaata tha. "
            "Same kaam, same area. Ab taintis hazaar bhi nahin hota. "
            "Lekin kaam kam nahin hua. Mahine mein do sau orders se zyada karta hoon. "
            "Per order rate kam ho gaya hai. Pehle thirty-two rupaye milte the. "
            "Ab twenty-six twenty-seven. Paaanch rupaye per order cut. "
            "Do sau orders pe ek hazaar rupaye straight loss. "
            "Zomato bolte hain earnings badh rahi hai. Meri toh ghat rahi hai."
        ),
        "transcript_raw": (
            "Mumbai. Zomato. Do saal pehle pachhattis hazaar. Ab taintis se bhi kam. "
            "Do sau orders. Per order rate thirty-two se twenty-six. "
            "Ek hazaar rupaye loss per mahina. Earnings badh rahi hai bolte hain. Ghat rahi hai."
        ),
    },
    {
        "language": "en",
        "platform": "zomato",
        "city_bucket": "Delhi",
        "transcript": (
            "Zomato partner calling from Delhi. Three years on the app. "
            "My monthly income in FY2024-25 was consistently between thirty-four and thirty-seven thousand. "
            "By the first quarter of 2026, it had dropped to twenty-eight to thirty thousand. "
            "I have not reduced my working hours. I still do eight to nine hours a day, six days a week. "
            "The per-order base pay dropped. The surge frequency dropped. "
            "My total hours worked is the same but my pay is lower. "
            "I read somewhere that Zomato reported average partner earnings increased. "
            "I do not know which partner they are talking about. Certainly not me or anyone I know."
        ),
        "transcript_raw": None,
    },
    {
        "language": "hi",
        "platform": "zomato",
        "city_bucket": "Hyderabad",
        "transcript": (
            "Hyderabad se hoon. Zomato delivery partner. Teen saal ka experience. "
            "FY24 mein mera average mahina taintis chounitis hazaar tha. "
            "Abhi same kaam, same orders, mila sirf aath aath is baar. "
            "Seedha chhe hazaar ka difference sirf is liye ki per order rate kam ho gaya. "
            "Pehle thirty rupaye per base order tha. Ab twenty-four twenty-five. "
            "Nahin yaar, yeh sahi nahin hai. Zomato report mein earnings improve hua bolte hain. "
            "Apne partners se poochhein toh sach pata chalega."
        ),
        "transcript_raw": (
            "Hyderabad. Zomato. Teen saal. FY24 mein chounitis hazaar. Ab aath aath. "
            "Chhe hazaar difference. Per order thirty se chaubis. "
            "Report mein improve bolte hain. Partners se poochhein sach pata chalega."
        ),
    },
    {
        "language": "en",
        "platform": "zomato",
        "city_bucket": "Pune",
        "transcript": (
            "Zomato delivery partner from Pune. I have been doing this for eighteen months. "
            "When I started in mid-2024 my monthly earnings were around thirty thousand rupees. "
            "I was working around two hundred hours a month. "
            "Now in early 2026, two hundred hours gives me around twenty-four thousand. "
            "That is six thousand less. Petrol went up by about twelve hundred rupees in the same period. "
            "So my actual net take-home is down by more than seven thousand rupees. "
            "Zomato says partner incomes are growing. "
            "My income is shrinking even though I have more experience and work the same hours."
        ),
        "transcript_raw": None,
    },
    # ------------------------------------------------------------------
    # SET E: Zomato — wrongful deactivations (targets ZOMATO-ANNUAL-REPORT-PARTNER-WELFARE)
    # ------------------------------------------------------------------
    {
        "language": "hi",
        "platform": "zomato",
        "city_bucket": "Bengaluru Urban",
        "transcript": (
            "Main Bengaluru mein Zomato partner tha. Tha — kyunki abhi account band hai. "
            "Ek din achanak app ne mujhe login nahin karne diya. "
            "Koi message nahin, koi email nahin, koi warning nahin. "
            "Support se contact kiya. Usne kaha account review mein hai. "
            "Teen hafte ho gaye, ab bhi review mein hai. Mere paas koi income nahin. "
            "Mujhe nahin pata kya galat hua. Koi specific reason nahin diya. "
            "Zomato ki report mein partner welfare aur due process likha hoga. "
            "Mere case mein toh na process tha, na welfare."
        ),
        "transcript_raw": (
            "Bengaluru. Zomato account band. Koi message nahin. Login nahin hota. "
            "Support: review mein hai. Teen hafte. Income nahin. Reason nahin. "
            "Report mein due process likha. Mere case mein nahin tha."
        ),
    },
    {
        "language": "en",
        "platform": "zomato",
        "city_bucket": "Mumbai Suburban",
        "transcript": (
            "I am a Zomato delivery partner from Mumbai, or I was until last month. "
            "My account was deactivated without any prior warning. "
            "I woke up one morning and could not log in. No SMS, no email, nothing. "
            "I called Zomato support. They said my account was under review for policy violation. "
            "They would not tell me which policy or what I allegedly did. "
            "I had four-point-six star rating. No complaints from customers in recent months. "
            "After two weeks they said the deactivation was confirmed. No appeal option explained. "
            "I have two children. I was out of income for three weeks while this dragged on. "
            "Zomato's annual report mentions a robust grievance redressal mechanism for partners. "
            "That mechanism did not work for me."
        ),
        "transcript_raw": None,
    },
    {
        "language": "hi",
        "platform": "zomato",
        "city_bucket": "Delhi",
        "transcript": (
            "Delhi se hoon. Zomato pe aadhe saal kaam kiya. "
            "Phir ek din bina kisi warning ke account deactivate ho gaya. "
            "Reason: policy violation. Kaunsi policy? Unhone nahin bataya. "
            "Rating check kiya — char point saat tha. Customer complaint? Nahi. "
            "Support ne kaha investigation mein hai. Ek mahina wait karo. "
            "Ek mahina baad bola: permanent deactivation. "
            "Koi explanation nahin. Appeal ka option nahin diya. "
            "Is dauraan ek mahine ki earnings gayi. "
            "Company kehti hai partners ke saath fair process hota hai. "
            "Fair process mujhe dikhaa to dena."
        ),
        "transcript_raw": (
            "Delhi. Zomato. Chhe mahine kaam. Ek din deactivate. Reason: policy violation. Kaunsi? Nahin bataya. "
            "Rating char.saat. Complaint nahin. Ek mahine baad permanent deactivation. "
            "Appeal nahin. Ek mahine earnings gayi. Fair process dikhaa."
        ),
    },
    {
        "language": "en",
        "platform": "zomato",
        "city_bucket": "Chennai",
        "transcript": (
            "Zomato partner from Chennai. I want to report an unfair deactivation. "
            "My account was suspended in February with no warning. "
            "When I contacted support they said I had received too many cancellations. "
            "But I checked my stats — my cancellation rate was four percent. "
            "The app itself shows the acceptable threshold as ten percent. "
            "My rate was well within policy. Still deactivated. "
            "I sent three emails explaining this with screenshots. No response for two weeks. "
            "Then a standard rejection email. No human reviewed my case. "
            "Zomato talks about partner welfare initiatives in their public filings. "
            "A welfare initiative would have included reviewing my case before deactivating me."
        ),
        "transcript_raw": None,
    },
    {
        "language": "hi",
        "platform": "zomato",
        "city_bucket": "Kolkata",
        "transcript": (
            "Kolkata se baat kar raha hoon. Zomato partner tha. "
            "March mein account suspend ho gaya. Reason kuch bhi nahin diya clear. "
            "App pe sirf likha tha: account suspended. "
            "Support se poochha. Unhone kaha: incident investigation. "
            "Kaunsa incident? Nahin pata. Teen hafte baad bola permanently closed. "
            "Aaj bhi nahin pata kya galat hua. "
            "Ek chhote bhai ko bhi yahi hua pichle mahine. Same process. "
            "Company wellness report mein kya likha hoga? "
            "Hamare liye toh support ka matlab auto-rejection hai."
        ),
        "transcript_raw": (
            "Kolkata. Zomato suspend March mein. Reason nahin. Investigation. "
            "Teen hafte baad permanent. Kya hua nahin pata. "
            "Chhote bhai ka bhi same. Wellness report mein kuch bhi likho. "
            "Hamare liye auto-rejection hai."
        ),
    },
    # ------------------------------------------------------------------
    # SET F: Zomato — retention / conditions (targets ZOMATO-INVESTOR-CALL-PARTNER-GROWTH)
    # ------------------------------------------------------------------
    {
        "language": "en",
        "platform": "zomato",
        "city_bucket": "Bengaluru Urban",
        "transcript": (
            "I have been a Zomato delivery partner in Bengaluru for three years. "
            "I can tell you that many of my colleagues have left the platform in the past six months. "
            "In my usual pickup area I know about fifteen partners personally. "
            "At least six of them have switched to other platforms or gone back to their hometowns. "
            "The reason is simple — the money is not there anymore. "
            "We earn less per order than we did a year ago. The surge pricing has reduced. "
            "Food costs went up for us too. Petrol is expensive. The maths does not work. "
            "Zomato told investors that partner retention is strong. "
            "Come to Bengaluru and see which partners are still here from a year ago."
        ),
        "transcript_raw": None,
    },
    {
        "language": "hi",
        "platform": "zomato",
        "city_bucket": "Hyderabad",
        "transcript": (
            "Hyderabad se hoon, Zomato pe hoon. Mere aas paas ke drivers mein se kaafi chale gaye. "
            "Pichle chhe mahine mein mere jaane paehchhane das mein se chaar ne platform chhod diya. "
            "Sab ek hi baat bolte hain — paise nahin ban rahe. "
            "Per order rate giri hai. Surge kam hua hai. Petrol mehnga ho gaya. "
            "Ek banda apni native pe wapas gaya kyunki Hyderabad mein afford nahin ho raha tha. "
            "Main bhi soch raha hoon chhod doon. Teen saal se hoon lekin ab sustainable nahin hai. "
            "Investor call mein company bolti hai retention strong hai. "
            "Jo log reh gaye hain woh bhi bahut frustrated hain."
        ),
        "transcript_raw": (
            "Hyderabad. Zomato. Das mein se chaar chale gaye chhe mahine mein. "
            "Per order rate giri. Surge kam. Petrol mehnga. "
            "Main bhi soch raha hoon. Teen saal se hoon. Sustainable nahin. "
            "Retention strong bolte hain. Jo hain woh frustrated hain."
        ),
    },
    {
        "language": "en",
        "platform": "zomato",
        "city_bucket": "Ahmedabad",
        "transcript": (
            "Zomato partner from Ahmedabad. I have noticed significant attrition among partners here. "
            "The partner WhatsApp group I am in started with forty-two members from our zone. "
            "Now only twenty-six remain active. The rest either quit or switched to competitors. "
            "The main reason is that earnings per hour have dropped. "
            "A year ago I would earn around one hundred and sixty rupees per hour net. "
            "Now it is closer to one hundred and twenty. That is a forty rupee per hour drop. "
            "Over a two-hundred-hour month that is eight thousand rupees less per month. "
            "The company claims partner fleet is growing and healthy. "
            "The people I know are leaving, and those staying are earning less."
        ),
        "transcript_raw": None,
    },
    {
        "language": "hi",
        "platform": "zomato",
        "city_bucket": "Pune",
        "transcript": (
            "Pune se hoon. Zomato partner hoon do saal se. "
            "Mere zone mein bahut saare log platform chhod rahe hain. "
            "Earnings per hour pehle ek sau sattar rupaye the. "
            "Ab ek sau bees rupaye bhi mushkil se hote hain. "
            "Pachaas rupaye per ghante ka difference. "
            "Do sau ghante mahine mein matlab das hazaar rupaye kam. "
            "Koi bhi isiliye nahin chhod raha ki unhein koi aur cheez mili. "
            "Chhod rahe hain kyunki Zomato pe rehna ghate ka sauda ho gaya hai. "
            "Investor presentation mein bolte hain partner satisfaction high hai. "
            "Hamaara satisfaction? Zero hai."
        ),
        "transcript_raw": (
            "Pune. Zomato. Do saal. Per hour ek sau sattar se ek sau bees. "
            "Pachaas rupaye per ghanta kam. Das hazaar per mahina. "
            "Log isliye chhod rahe hain ki ghate ka sauda ho gaya. "
            "Partner satisfaction high bolte hain. Hamaara zero."
        ),
    },
    {
        "language": "en",
        "platform": "zomato",
        "city_bucket": "Kolkata",
        "transcript": (
            "I am a Zomato delivery partner in Kolkata. Four years on the platform. "
            "Four years ago I was making decent money. Around thirty-two to thirty-four thousand a month. "
            "Now I barely cross twenty-six thousand. The per-order rate has been cut multiple times. "
            "Long-distance orders that used to pay well now pay the same as short ones. "
            "Peak hour surges are smaller and rarer. My effective hourly rate has dropped by about thirty percent. "
            "I have stayed because I do not have a better option right now. "
            "But three of my closest colleagues who were on Zomato quit in the last year. "
            "Zomato said in their last investor call that partner metrics are the best they have ever been. "
            "I have four years of experience and I am earning less than I did in year one."
        ),
        "transcript_raw": None,
    },
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed surgical targeted grievances into the API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    base_url = args.base_url.rstrip("/")

    with httpx.Client(timeout=30.0) as client:
        health = client.get(f"{base_url}/health")
        health.raise_for_status()

        for index, grievance in enumerate(_GRIEVANCES):
            payload = {
                "worker_secret": f"synthetic-targeted-{index}",
                "language": grievance["language"],
                "transcript": grievance["transcript"],
                "transcript_raw": grievance.get("transcript_raw"),
                "city_bucket": grievance["city_bucket"],
                "platform": grievance["platform"],
                "source": "synthetic",
            }
            response = client.post(f"{base_url}/ingest/text", json=payload)
            response.raise_for_status()
            data = response.json()
            print(f"Inserted targeted grievance {index + 1}/{len(_GRIEVANCES)}  id={data['id']}  platform={grievance['platform']}")

    print(f"\nDone. {len(_GRIEVANCES)} surgical grievances loaded.")
    print("These are tuned to surface contradictions against the filing chunks.")
    print("Edit _GRIEVANCES in this file after reading the actual filing documents.")


if __name__ == "__main__":
    main()
