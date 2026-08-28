from django import forms

from products.models import ContactMessage


class ContactForm(forms.ModelForm):
    """询价表单：姓名/邮箱/留言必填，邮箱格式由 ModelForm 校验。"""

    class Meta:
        model = ContactMessage
        fields = ['name', 'company', 'email', 'phone', 'country', 'category', 'message']
