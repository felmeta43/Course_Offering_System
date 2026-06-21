from django import forms


class ExcelUploadForm(forms.Form):
    workbook = forms.FileField(label="Excel file (.xlsx)")
