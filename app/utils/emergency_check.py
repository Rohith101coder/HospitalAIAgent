import re
from typing import Tuple
from app.core.config import settings

# Keyword lists for emergency detection across languages
EMERGENCY_KEYWORDS_ENGLISH = [
    r"\bchest\s+pain\b",
    r"\bheart\s+attack\b",
    r"\bsevere\s+(?:breathing\s+difficulty|shortness\s+of\s+breath|difficulty\s+breathing)\b",
    r"\bcan'?t\s+breathe\b",
    r"\bunconscious(?:ness)?\b",
    r"\bpassed\s+out\b",
    r"\bheavy\s+bleeding\b",
    r"\bprofuse\s+bleeding\b",
    r"\bstroke\b",
    r"\bsevere\s+allergic\s+reaction\b",
    r"\banaphylaxis\b",
    r"\bseizure\b",
    r"\bconvulsion\b",
    r"\bcoughing\s+blood\b",
    r"\bvomiting\s+blood\b",
    r"\bhead\s+trauma\b",
    r"\boverdose\b",
]

EMERGENCY_KEYWORDS_TELUGU = [
    r"ఛాతీ\s*నొప్పి",
    r"తీవ్రమైన\s*ఛాతీ\s*నొప్పి",
    r"గుండెపోటు",
    r"గుండె\s*నొప్పి",
    r"శ్వాస\s*తీసుకోవడంలో\s*ఇబ్బంది",
    r"శ్వాస\s*ఆడటం\s*లేదు",
    r"స్పృహ\s*తప్పడం",
    r"స్పృహ\s*కోల్పోవడం",
    r"రక్తం\s*కారడం",
    r"రక్తస్రావం",
    r"ఫిట్స్",
]

EMERGENCY_KEYWORDS_TELUGU_TRANSLIT = [
    r"\bchati\s+noppi\b",
    r"\bchaathi\s+noppi\b",
    r"\bgunde\s+potu\b",
    r"\bgunde\s+noppi\b",
    r"\bshwasa\s+aadtam\s+ledu\b",
    r"\bshwasa\s+ibbandi\b",
    r"\bspruha\s+tappadam\b",
    r"\braktam\s+karadam\b",
]

EMERGENCY_KEYWORDS_HINDI = [
    r"सीने\s*में\s*(?:तेज़|तेज)?\s*दर्द",
    r"दिल\s*का\s*दौरा",
    r"सांस\s*लेने\s*में\s*(?:गंभीर\s*)?परेशानी",
    r"सांस\s*नहीं\s*आ\s*रही",
    r"बेहोश(?:ी)?",
    r"भारी\s*रक्तस्राव",
    r"खून\s*बह\s*रहा",
    r"दौरा\s*पड़ना",
]

EMERGENCY_KEYWORDS_HINDI_TRANSLIT = [
    r"\bseene\s+me(?:in)?\s+dard\b",
    r"\bchhati\s+me(?:in)?\s+dard\b",
    r"\bdil\s+ka\s+daura\b",
    r"\bsaans\s+lene\s+me(?:in)?\s+pareshani\b",
    r"\bsaans\s+nahi\s+aa\s+rahi\b",
    r"\bbehosh(?:i)?\b",
    r"\bkhoon\s+beh\s+raha\b",
]


def detect_emergency(text: str) -> Tuple[bool, str, str]:
    """
    Check if user input describes an immediate medical emergency.
    
    LIMITATION NOTE:
    This function uses rule-based keyword pattern matching and is NOT
    a clinically validated triage system. It is designed to immediately divert
    patients to emergency phone services and emergency rooms.
    
    Returns:
        (is_emergency: bool, language: str, emergency_message: str)
    """
    clean_text = text.lower().strip()
    emergency_num = settings.EMERGENCY_NUMBER or "108 / 112"

    # Check Telugu script
    for pattern in EMERGENCY_KEYWORDS_TELUGU:
        if re.search(pattern, clean_text):
            msg = (
                f"🚨 **అత్యవసర హెచ్చరిక!**\n\n"
                f"మీరు అత్యవసర వైద్య పరిస్థితిని ఎదుర్కొంటున్నట్లు కనిపిస్తోంది. "
                f"దయచేసి తక్షణమే అత్యవసర సేవలు **{emergency_num}** కు కాల్ చేయండి లేదా సమీపంలోని ఎమర్జెన్సీ ఆసుపత్రికి వెళ్లండి. "
                f"చాట్ ద్వారా అపాయింట్‌మెంట్ తీసుకోవడం సరిపోదు. మీ ప్రాణ రక్షణ మొదటి ప్రాధాన్యత!"
            )
            return True, "te", msg

    # Check Telugu transliteration
    for pattern in EMERGENCY_KEYWORDS_TELUGU_TRANSLIT:
        if re.search(pattern, clean_text):
            msg = (
                f"🚨 **Atyavasara Hecharika (Emergency Alert)!**\n\n"
                f"Meeru atyavasara vaidya paristhithini edurukuntunnaru. "
                f"Dayachesi ventane emergency number **{emergency_num}** ki call cheyandi leda daggaraloni hospital emergency room ki vellandi. "
                f"Chat appointment book cheyadam saripodu. Ventane emergency sahayanni pondandi!"
            )
            return True, "te", msg

    # Check Hindi script
    for pattern in EMERGENCY_KEYWORDS_HINDI:
        if re.search(pattern, clean_text):
            msg = (
                f"🚨 **आपातकालीन चेतावनी (Emergency Alert)!**\n\n"
                f"ऐसा प्रतीत होता है कि आप एक आपातकालीन चिकित्सा स्थिति का सामना कर रहे हैं। "
                f"कृपया तुरंत आपातकालीन नंबर **{emergency_num}** पर कॉल करें या निकटतम अस्पताल के आपातकालीन विभाग में जाएं। "
                f"चैटबॉट से अपॉइंटमेंट बुक करने का इंतज़ार न करें। आपकी सुरक्षा अत्यंत महत्वपूर्ण है!"
            )
            return True, "hi", msg

    # Check Hindi transliteration
    for pattern in EMERGENCY_KEYWORDS_HINDI_TRANSLIT:
        if re.search(pattern, clean_text):
            msg = (
                f"🚨 **Aapatkaleen Chetwani (Emergency Alert)!**\n\n"
                f"Aisa lagta hai ki yeh ek medical emergency hai. "
                f"Kripya turant emergency number **{emergency_num}** par call karein ya paas ke hospital emergency room mein jayein. "
                f"Chat par appointment book karne ka intezar na karein. Turant doctori sahayata lein!"
            )
            return True, "hi", msg

    # Check English
    for pattern in EMERGENCY_KEYWORDS_ENGLISH:
        if re.search(pattern, clean_text):
            msg = (
                f"🚨 **CRITICAL MEDICAL EMERGENCY DETECTED!**\n\n"
                f"Your symptoms require immediate, urgent medical attention. "
                f"Please call emergency services at **{emergency_num}** right away or proceed immediately to the nearest hospital Emergency Room.\n\n"
                f"Do not wait for a scheduled appointment. Hospital staff are available 24/7 in the ER."
            )
            return True, "en", msg

    return False, "en", ""

