from django import forms


class EmailLoginForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        error_messages={
            "required": "Enter your email address.",
            "invalid": "Enter a valid email address.",
        },
        widget=forms.EmailInput(
            attrs={"placeholder": "you@example.com", "autocomplete": "email", "autofocus": True}
        ),
    )
