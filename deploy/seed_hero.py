from core.models import HeroSlide

for i in range(1, 7):
    HeroSlide.objects.get_or_create(
        sort_order=i,
        defaults={'image': f'hero/hero{i}.jpg', 'is_active': True},
    )
print('HeroSlide count:', HeroSlide.objects.count())
