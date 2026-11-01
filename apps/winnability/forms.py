from django import forms

MAX_KEYWORD_LENGTH = 100


class KeywordForm(forms.Form):
    keyword = forms.CharField(
        max_length=MAX_KEYWORD_LENGTH,
        strip=True,
        error_messages={
            "required": "Enter a keyword to check.",
            "max_length": f"Keep it under {MAX_KEYWORD_LENGTH} characters.",
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. best microphone for youtube beginners",
                "maxlength": MAX_KEYWORD_LENGTH,
                "autocomplete": "off",
            }
        ),
    )
