import pytest

from app.ingestion.cleaner import clean_text


@pytest.mark.parametrize(
    "raw, want",
    [
        ("Haaaaan bhaiii", "haan bhai"),
        ("kb aayega? nhi pata", "kab aayega? nahi pata"),
        ("Kl milte hain, hn?", "kal milte hain, haan?"),
        ("check https://x.com/a?b=1 now", "check <url> now"),
        ("call +91 98765 43210 asap", "call <phone> asap"),
        ("₹5000 by 20/11 at 5:30", "₹5000 by 20/11 at 5:30"),
        ("done 👍", "done thumbs up"),
        ("ｆｕｌｌ   width", "full width"),
    ],
)
def test_clean_text(raw, want):
    assert clean_text(raw) == want


def test_variant_inside_longer_word_untouched():
    # "kb" is a variant of "kab", but "kbps" must not change
    assert clean_text("speed 10 kbps") == "speed 10 kbps"
