"""补建两个页头图片槽位的数据行（产品目录页、联系页）。

新增 KEY_CHOICES 只是允许这两个 key，后台列表靠数据库里的行来展示；
这里把行建出来（无图 → 前台回退占位/纯色页头）。
"""

from django.db import migrations

NEW_SLOTS = ['catalog_hero', 'contact_hero']


def create_slots(apps, schema_editor):
    SiteImage = apps.get_model('core', 'SiteImage')
    for key in NEW_SLOTS:
        SiteImage.objects.get_or_create(key=key)


def drop_slots(apps, schema_editor):
    SiteImage = apps.get_model('core', 'SiteImage')
    SiteImage.objects.filter(key__in=NEW_SLOTS, image='').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_alter_siteimage_key'),
    ]

    operations = [
        migrations.RunPython(create_slots, drop_slots),
    ]
