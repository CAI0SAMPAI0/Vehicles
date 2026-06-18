from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0005_car_bio'),
    ]

    operations = [
        migrations.AddField(
            model_name='car',
            name='categoria',
            field=models.CharField(
                blank=True,
                choices=[
                    ('SEDAN', 'Sedan'),
                    ('SUV', 'SUV'),
                    ('HATCH', 'Hatch'),
                    ('PICAPE', 'Picape'),
                    ('ESPORTIVO', 'Esportivo'),
                    ('MINIVAN', 'Minivan'),
                    ('ELETRICO', 'Elétrico'),
                    ('CLASSICO', 'Clássico'),
                    ('OUTRO', 'Outro'),
                ],
                default=None,
                max_length=20,
                null=True,
            ),
        ),
    ]
