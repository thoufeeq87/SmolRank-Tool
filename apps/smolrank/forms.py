from django import forms


class KeywordForm(forms.Form):
    keyword = forms.CharField(max_length=100, strip=True, label="YouTube keyword")
