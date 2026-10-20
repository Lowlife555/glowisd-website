"""预置 7 个站点图片槽位（后台「站点图片」列表可见全部位置，上传即替换）。"""
from django.db import migrations

SLOTS = [
    'home_factory',
    'factory_hero',
    'workshop_1',
    'workshop_2',
    'workshop_3',
    'workshop_4',
    'custom_hero',
]


def seed_slots(apps, schema_editor):
    SiteImage = apps.get_model('core', 'SiteImage')
    for key in SLOTS:
        SiteImage.objects.get_or_create(key=key)


def unseed_slots(apps, schema_editor):
    SiteImage = apps.get_model('core', 'SiteImage')
    SiteImage.objects.filter(key__in=SLOTS, image='').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_siteimage'),
    ]

    operations = [
        migrations.RunPython(seed_slots, unseed_slots),
    ]
