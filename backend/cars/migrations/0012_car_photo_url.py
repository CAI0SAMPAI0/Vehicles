from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0011_pricealert'),
    ]

    operations = [
        migrations.AddField(
            model_name='car',
            name='photo_url',
            field=models.URLField(blank=True, max_length=1000, null=True),
        ),
    ]
