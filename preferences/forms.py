from django import forms

from .models import PreferenceWindow


class PreferenceWindowForm(forms.ModelForm):
    class Meta:
        model = PreferenceWindow
        fields = ["academic_term", "opens_at", "deadline", "closed_manually"]
        widgets = {
            "opens_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "deadline": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class PreferenceSubmissionForm(forms.Form):
    """Three ranked course choices, restricted to the instructor's department."""

    choice_1 = forms.ModelChoiceField(queryset=None, label="1st choice")
    choice_2 = forms.ModelChoiceField(queryset=None, label="2nd choice")
    choice_3 = forms.ModelChoiceField(queryset=None, label="3rd choice")

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        from curriculum.models import Course

        qs = Course.objects.filter(department=department)
        for field in ("choice_1", "choice_2", "choice_3"):
            self.fields[field].queryset = qs

    def clean(self):
        cleaned = super().clean()
        choices = [cleaned.get("choice_1"), cleaned.get("choice_2"), cleaned.get("choice_3")]
        if all(choices) and len({c.id for c in choices}) != 3:
            raise forms.ValidationError("Your three choices must be different courses.")
        return cleaned
