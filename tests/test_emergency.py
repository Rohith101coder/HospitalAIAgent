from app.utils.emergency_check import detect_emergency


def test_emergency_detection_english():
    # Emergency sentences
    is_em, lang, msg = detect_emergency("I am having severe chest pain right now")
    assert is_em is True
    assert lang == "en"
    assert "EMERGENCY" in msg

    is_em, lang, msg = detect_emergency("Help, I think he is having a heart attack!")
    assert is_em is True

    is_em, lang, msg = detect_emergency("Patient has heavy bleeding and can't breathe")
    assert is_em is True

    # Non-emergency
    is_em, _, _ = detect_emergency("I want an appointment with a cardiologist tomorrow morning")
    assert is_em is False


def test_emergency_detection_telugu():
    # Telugu script
    is_em, lang, msg = detect_emergency("నాకు తీవ్రమైన ఛాతీ నొప్పి వస్తోంది")
    assert is_em is True
    assert lang == "te"

    # Telugu transliteration
    is_em, lang, msg = detect_emergency("Naaku chaathi noppi ga undi ventane help kavali")
    assert is_em is True
    assert lang == "te"

    # Non-emergency Telugu
    is_em, _, _ = detect_emergency("నాకు గుండె డాక్టర్ అపాయింట్మెంట్ కావాలి")
    assert is_em is False


def test_emergency_detection_hindi():
    # Hindi script
    is_em, lang, msg = detect_emergency("सीने में तेज दर्द हो रहा है")
    assert is_em is True
    assert lang == "hi"

    # Hindi transliteration
    is_em, lang, msg = detect_emergency("Mujhe seene me dard ho raha hai please help")
    assert is_em is True
    assert lang == "hi"

    # Non-emergency Hindi
    is_em, _, _ = detect_emergency("Mujhe kal doctor se appointment lena hai")
    assert is_em is False

