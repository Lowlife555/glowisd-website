# 数据迁移：水印位置统一改到左上角（V0.4.0）
# 已有 SiteSettings 行的 watermark_position='bottom_right' → 'top_left'

from django.db import migrations


def forwards(apps, schema_editor):
    SiteSettings = apps.get_model('core', 'SiteSettings')
    updated = SiteSettings.objects.filter(watermark_position='bottom_right').update(watermark_position='top_left')
    print(f'  [0009] watermark_position bottom_right -> top_left: {updated} rows')


def backwards(apps, schema_editor):
    SiteSettings = apps.get_model('core', 'SiteSettings')
    updated = SiteSettings.objects.filter(watermark_position='top_left').update(watermark_position='bottom_right')
    print(f'  [0009] watermark_position top_left -> bottom_right: {updated} rows')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_alter_sitesettings_watermark_position'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
