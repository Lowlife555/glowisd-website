from django import forms

from products.models import ContactMessage


class ContactForm(forms.ModelForm):
    """询价表单：姓名/邮箱/留言必填，邮箱格式由 ModelForm 校验。

    `product` 为隐藏字段（非模型字段）：产品详情页跳转 `/contact/?product=<sku>` 时，
    前台把 sku 放进隐藏输入随表单一并提交，视图据此关联 inquired_product。
    """
    product = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = ContactMessage
        fields = ['name', 'company', 'email', 'phone', 'country', 'category', 'message']
